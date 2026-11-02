from __future__ import annotations

import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from omp_yield.demo_db import (
    CommandResult,
    DemoDbError,
    DemoDbManager,
    DemoDbSettings,
    redact_secrets,
    run_command,
    secret_values,
    tail_text,
)

_ENV_KEYS = (
    "OMP_DOCKER_BUILD_DIR",
    "OMP_DOCKER_COMPOSE_FILE",
    "OMP_DOCKER_SERVICE",
    "OMP_DOCKER_BUILD_TIMEOUT_SECONDS",
    "OMP_DOCKER_LIFECYCLE_TIMEOUT_SECONDS",
    "OMP_DOCKER_STATUS_TIMEOUT_SECONDS",
    "OMP_MCP_ALLOW_DOCKER_MUTATIONS",
    "MSSQL_SA_PASSWORD",
    "OMP_DB_PASSWORD",
    "OMP_SERVER_PASS",
)


@pytest.fixture(autouse=True)
def _clean_demo_db_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def _settings(tmp_path: Path) -> DemoDbSettings:
    compose = tmp_path / "docker-compose.yml"
    compose.write_text("services: {}\n", encoding="utf-8")
    return DemoDbSettings(build_dir=tmp_path, compose_file="docker-compose.yml")


class FakeRunner:
    def __init__(self, result: CommandResult | None = None) -> None:
        self.calls: list[tuple[tuple[str, ...], dict[str, Any]]] = []
        self.result = result or CommandResult(
            command=("docker",),
            returncode=0,
            stdout="",
            stderr="",
            duration_seconds=0.01,
        )

    def __call__(
        self,
        command: Sequence[str],
        *,
        timeout_seconds: float,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
    ) -> CommandResult:
        self.calls.append(
            (
                tuple(command),
                {
                    "timeout_seconds": timeout_seconds,
                    "cwd": cwd,
                    "env": env,
                },
            )
        )
        return self.result


def test_default_settings() -> None:
    settings = DemoDbSettings()

    assert settings.build_dir.name == "docker-build"
    assert settings.build_dir.is_absolute()
    assert settings.compose_path.name == "docker-compose.yml"
    assert settings.service == "db"
    assert settings.build_timeout_seconds == 600
    assert settings.lifecycle_timeout_seconds == 120
    assert settings.status_timeout_seconds == 30
    assert settings.allow_mutations is True


