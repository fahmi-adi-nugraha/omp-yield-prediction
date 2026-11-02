"""Scoped Docker Compose helpers for the local demo database stack."""

from __future__ import annotations

import contextlib
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

    def _secret_values(self) -> tuple[str, ...]:
        return secret_values(self._environ)
