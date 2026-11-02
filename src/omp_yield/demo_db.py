"""Scoped Docker Compose helpers for the local demo database stack."""

from __future__ import annotations

import contextlib
import json
import os
import signal
import subprocess
import threading
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SECRET_ENV_KEYS = ("MSSQL_SA_PASSWORD", "OMP_DB_PASSWORD", "OMP_SERVER_PASS")
_MAX_TAIL_LINES = 200
_MAX_TAIL_CHARS = 16_000


class DemoDbError(RuntimeError):
    """Raised when the demo database Docker stack cannot be managed."""


def redact_secrets(text: str, secrets: Iterable[str]) -> str:
    """Replace known secret values in text with a fixed marker."""

    values = sorted({value for value in secrets if value}, key=len, reverse=True)
    redacted = text
    for value in values:
        redacted = redacted.replace(value, "***")
    return redacted


def secret_values(environ: Mapping[str, str] | None = None) -> tuple[str, ...]:
    """Return sensitive environment values that must never appear in output."""

    source = os.environ if environ is None else environ
    return tuple(value for key in _SECRET_ENV_KEYS if (value := source.get(key)))


def tail_text(
    text: str,
    *,
    max_lines: int = _MAX_TAIL_LINES,
    max_chars: int = _MAX_TAIL_CHARS,
) -> str:
    """Keep the end of a potentially large command output."""

    if not text:
        return ""

    lines = text.splitlines()
    line_limit = max(1, max_lines)
    if len(lines) > line_limit:
        lines = ["...", *lines[-line_limit:]]
    result = "\n".join(lines)

    char_limit = max(1, max_chars)
    if len(result) > char_limit:
        result = "..." + result[-char_limit:]
    return result


