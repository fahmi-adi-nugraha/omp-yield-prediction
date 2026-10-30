from __future__ import annotations

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
