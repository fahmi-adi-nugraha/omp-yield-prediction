from __future__ import annotations

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
    assert settings.allow_mutations is True


def test_environment_overrides(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OMP_DOCKER_BUILD_DIR", str(tmp_path))
    monkeypatch.setenv("OMP_DOCKER_COMPOSE_FILE", "custom.yml")
    monkeypatch.setenv("OMP_DOCKER_SERVICE", "database")
    monkeypatch.setenv("OMP_DOCKER_BUILD_TIMEOUT_SECONDS", "42")
    monkeypatch.setenv("OMP_DOCKER_LIFECYCLE_TIMEOUT_SECONDS", "7")
    monkeypatch.setenv("OMP_MCP_ALLOW_DOCKER_MUTATIONS", "0")

    settings = DemoDbSettings()

    assert settings.resolved_build_dir == tmp_path.resolve()
    assert settings.compose_path == (tmp_path / "custom.yml").resolve()
    assert settings.service == "database"
    assert settings.build_timeout_seconds == 42
    assert settings.lifecycle_timeout_seconds == 7
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