class DemoDbSettings(BaseSettings):
    """Environment-driven settings for the demo database Compose stack."""

    model_config = SettingsConfigDict(
        env_prefix="OMP_DOCKER_",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    build_dir: Path = Field(default_factory=lambda: _REPO_ROOT / "docker-build")
    compose_file: str = Field(default="docker-compose.yml")
    service: str = Field(default="db")
    build_timeout_seconds: int = Field(default=600, ge=1, le=3600)
    lifecycle_timeout_seconds: int = Field(default=120, ge=1, le=3600)
    status_timeout_seconds: int = Field(default=30, ge=1, le=600)
    allow_mutations: bool = Field(
        default=True,
        validation_alias="OMP_MCP_ALLOW_DOCKER_MUTATIONS",
    )

    @property
    def resolved_build_dir(self) -> Path:
        """Absolute path to the Compose project directory."""

        return self.build_dir.expanduser().resolve()

    @property
    def compose_path(self) -> Path:
        """Absolute path to the Compose file."""

        candidate = Path(self.compose_file).expanduser()
        if not candidate.is_absolute():
            candidate = self.resolved_build_dir / candidate
        return candidate.resolve()

    def validate_paths(self) -> None:
        """Raise a clear error when the Compose project is not usable."""

        if not self.resolved_build_dir.is_dir():
            raise DemoDbError(f"Docker build directory not found: {self.resolved_build_dir}")
        if not self.compose_path.is_file():
            raise DemoDbError(f"Compose file not found: {self.compose_path}")


@dataclass(frozen=True)
class CommandResult:
    """Captured result of one external command."""

    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        """Whether the command completed successfully."""

        return self.returncode == 0 and not self.timed_out

    def redacted(self, secrets: Iterable[str]) -> CommandResult:
        """Return a copy with secret values removed from output."""

        values = tuple(secrets)
        return replace(
            self,
            stdout=redact_secrets(self.stdout, values),
            stderr=redact_secrets(self.stderr, values),
        )

    def to_dict(
        self,
        *,
        max_lines: int = _MAX_TAIL_LINES,
        max_chars: int = _MAX_TAIL_CHARS,
    ) -> dict[str, Any]:
        """Return a bounded, JSON-serializable representation."""

        return {
            "ok": self.ok,
            "command": list(self.command),
            "returncode": self.returncode,
            "stdout_tail": tail_text(
                self.stdout, max_lines=max_lines, max_chars=max_chars
            ),
            "stderr_tail": tail_text(
                self.stderr, max_lines=max_lines, max_chars=max_chars
            ),
            "duration_seconds": round(self.duration_seconds, 3),
            "timed_out": self.timed_out,
        }


def _command_error(result: CommandResult) -> str:
    if result.timed_out:
        return "Command timed out."
    detail = tail_text(
        result.stderr or result.stdout,
        max_lines=20,
        max_chars=4000,
    ).strip()
    if detail:
        return detail
    return f"Command failed with exit code {result.returncode}."


def _service_model(model: dict[str, Any], service: str) -> dict[str, Any]:
    services = model.get("services")
    if not isinstance(services, dict):
        return {}
    value = services.get(service)
    if not isinstance(value, dict):
        return {}
    return value


def _data_volume(
    model: dict[str, Any],
    service_model: dict[str, Any],
) -> tuple[str | None, str | None]:
    volumes = model.get("volumes")
    mounts = service_model.get("volumes")
    if not isinstance(volumes, dict) or not isinstance(mounts, list):
        return None, None

    for mount in mounts:
        if not isinstance(mount, dict) or mount.get("target") != "/var/opt/mssql":
            continue
        source = mount.get("source")
        if not isinstance(source, str):
            continue
        definition = volumes.get(source)
        if isinstance(definition, dict):
            name = definition.get("name")
            if isinstance(name, str):
                return source, name
        return source, source
    return None, None


def _empty_container(error: str | None = None) -> dict[str, Any]:
    return {
        "present": False,
        "id": None,
        "name": None,
        "state": None,
        "running": False,
        "started_at": None,
        "image_id": None,
        "image_name": None,
        "image_matches": None,
        "error": error,
    }


def _as_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _terminate_process_group(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return

    try:
        if os.name == "posix":
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        else:
            process.kill()
    except OSError:
        with contextlib.suppress(OSError):
            process.kill()


def run_command(
    command: Sequence[str],
    *,
    timeout_seconds: float,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> CommandResult:
    """Run one command without a shell and capture its output.

    The child is started in its own process group so a timeout also terminates
    helper processes started by the Docker CLI.
    """

    argv = tuple(str(part) for part in command)
    if not argv:
        raise DemoDbError("Cannot run an empty command.")

    process: subprocess.Popen[str]
    try:
        process = subprocess.Popen(
            argv,
            cwd=str(cwd) if cwd is not None else None,
            env=dict(env) if env is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
            start_new_session=os.name == "posix",
        )
    except FileNotFoundError as exc:
        raise DemoDbError(f"Command not found: {argv[0]}") from exc
    except OSError as exc:
        raise DemoDbError(f"Failed to start command {argv[0]}: {exc}") from exc

    started = time.monotonic()
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        _terminate_process_group(process)
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            stdout, stderr = "", ""

    duration = time.monotonic() - started
    return CommandResult(
        command=argv,
        returncode=process.returncode if process.returncode is not None else -1,
        stdout=_as_text(stdout),
        stderr=_as_text(stderr),
        duration_seconds=duration,
        timed_out=timed_out,
    )


class DemoDbManager:
    """Run scoped Docker Compose commands for the demo database stack."""

    def __init__(
        self,
        settings: DemoDbSettings | None = None,
        *,
        runner: Callable[..., CommandResult] | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        self.settings = settings or DemoDbSettings()
        self._runner = runner or run_command
        self._environ = environ
        # Serialize mutating lifecycle operations. RLock allows up() to call
        # build() while holding the same lock.
        self._lock = threading.RLock()

    def validate(self) -> None:
        """Validate that the Compose project is present and readable."""

        self.settings.validate_paths()

    def compose_command(self, *args: str) -> tuple[str, ...]:
        """Build the scoped Docker Compose command line."""

        return (
            "docker",
            "compose",
            "--ansi",
            "never",
            "--project-directory",
            str(self.settings.resolved_build_dir),
            "-f",
            str(self.settings.compose_path),
            *args,
        )

    def run_compose(
        self,
        args: Sequence[str],
        *,
        timeout_seconds: float | None = None,
    ) -> CommandResult:
        """Run one Compose subcommand and redact any known secrets."""

        self.validate()
        timeout = (
            timeout_seconds
            if timeout_seconds is not None
            else float(self.settings.lifecycle_timeout_seconds)
        )
        result = self._runner(
            self.compose_command(*args),
            timeout_seconds=timeout,
            cwd=self.settings.resolved_build_dir,
            env=dict(self._environ) if self._environ is not None else None,
        )
        return result.redacted(self._secret_values())

    def run_docker(
        self,
        args: Sequence[str],
        *,
        timeout_seconds: float | None = None,
    ) -> CommandResult:
        """Run one Docker command and redact any known secrets."""

        timeout = (
            timeout_seconds
            if timeout_seconds is not None
            else float(self.settings.status_timeout_seconds)
        )
        result = self._runner(
            ("docker", *args),
            timeout_seconds=timeout,
            cwd=None,
            env=dict(self._environ) if self._environ is not None else None,
        )
        return result.redacted(self._secret_values())

    def status(self) -> dict[str, Any]:
        """Return a read-only snapshot of the Docker demo DB stack."""

        docker_version, docker_error = self._docker_version()
        status: dict[str, Any] = {
            "ok": docker_version is not None,
            "ready": False,
            "docker_available": docker_version is not None,
            "docker_version": docker_version,
            "docker_error": docker_error,
            "compose_valid": False,
            "compose_error": None,
            "project_name": None,
            "service": self.settings.service,
            "compose_file": str(self.settings.compose_path),
            "build_dir": str(self.settings.resolved_build_dir),
            "image": None,
            "container": None,
            "volume": None,
            "setup_done": None,
        }
        if docker_version is None:
            return status

        model, compose_error = self._compose_model()
        if model is None:
            status["ok"] = False
            status["compose_error"] = compose_error
            return status

        status["ok"] = True
        status["compose_valid"] = True

        service_model = _service_model(model, self.settings.service)
        project_name = model.get("name")
        if isinstance(project_name, str):
            status["project_name"] = project_name

        image_name = service_model.get("image")
        if not isinstance(image_name, str):
            image_name = None
        container_name = service_model.get("container_name")
        if not isinstance(container_name, str):
            container_name = None
        volume_key, volume_name = _data_volume(model, service_model)

        image = self._image_status(image_name)
        container = self._container_status(self.settings.service)
        container["expected_name"] = container_name
        volume = self._volume_status(volume_name)
        if volume_key is not None:
            volume["key"] = volume_key
        setup_done = self._setup_done(container)

        image_matches: bool | None = None
        if image.get("present") and container.get("present"):
            image_matches = image.get("id") == container.get("image_id")
        container["image_matches"] = image_matches

        status["image"] = image
        status["container"] = container
        status["volume"] = volume
        status["setup_done"] = setup_done
        status["ready"] = bool(
            image.get("present")
            and container.get("present")
            and container.get("running")
            and image_matches is True
            and setup_done is True
            and volume.get("present")
        )
        return status

    def logs(self, tail: int = 100) -> dict[str, Any]:
        """Return the tail of the demo DB Compose logs."""

        limit = max(1, min(int(tail), 1000))
        try:
            result = self.run_compose(
                ["logs", "--no-color", "--tail", str(limit), self.settings.service],
                timeout_seconds=float(self.settings.status_timeout_seconds),
            )
        except DemoDbError as exc:
            return {
                "ok": False,
                "lines": [],
                "line_count": 0,
                "returncode": None,
                "timed_out": False,
                "stderr_tail": "",
                "error": str(exc),
            }

        text = tail_text(result.stdout, max_lines=limit, max_chars=_MAX_TAIL_CHARS)
        lines = text.splitlines() if text else []
        return {
            "ok": result.ok,
            "lines": lines,
            "line_count": len(lines),
            "returncode": result.returncode,
            "timed_out": result.timed_out,
            "stderr_tail": tail_text(result.stderr, max_lines=20, max_chars=4000),
            "error": None if result.ok else _command_error(result),
        }

    def build(self, force: bool = False) -> dict[str, Any]:
        """Build the demo database image if it is missing or force is set."""

        try:
            self._ensure_mutations_enabled()
            with self._lock:
                image_name, error = self._image_name()
                if image_name is None:
                    return {"ok": False, "action": "build_failed", "error": error}

                image = self._image_status(image_name)
                if image["present"] and not force:
                    return {
                        "ok": True,
                        "action": "skipped",
                        "reason": "Image already exists.",
                        "image": image,
                    }

                result = self.run_compose(
                    ["build"],
                    timeout_seconds=float(self.settings.build_timeout_seconds),
                )
                image_after = self._image_status(image_name)
                payload: dict[str, Any] = {
                    "ok": result.ok and image_after["present"],
                    "action": "built" if result.ok else "build_failed",
                    "image": image_after,
                    **self._command_fields(result),
                }
                if result.ok and not image_after["present"]:
                    payload["ok"] = False
                    payload["error"] = "Build completed but the image was not found."
                return payload
        except DemoDbError as exc:
            return {"ok": False, "action": "build_failed", "error": str(exc)}

    def up(self, recreate: bool = False) -> dict[str, Any]:
        """Create or start the demo database container, building if needed."""

        try:
            self._ensure_mutations_enabled()
            with self._lock:
                image_name, error = self._image_name()
                if image_name is None:
                    return {"ok": False, "action": "up_failed", "error": error}

                image = self._image_status(image_name)
                if not image["present"]:
                    build_result = self.build()
                    if not build_result.get("ok"):
                        return {
                            "ok": False,
                            "action": "up_failed",
                            "error": "Image build failed.",
                            "stderr_tail": build_result.get("stderr_tail", ""),
                            "build": build_result,
                        }
                    built_image = build_result.get("image")
                    if isinstance(built_image, dict):
                        image = built_image

                args = ["up", "-d", "--no-build"]
                if recreate:
                    args.append("--force-recreate")
                result = self.run_compose(
                    args,
                    timeout_seconds=float(self.settings.lifecycle_timeout_seconds),
                )
                return {
                    "ok": result.ok,
                    "action": "up" if result.ok else "up_failed",
                    "recreate": recreate,
                    "image": image,
                    **self._command_fields(result),
                }
        except DemoDbError as exc:
            return {"ok": False, "action": "up_failed", "error": str(exc)}

    def stop(self) -> dict[str, Any]:
        """Stop the demo database container without removing it."""

        try:
            self._ensure_mutations_enabled()
            with self._lock:
                container = self._container_status(self.settings.service)
                if not container.get("present"):
                    return {
                        "ok": True,
                        "action": "noop",
                        "reason": "Container does not exist.",
                    }
                if not container.get("running"):
                    return {
                        "ok": True,
                        "action": "noop",
                        "reason": "Container is already stopped.",
                    }
                result = self.run_compose(
                    ["stop", self.settings.service],
                    timeout_seconds=float(self.settings.lifecycle_timeout_seconds),
                )
                return self._lifecycle_result(result, "stopped", "stop_failed")
        except DemoDbError as exc:
            return {"ok": False, "action": "stop_failed", "error": str(exc)}

    def start(self) -> dict[str, Any]:
        """Start an existing stopped demo database container."""

        try:
            self._ensure_mutations_enabled()
            with self._lock:
                container = self._container_status(self.settings.service)
                if not container.get("present"):
                    return {
                        "ok": False,
                        "action": "start_failed",
                        "error": "Container does not exist. Use demo_db_up to create it.",
                    }
                if container.get("running"):
                    return {
                        "ok": True,
                        "action": "noop",
                        "reason": "Container is already running.",
                    }
                result = self.run_compose(
                    ["start", self.settings.service],
                    timeout_seconds=float(self.settings.lifecycle_timeout_seconds),
                )
                return self._lifecycle_result(result, "started", "start_failed")
        except DemoDbError as exc:
            return {"ok": False, "action": "start_failed", "error": str(exc)}

    def restart(self) -> dict[str, Any]:
        """Restart an existing demo database container."""

        try:
            self._ensure_mutations_enabled()
            with self._lock:
                container = self._container_status(self.settings.service)
                if not container.get("present"):
                    return {
                        "ok": False,
                        "action": "restart_failed",
                        "error": "Container does not exist. Use demo_db_up to create it.",
                    }
                result = self.run_compose(
                    ["restart", self.settings.service],
                    timeout_seconds=float(self.settings.lifecycle_timeout_seconds),
                )
                return self._lifecycle_result(result, "restarted", "restart_failed")
        except DemoDbError as exc:
            return {"ok": False, "action": "restart_failed", "error": str(exc)}

    def down(self, remove_volumes: bool = False) -> dict[str, Any]:
        """Stop and remove the stack, optionally deleting the data volume."""

        try:
            self._ensure_mutations_enabled()
            with self._lock:
                model, compose_error = self._compose_model()
                if model is None:
                    return {
                        "ok": False,
                        "action": "down_failed",
                        "error": compose_error or "Compose config is invalid.",
                    }

                service_model = _service_model(model, self.settings.service)
                _, volume_name = _data_volume(model, service_model)
                args = ["down"]
                if remove_volumes:
                    args.append("-v")

                result = self.run_compose(
                    args,
                    timeout_seconds=float(self.settings.lifecycle_timeout_seconds),
                )
                volume_after = self._volume_status(volume_name)
                payload = self._lifecycle_result(result, "down", "down_failed")
                payload["remove_volumes"] = remove_volumes
                payload["volume"] = volume_after
                if result.ok:
                    if remove_volumes:
                        if volume_after["present"]:
                            payload["warning"] = (
                                "Docker Compose completed, but the database volume still exists."
                            )
                        else:
                            payload["warning"] = (
                                "The demo database volume was removed. "
                                "The next up will restore from backup."
                            )
                    else:
                        payload["warning"] = "The demo database volume was preserved."
                return payload
        except DemoDbError as exc:
            return {"ok": False, "action": "down_failed", "error": str(exc)}

    def _docker_version(self) -> tuple[str | None, str | None]:
        try:
            result = self.run_docker(
                ["version", "--format", "{{.Server.Version}}"],
                timeout_seconds=float(self.settings.status_timeout_seconds),
            )
        except DemoDbError as exc:
            return None, str(exc)
        if not result.ok:
            return None, _command_error(result)
        version = result.stdout.strip()
        if not version:
            return None, "Docker version was empty."
        return version, None

    def _compose_model(self) -> tuple[dict[str, Any] | None, str | None]:
        try:
            result = self.run_compose(
                ["config", "--format", "json"],
                timeout_seconds=float(self.settings.status_timeout_seconds),
            )
        except DemoDbError as exc:
            return None, str(exc)
        if not result.ok:
            return None, _command_error(result)
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            return None, f"Could not parse docker compose config: {exc}"
        if not isinstance(payload, dict):
            return None, "Unexpected docker compose config output."
        return payload, None

    def _image_status(self, image_name: str | None) -> dict[str, Any]:
        if not image_name:
            return {"name": None, "present": False, "id": None}
        try:
            result = self.run_docker(
                ["image", "inspect", image_name, "--format", "{{.Id}}"],
                timeout_seconds=float(self.settings.status_timeout_seconds),
            )
        except DemoDbError as exc:
            return {
                "name": image_name,
                "present": False,
                "id": None,
                "error": str(exc),
            }
        if not result.ok:
            return {"name": image_name, "present": False, "id": None}
        return {
            "name": image_name,
            "present": True,
            "id": result.stdout.strip() or None,
        }

    def _container_status(self, service: str) -> dict[str, Any]:
        try:
            ps = self.run_compose(
                ["ps", "-a", "-q", service],
                timeout_seconds=float(self.settings.status_timeout_seconds),
            )
        except DemoDbError as exc:
            return _empty_container(str(exc))
        if not ps.ok:
            return _empty_container(_command_error(ps))

        container_id = ps.stdout.strip().splitlines()[0] if ps.stdout.strip() else None
        if not container_id:
            return _empty_container()

        try:
            inspect = self.run_docker(
                ["inspect", container_id],
                timeout_seconds=float(self.settings.status_timeout_seconds),
            )
        except DemoDbError as exc:
            return _empty_container(str(exc))
        if not inspect.ok:
            return _empty_container(_command_error(inspect))

        try:
            payload = json.loads(inspect.stdout)
        except json.JSONDecodeError as exc:
            return _empty_container(f"Could not parse docker inspect output: {exc}")
        if not isinstance(payload, list) or not payload or not isinstance(payload[0], dict):
            return _empty_container("Unexpected docker inspect output.")

        data = payload[0]
        state = data.get("State")
        state_data = state if isinstance(state, dict) else {}
        config = data.get("Config")
        config_data = config if isinstance(config, dict) else {}
        raw_name = data.get("Name")
        name = raw_name.lstrip("/") if isinstance(raw_name, str) else None

        return {
            "present": True,
            "id": data.get("Id"),
            "name": name,
            "state": state_data.get("Status"),
            "running": bool(state_data.get("Running", False)),
            "started_at": state_data.get("StartedAt"),
            "image_id": data.get("Image"),
            "image_name": config_data.get("Image"),
            "image_matches": None,
            "error": None,
        }

    def _volume_status(self, volume_name: str | None) -> dict[str, Any]:
        if not volume_name:
            return {"name": None, "present": False, "mountpoint": None}
        try:
            result = self.run_docker(
                ["volume", "inspect", volume_name, "--format", "{{.Mountpoint}}"],
                timeout_seconds=float(self.settings.status_timeout_seconds),
            )
        except DemoDbError as exc:
            return {
                "name": volume_name,
                "present": False,
                "mountpoint": None,
                "error": str(exc),
            }
        if not result.ok:
            return {"name": volume_name, "present": False, "mountpoint": None}
        return {
            "name": volume_name,
            "present": True,
            "mountpoint": result.stdout.strip() or None,
        }

    def _setup_done(self, container: Mapping[str, Any]) -> bool | None:
        if not container.get("present") or not container.get("running"):
            return None
        container_id = container.get("id")
        if not isinstance(container_id, str) or not container_id:
            return None
        try:
            result = self.run_docker(
                ["exec", container_id, "test", "-f", "/var/opt/mssql/.setup_done"],
                timeout_seconds=float(self.settings.status_timeout_seconds),
            )
        except DemoDbError:
            return None
        if result.ok:
            return True
        if result.returncode == 1:
            return False
        return None

    def _ensure_mutations_enabled(self) -> None:
        if not self.settings.allow_mutations:
            raise DemoDbError(
                "Docker mutations are disabled. Set "
                "OMP_MCP_ALLOW_DOCKER_MUTATIONS=1 to enable them."
            )

    def _image_name(self) -> tuple[str | None, str | None]:
        model, error = self._compose_model()
        if model is None:
            return None, error
        service_model = _service_model(model, self.settings.service)
        image_name = service_model.get("image")
        if not isinstance(image_name, str) or not image_name:
            return (
                None,
                f"Service {self.settings.service!r} has no image in Compose config.",
            )
        return image_name, None

    def _command_fields(self, result: CommandResult) -> dict[str, Any]:
        return {
            "returncode": result.returncode,
            "timed_out": result.timed_out,
            "duration_seconds": round(result.duration_seconds, 3),
            "stdout_tail": tail_text(result.stdout, max_lines=50, max_chars=8000),
            "stderr_tail": tail_text(result.stderr, max_lines=50, max_chars=8000),
            "error": None if result.ok else _command_error(result),
        }

    def _lifecycle_result(
        self,
        result: CommandResult,
        success_action: str,
        failure_action: str,
    ) -> dict[str, Any]:
        return {
            "ok": result.ok,
            "action": success_action if result.ok else failure_action,
            **self._command_fields(result),
        }

    def _secret_values(self) -> tuple[str, ...]:
        return secret_values(self._environ)
