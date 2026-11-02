from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from omp_yield import mcp_server
from omp_yield.demo_db import CommandResult, DemoDbManager, DemoDbSettings

_TOOL_NAMES = (
    "db_ping",
    "db_tables",
    "db_schema",
    "db_query",
    "demo_db_status",
    "demo_db_logs",
    "demo_db_build",
    "demo_db_up",
    "demo_db_stop",
    "demo_db_start",
    "demo_db_restart",
    "demo_db_down",
)


def test_mcp_tools_are_callable() -> None:
    for name in _TOOL_NAMES:
        assert callable(getattr(mcp_server, name))


def test_mcp_tools_are_registered() -> None:
    tools = asyncio.run(mcp_server.mcp.list_tools())
    names = {tool.name for tool in tools}

    assert set(_TOOL_NAMES) <= names


def test_lifecycle_tool_annotations() -> None:
    tools = {tool.name: tool for tool in asyncio.run(mcp_server.mcp.list_tools())}

    status = tools["demo_db_status"].annotations
    logs = tools["demo_db_logs"].annotations
    down = tools["demo_db_down"].annotations

    assert status is not None
    assert status.read_only_hint is True
    assert status.destructive_hint is False
    assert status.idempotent_hint is True

    assert logs is not None
    assert logs.read_only_hint is True

    assert down is not None
    assert down.read_only_hint is False
    assert down.destructive_hint is True
    assert down.idempotent_hint is True


def test_mcp_exception_becomes_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class RaisingManager:
        def status(self) -> dict[str, Any]:
            raise RuntimeError("boom")

    monkeypatch.setattr(mcp_server, "_demo_db", RaisingManager())

    result = asyncio.run(mcp_server.demo_db_status())

    assert result == {"ok": False, "error": "boom"}


def test_mcp_mutations_disabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    settings = DemoDbSettings(build_dir=tmp_path, allow_mutations=False)
    manager = DemoDbManager(settings=settings)
    monkeypatch.setattr(mcp_server, "_demo_db", manager)

    result = asyncio.run(mcp_server.demo_db_build())

    assert result["ok"] is False
    assert "disabled" in str(result["error"])


class _LogsRunner:
    def __call__(
        self,
        command: Sequence[str],
        *,
        timeout_seconds: float,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
    ) -> CommandResult:
        return CommandResult(
            command=tuple(command),
            returncode=0,
            stdout="super-secret\n",
            stderr="",
            duration_seconds=0.01,
        )


def test_mcp_logs_redacts_secrets(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("MSSQL_SA_PASSWORD", "super-secret")
    (tmp_path / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    settings = DemoDbSettings(build_dir=tmp_path)
    manager = DemoDbManager(settings=settings, runner=_LogsRunner())
    monkeypatch.setattr(mcp_server, "_demo_db", manager)

    result = asyncio.run(mcp_server.demo_db_logs(tail=5))

    assert "super-secret" not in str(result)
    assert "***" in "\n".join(result["lines"])
