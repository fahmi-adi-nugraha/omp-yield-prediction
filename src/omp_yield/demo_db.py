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
        # Reserved for mutating lifecycle operations added in later parts.
        self._lock = threading.Lock()

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

    def _secret_values(self) -> tuple[str, ...]:
        return secret_values(self._environ)
