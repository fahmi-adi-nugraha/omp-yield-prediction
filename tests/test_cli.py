from __future__ import annotations

from typing import Any

import pytest
from typer.testing import CliRunner

from omp_yield.cli import app


def test_version() -> None:
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "omp-yield 0.1.0" in result.output


def test_info_does_not_leak_password() -> None:
    result = CliRunner().invoke(app, ["info"])
    assert result.exit_code == 0
    assert "omp_as_demo" in result.output
    assert "OMP_DB_PASSWORD" not in result.output


class FakeDemoDbManager:
    def __init__(self, result: dict[str, Any]) -> None:
        self.result = result
        self.build_force: bool | None = None
        self.up_recreate: bool | None = None
        self.down_remove_volumes: bool | None = None
        self.logs_tail: int | None = None

    def status(self) -> dict[str, Any]:
        return self.result

    def build(self, force: bool = False) -> dict[str, Any]:
        self.build_force = force
        return self.result

    def up(self, recreate: bool = False) -> dict[str, Any]:
        self.up_recreate = recreate
        return self.result

    def stop(self) -> dict[str, Any]:
        return self.result

    def start(self) -> dict[str, Any]:
        return self.result

    def restart(self) -> dict[str, Any]:
        return self.result

    def down(self, remove_volumes: bool = False) -> dict[str, Any]:
        self.down_remove_volumes = remove_volumes
        return self.result

    def logs(self, tail: int = 100) -> dict[str, Any]:
        self.logs_tail = tail
        return self.result


def test_demo_db_help_lists_commands() -> None:
    result = CliRunner().invoke(app, ["demo-db", "--help"])

    assert result.exit_code == 0
    for command in (
        "status",
        "build",
        "up",
        "stop",
        "start",
        "restart",
        "down",
        "logs",
    ):
        assert command in result.output


def test_demo_db_status(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeDemoDbManager(
        {
            "ok": True,
            "ready": True,
            "docker_available": True,
            "compose_valid": True,
            "image": None,
            "container": None,
            "volume": None,
            "setup_done": None,
        }
    )
    monkeypatch.setattr("omp_yield.cli.DemoDbManager", lambda: fake)

    result = CliRunner().invoke(app, ["demo-db", "status"])

    assert result.exit_code == 0
    assert "ready" in result.output


def test_demo_db_error_exits_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeDemoDbManager(
        {"ok": False, "action": "build_failed", "error": "boom"}
    )
    monkeypatch.setattr("omp_yield.cli.DemoDbManager", lambda: fake)

    result = CliRunner().invoke(app, ["demo-db", "build"])

    assert result.exit_code == 1
    assert "boom" in result.output


def test_demo_db_build_force(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeDemoDbManager({"ok": True, "action": "built"})
    monkeypatch.setattr("omp_yield.cli.DemoDbManager", lambda: fake)

    result = CliRunner().invoke(app, ["demo-db", "build", "--force"])

    assert result.exit_code == 0
    assert fake.build_force is True


def test_demo_db_down_remove_volumes(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeDemoDbManager({"ok": True, "action": "down"})
    monkeypatch.setattr("omp_yield.cli.DemoDbManager", lambda: fake)

    result = CliRunner().invoke(app, ["demo-db", "down", "--remove-volumes"])

    assert result.exit_code == 0
    assert fake.down_remove_volumes is True


def test_demo_db_logs(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeDemoDbManager(
        {"ok": True, "lines": ["line one", "line two"], "line_count": 2}
    )
    monkeypatch.setattr("omp_yield.cli.DemoDbManager", lambda: fake)

    result = CliRunner().invoke(app, ["demo-db", "logs", "--tail", "5"])

    assert result.exit_code == 0
    assert "line one" in result.output
    assert fake.logs_tail == 5


def test_features_help() -> None:
    result = CliRunner().invoke(app, ["features", "--help"])

    assert result.exit_code == 0
    assert "modeling table" in result.output.lower()


def test_splits_help() -> None:
    result = CliRunner().invoke(app, ["splits", "--help"])

    assert result.exit_code == 0
    assert "split" in result.output.lower()