def test_environment_overrides(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OMP_DOCKER_BUILD_DIR", str(tmp_path))
    monkeypatch.setenv("OMP_DOCKER_COMPOSE_FILE", "custom.yml")
    monkeypatch.setenv("OMP_DOCKER_SERVICE", "database")
    monkeypatch.setenv("OMP_DOCKER_BUILD_TIMEOUT_SECONDS", "42")
    monkeypatch.setenv("OMP_DOCKER_LIFECYCLE_TIMEOUT_SECONDS", "7")
    monkeypatch.setenv("OMP_DOCKER_STATUS_TIMEOUT_SECONDS", "9")
    monkeypatch.setenv("OMP_MCP_ALLOW_DOCKER_MUTATIONS", "0")

    settings = DemoDbSettings()

    assert settings.resolved_build_dir == tmp_path.resolve()
    assert settings.compose_path == (tmp_path / "custom.yml").resolve()
    assert settings.service == "database"
    assert settings.build_timeout_seconds == 42
    assert settings.lifecycle_timeout_seconds == 7
    assert settings.status_timeout_seconds == 9
    assert settings.allow_mutations is False


def test_absolute_compose_file(tmp_path: Path) -> None:
    compose = tmp_path / "custom.yml"
    settings = DemoDbSettings(build_dir=tmp_path, compose_file=str(compose))

    assert settings.compose_path == compose.resolve()


def test_validate_missing_build_dir(tmp_path: Path) -> None:
    settings = DemoDbSettings(build_dir=tmp_path / "missing")
    manager = DemoDbManager(settings=settings)

    with pytest.raises(DemoDbError, match="Docker build directory not found"):
        manager.validate()


def test_validate_missing_compose_file(tmp_path: Path) -> None:
    settings = DemoDbSettings(build_dir=tmp_path)
    manager = DemoDbManager(settings=settings)

    with pytest.raises(DemoDbError, match="Compose file not found"):
        manager.validate()


def test_compose_command_is_scoped_and_uses_argv(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    manager = DemoDbManager(settings=settings)

    command = manager.compose_command("ps", "-q", settings.service)

    assert command == (
        "docker",
        "compose",
        "--ansi",
        "never",
        "--project-directory",
        str(tmp_path.resolve()),
        "-f",
        str((tmp_path / "docker-compose.yml").resolve()),
        "ps",
        "-q",
        "db",
    )


def test_run_compose_passes_command_and_redacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("MSSQL_SA_PASSWORD", "super-secret")
    fake = FakeRunner(
        CommandResult(
            command=("docker",),
            returncode=0,
            stdout="stdout super-secret",
            stderr="stderr super-secret",
            duration_seconds=0.1,
        )
    )
    manager = DemoDbManager(settings=_settings(tmp_path), runner=fake)

    result = manager.run_compose(["config"], timeout_seconds=7)

    assert "super-secret" not in result.stdout
    assert "super-secret" not in result.stderr
    assert result.stdout == "stdout ***"
    assert result.stderr == "stderr ***"
    assert fake.calls[0][0] == manager.compose_command("config")
    assert fake.calls[0][1]["timeout_seconds"] == 7
    assert fake.calls[0][1]["cwd"] == tmp_path.resolve()


def test_run_compose_uses_default_lifecycle_timeout(tmp_path: Path) -> None:
    fake = FakeRunner()
    manager = DemoDbManager(settings=_settings(tmp_path), runner=fake)

    manager.run_compose(["ps"])

    assert fake.calls[0][1]["timeout_seconds"] == 120


def test_run_compose_invalid_path_does_not_run(tmp_path: Path) -> None:
    fake = FakeRunner()
    manager = DemoDbManager(
        settings=DemoDbSettings(build_dir=tmp_path),
        runner=fake,
    )

    with pytest.raises(DemoDbError, match="Compose file not found"):
        manager.run_compose(["ps"])

    assert fake.calls == []


def test_manager_uses_injected_environment_for_secrets(tmp_path: Path) -> None:
    fake = FakeRunner(
        CommandResult(
            command=("docker",),
            returncode=0,
            stdout="db-secret",
            stderr="",
            duration_seconds=0.1,
        )
    )
    manager = DemoDbManager(
        settings=_settings(tmp_path),
        runner=fake,
        environ={"OMP_DB_PASSWORD": "db-secret"},
    )

    result = manager.run_compose(["ps"])

    assert result.stdout == "***"


def test_run_command_missing_executable() -> None:
    with pytest.raises(DemoDbError, match="Command not found"):
        run_command(["definitely-not-a-real-command-xyz"], timeout_seconds=1)


def test_run_command_does_not_use_shell() -> None:
    with pytest.raises(DemoDbError, match="Command not found"):
        run_command(["echo hello; echo injected"], timeout_seconds=1)


def test_run_command_timeout() -> None:
    result = run_command(
        [sys.executable, "-c", "import time; time.sleep(5)"],
        timeout_seconds=0.2,
    )

    assert result.timed_out is True
    assert result.ok is False
    assert result.returncode != 0
    assert result.duration_seconds < 5


def test_run_command_success() -> None:
    result = run_command(
        [sys.executable, "-c", "print('hello')"],
        timeout_seconds=5,
    )

    assert result.ok is True
    assert result.stdout.strip() == "hello"
    assert result.stderr == ""


def test_redact_secrets() -> None:
    assert redact_secrets("a=super-secret b=super-secret", ["super-secret"]) == (
        "a=*** b=***"
    )
    assert redact_secrets("unchanged", []) == "unchanged"


def test_secret_values() -> None:
    env = {
        "MSSQL_SA_PASSWORD": "sa-secret",
        "OMP_DB_PASSWORD": "db-secret",
        "OMP_SERVER_PASS": "server-secret",
        "UNRELATED": "visible",
    }

    assert set(secret_values(env)) == {"sa-secret", "db-secret", "server-secret"}


def test_tail_text() -> None:
    text = "\n".join(str(index) for index in range(10))

    assert tail_text(text, max_lines=3) == "...\n7\n8\n9"
    assert tail_text("x" * 20, max_lines=10, max_chars=5) == "..." + "x" * 5
    assert tail_text("", max_lines=10, max_chars=10) == ""


def test_command_result_to_dict() -> None:
    result = CommandResult(
        command=("cmd", "arg"),
        returncode=1,
        stdout="x" * 100,
        stderr="y" * 100,
        duration_seconds=0.123456,
    )

    payload = result.to_dict(max_lines=10, max_chars=10)

    assert payload["ok"] is False
    assert payload["command"] == ["cmd", "arg"]
    assert payload["returncode"] == 1
    assert payload["duration_seconds"] == 0.123
    assert payload["stdout_tail"] == "..." + "x" * 10
    assert payload["stderr_tail"] == "..." + "y" * 10
    assert payload["timed_out"] is False


def test_command_result_ok_and_timeout() -> None:
    success = CommandResult(("cmd",), 0, "", "", 0.0)
    timed_out = CommandResult(("cmd",), 0, "", "", 0.0, timed_out=True)

    assert success.ok is True
    assert timed_out.ok is False


def _result(
    command: Sequence[str],
    *,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
    timed_out: bool = False,
) -> CommandResult:
    return CommandResult(
        command=tuple(command),
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
        duration_seconds=0.01,
        timed_out=timed_out,
    )


class DockerFake:
    """Small scripted fake for Docker and Compose commands used by status/logs."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.docker_version: str | None = "29.9.2"
        self.docker_version_error = "Cannot connect to the Docker daemon"
        self.compose_error: str | None = None
        self.compose_model: dict[str, Any] = {
            "name": "docker-build",
            "services": {
                "db": {
                    "image": "omp-as-demo:v306",
                    "container_name": "omp-as-demo-db",
                    "volumes": [
                        {
                            "type": "volume",
                            "source": "mssql-2025-omp-as-demo-db",
                            "target": "/var/opt/mssql",
                        }
                    ],
                }
            },
            "volumes": {
                "mssql-2025-omp-as-demo-db": {
                    "name": "docker-build_mssql-2025-omp-as-demo-db"
                }
            },
        }
        self.image_id: str | None = "sha256:image"
        self.container_id: str | None = "container-id"
        self.container_name = "omp-as-demo-db"
        self.container_state = "running"
        self.container_running = True
        self.container_image_id = "sha256:image"
        self.volume_mountpoint: str | None = "/var/lib/docker/volumes/example/_data"
        self.setup_done: bool | None = True
        self.logs_output = "line 1\nline 2\n"

    def __call__(
        self,
        command: Sequence[str],
        *,
        timeout_seconds: float,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
    ) -> CommandResult:
        argv = tuple(command)
        self.calls.append(argv)

        if argv[:2] == ("docker", "version"):
            if self.docker_version is None:
                return _result(
                    argv,
                    returncode=1,
                    stderr=self.docker_version_error,
                )
            return _result(argv, stdout=f"{self.docker_version}\n")

        if "compose" in argv:
            if self.compose_error is not None:
                return _result(argv, returncode=1, stderr=self.compose_error)
            if "config" in argv:
                return _result(argv, stdout=json.dumps(self.compose_model))
            if "ps" in argv:
                container = f"{self.container_id}\n" if self.container_id else ""
                return _result(argv, stdout=container)
            if "logs" in argv:
                return _result(argv, stdout=self.logs_output)

        if argv[:3] == ("docker", "image", "inspect"):
            if self.image_id is None:
                return _result(argv, returncode=1, stderr="No such image")
            return _result(argv, stdout=f"{self.image_id}\n")

        if argv[:2] == ("docker", "inspect"):
            if self.container_id is None:
                return _result(argv, returncode=1, stderr="no such object")
            payload = [
                {
                    "Id": self.container_id,
                    "Name": f"/{self.container_name}",
                    "Image": self.container_image_id,
                    "State": {
                        "Status": self.container_state,
                        "Running": self.container_running,
                        "StartedAt": "2026-11-02T00:00:00Z",
                    },
                    "Config": {"Image": "omp-as-demo:v306"},
                }
            ]
            return _result(argv, stdout=json.dumps(payload))

        if argv[:3] == ("docker", "volume", "inspect"):
            if self.volume_mountpoint is None:
                return _result(argv, returncode=1, stderr="no such volume")
            return _result(argv, stdout=f"{self.volume_mountpoint}\n")

        if argv[:2] == ("docker", "exec"):
            if self.setup_done is None:
                return _result(argv, returncode=2, stderr="exec failed")
            if self.setup_done:
                return _result(argv, stdout="")
            return _result(argv, returncode=1, stdout="")

        return _result(argv)


def test_status_docker_unavailable(tmp_path: Path) -> None:
    fake = DockerFake()
    fake.docker_version = None
    manager = DemoDbManager(settings=_settings(tmp_path), runner=fake)

    status = manager.status()

    assert status["ok"] is False
    assert status["ready"] is False
    assert status["docker_available"] is False
    assert status["compose_valid"] is False
    assert "Cannot connect" in str(status["docker_error"])
    assert fake.calls == [("docker", "version", "--format", "{{.Server.Version}}")]


def test_status_compose_invalid(tmp_path: Path) -> None:
    fake = DockerFake()
    fake.compose_error = (
        'service "db" refers to undefined volume mssql-2025-omp-as-demod-b: '
        "invalid compose project"
    )
    manager = DemoDbManager(settings=_settings(tmp_path), runner=fake)

    status = manager.status()

    assert status["ok"] is False
    assert status["docker_available"] is True
    assert status["compose_valid"] is False
    assert status["compose_error"] == fake.compose_error
    assert status["image"] is None
    assert status["container"] is None
    assert status["volume"] is None
    assert status["ready"] is False


def test_status_healthy_stack(tmp_path: Path) -> None:
    fake = DockerFake()
    manager = DemoDbManager(settings=_settings(tmp_path), runner=fake)

    status = manager.status()

    assert status["ok"] is True
    assert status["ready"] is True
    assert status["docker_available"] is True
    assert status["docker_version"] == "29.9.2"
    assert status["compose_valid"] is True
    assert status["project_name"] == "docker-build"
    assert status["service"] == "db"
    assert status["image"] == {
        "name": "omp-as-demo:v306",
        "present": True,
        "id": "sha256:image",
    }
    assert status["container"]["present"] is True
    assert status["container"]["id"] == "container-id"
    assert status["container"]["name"] == "omp-as-demo-db"
    assert status["container"]["expected_name"] == "omp-as-demo-db"
    assert status["container"]["state"] == "running"
    assert status["container"]["running"] is True
    assert status["container"]["image_matches"] is True
    assert status["volume"] == {
        "key": "mssql-2025-omp-as-demo-db",
        "name": "docker-build_mssql-2025-omp-as-demo-db",
        "present": True,
        "mountpoint": "/var/lib/docker/volumes/example/_data",
    }
    assert status["setup_done"] is True


def test_status_missing_image(tmp_path: Path) -> None:
    fake = DockerFake()
    fake.image_id = None
    manager = DemoDbManager(settings=_settings(tmp_path), runner=fake)

    status = manager.status()

    assert status["ok"] is True
    assert status["ready"] is False
    assert status["image"]["present"] is False
    assert status["container"]["present"] is True
    assert status["container"]["image_matches"] is None


def test_status_missing_container(tmp_path: Path) -> None:
    fake = DockerFake()
    fake.container_id = None
    manager = DemoDbManager(settings=_settings(tmp_path), runner=fake)

    status = manager.status()

    assert status["ok"] is True
    assert status["ready"] is False
    assert status["image"]["present"] is True
    assert status["container"]["present"] is False
    assert status["setup_done"] is None


def test_status_stopped_container(tmp_path: Path) -> None:
    fake = DockerFake()
    fake.container_state = "exited"
    fake.container_running = False
    manager = DemoDbManager(settings=_settings(tmp_path), runner=fake)

    status = manager.status()

    assert status["ready"] is False
    assert status["container"]["state"] == "exited"
    assert status["container"]["running"] is False
    assert status["setup_done"] is None


def test_status_image_mismatch(tmp_path: Path) -> None:
    fake = DockerFake()
    fake.container_image_id = "sha256:older-image"
    manager = DemoDbManager(settings=_settings(tmp_path), runner=fake)

    status = manager.status()

    assert status["ready"] is False
    assert status["container"]["image_matches"] is False


def test_status_missing_volume(tmp_path: Path) -> None:
    fake = DockerFake()
    fake.volume_mountpoint = None
    manager = DemoDbManager(settings=_settings(tmp_path), runner=fake)

    status = manager.status()

    assert status["ready"] is False
    assert status["volume"]["present"] is False


def test_status_setup_pending(tmp_path: Path) -> None:
    fake = DockerFake()
    fake.setup_done = False
    manager = DemoDbManager(settings=_settings(tmp_path), runner=fake)

    status = manager.status()

    assert status["ready"] is False
    assert status["setup_done"] is False


def test_status_redacts_secrets_in_compose_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("MSSQL_SA_PASSWORD", "super-secret")
    fake = DockerFake()
    fake.compose_error = "compose failed with super-secret"
    manager = DemoDbManager(settings=_settings(tmp_path), runner=fake)

    status = manager.status()

    assert "super-secret" not in str(status["compose_error"])
    assert "***" in str(status["compose_error"])


def test_status_does_not_run_mutating_commands(tmp_path: Path) -> None:
    fake = DockerFake()
    manager = DemoDbManager(settings=_settings(tmp_path), runner=fake)

    manager.status()

    mutating = {"up", "down", "stop", "start", "restart", "build", "rm", "kill"}
    for call in fake.calls:
        assert mutating.isdisjoint(call)


def test_logs_returns_bounded_redacted_tail(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("MSSQL_SA_PASSWORD", "super-secret")
    fake = DockerFake()
    fake.logs_output = "\n".join(f"line {index}" for index in range(300)) + (
        "\nsuper-secret\n"
    )
    manager = DemoDbManager(settings=_settings(tmp_path), runner=fake)

    result = manager.logs(tail=5)

    assert result["ok"] is True
    assert len(result["lines"]) <= 6
    assert result["line_count"] == len(result["lines"])
    assert "super-secret" not in "\n".join(result["lines"])
    assert "***" in "\n".join(result["lines"])
    logs_call = next(call for call in fake.calls if "logs" in call)
    assert logs_call[-3:] == ("--tail", "5", "db")


def test_logs_clamps_tail(tmp_path: Path) -> None:
    fake = DockerFake()
    manager = DemoDbManager(settings=_settings(tmp_path), runner=fake)

    manager.logs(tail=0)
    manager.logs(tail=5000)

    calls = [call for call in fake.calls if "logs" in call]
    assert calls[0][-3:] == ("--tail", "1", "db")
    assert calls[1][-3:] == ("--tail", "1000", "db")


def test_logs_invalid_compose(tmp_path: Path) -> None:
    fake = DockerFake()
    fake.compose_error = "invalid compose configuration"
    manager = DemoDbManager(settings=_settings(tmp_path), runner=fake)

    result = manager.logs()

    assert result["ok"] is False
    assert result["lines"] == []
    assert result["error"] == "invalid compose configuration"
