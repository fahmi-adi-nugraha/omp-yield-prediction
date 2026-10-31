"""Command-line entry points for the OMP yield pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import polars as pl
import typer
from rich.console import Console
from rich.table import Table

from omp_yield import __version__
from omp_yield.config import Settings
from omp_yield.db import Database, OmpDatabaseError
from omp_yield.extract import (
    extract_snapshot,
    load_extraction_config,
    verify_snapshot,
    write_extraction_report,
)
from omp_yield.inventory import write_inventory_reports
from omp_yield.sql import UnsafeQueryError

console = Console()
app = typer.Typer(
    name="omp-yield",
    help="OMP oil palm yield prediction pipeline.",
    no_args_is_help=True,
)
db_app = typer.Typer(help="Read-only access to the OMP demo database.", no_args_is_help=True)
app.add_typer(db_app, name="db")


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"omp-yield {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the package version and exit.",
    ),
) -> None:
    """OMP oil palm yield prediction pipeline."""


def _print_frame(frame: pl.DataFrame, *, max_rows: int = 50, max_cols: int = 20) -> None:
    if frame.height == 0:
        console.print("[yellow]No rows returned.[/yellow]")
        return

    columns = frame.columns[:max_cols]
    table = Table(show_header=True, header_style="bold")
    for column in columns:
        table.add_column(str(column), overflow="fold")

    for row in frame.head(max_rows).select(columns).iter_rows():
        table.add_row(*["" if value is None else str(value) for value in row])

    console.print(table)
    if frame.height > max_rows:
        console.print(f"[dim]Showing {max_rows} of {frame.height} rows.[/dim]")
    if len(frame.columns) > max_cols:
        console.print(
            f"[dim]Showing {max_cols} of {len(frame.columns)} columns.[/dim]"
        )


def _json_output(frame: pl.DataFrame) -> None:
    console.print_json(json.dumps(json.loads(frame.write_json()), default=str))


def _handle_error(exc: Exception) -> None:
    console.print(f"[red]Error:[/red] {exc}")
    raise typer.Exit(code=1) from exc


@db_app.command("ping")
def db_ping() -> None:
    """Check connectivity and print server/database identity."""

    try:
        frame = Database(Settings()).ping()
    except (OmpDatabaseError, UnsafeQueryError, ValueError) as exc:
        _handle_error(exc)
        return
    _print_frame(frame)


@db_app.command("tables")
def db_tables(as_json: bool = typer.Option(False, "--json", help="Emit JSON.")) -> None:
    """List user tables in the configured database."""

    try:
        frame = Database(Settings()).tables()
    except (OmpDatabaseError, UnsafeQueryError, ValueError) as exc:
        _handle_error(exc)
        return
    if as_json:
        _json_output(frame)
    else:
        _print_frame(frame, max_rows=500, max_cols=5)


@db_app.command("schema")
def db_schema(
    table: str | None = typer.Option(None, "--table", "-t", help="Filter to one table."),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON."),
) -> None:
    """Show column metadata for the database or one table."""

    try:
        frame = Database(Settings()).schema(table=table)
    except (OmpDatabaseError, UnsafeQueryError, ValueError) as exc:
        _handle_error(exc)
        return
    if as_json:
        _json_output(frame)
    else:
        _print_frame(frame, max_rows=1000, max_cols=8)


@db_app.command("query")
def db_query(
    sql: str = typer.Argument(..., help="A single SELECT or WITH statement."),
    limit: int | None = typer.Option(
        None,
        "--limit",
        "-n",
        min=1,
        help="Maximum rows to return. Defaults to OMP_QUERY_ROW_LIMIT.",
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON."),
) -> None:
    """Run a read-only query and print the result."""

    try:
        frame = Database(Settings()).query(sql, limit=limit)
    except (OmpDatabaseError, UnsafeQueryError, ValueError) as exc:
        _handle_error(exc)
        return
    if as_json:
        _json_output(frame)
    else:
        _print_frame(frame)


@app.command("extract")
def extract(
    config: Annotated[
        Path,
        typer.Option("--config", help="Extraction YAML configuration."),
    ] = Path("config/extraction.yaml"),
    snapshot_id: Annotated[
        str | None,
        typer.Option("--snapshot-id", help="Optional deterministic snapshot ID."),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", help="Replace an existing snapshot directory."),
    ] = False,
    report: Annotated[
        Path,
        typer.Option("--report", help="Markdown extraction report path."),
    ] = Path("reports/02_extract_report.md"),
) -> None:
    """Extract configured tables into an immutable Parquet snapshot."""

    try:
        cfg = load_extraction_config(config)
        result = extract_snapshot(
            Database(Settings()),
            cfg,
            snapshot_id=snapshot_id,
            force=force,
        )
        report_path = write_extraction_report(result, report)
    except (
        OmpDatabaseError,
        UnsafeQueryError,
        ValueError,
        FileExistsError,
        RuntimeError,
    ) as exc:
        _handle_error(exc)
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("artifact")
    table.add_column("value")
    table.add_row("snapshot_id", result.snapshot_id)
    table.add_row("snapshot_dir", str(result.snapshot_dir))
    table.add_row("tables", str(result.manifest["summary"]["table_count"]))
    table.add_row("rows", f"{result.manifest['summary']['row_count']:,}")
    table.add_row("manifest_sha256", result.manifest_sha256)
    table.add_row("report", str(report_path))
    console.print(table)


@app.command("verify-snapshot")
def verify_snapshot_command(
    snapshot_dir: Annotated[
        Path,
        typer.Argument(help="Snapshot directory containing manifest.json."),
    ],
) -> None:
    """Re-verify a raw snapshot's manifest and Parquet files."""

    try:
        result = verify_snapshot(snapshot_dir)
    except (FileNotFoundError, ValueError) as exc:
        _handle_error(exc)
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("table")
    table.add_column("rows")
    table.add_column("sha256")
    table.add_column("columns")
    table.add_column("ok")
    for row in result["tables"]:
        table.add_row(
            row["table"],
            str(row["row_count"]),
            "ok" if row["sha256_ok"] else "FAIL",
            "ok" if row["columns_ok"] else "FAIL",
            "ok" if row["ok"] else "FAIL",
        )
    console.print(table)
    console.print(
        f"Manifest: {'ok' if result['manifest_ok'] else 'FAIL'}; "
        f"overall: {'ok' if result['all_ok'] else 'FAIL'}"
    )
    if not result["all_ok"]:
        raise typer.Exit(code=1)


@app.command("inventory")
def inventory(
    docs_dir: Annotated[
        Path,
        typer.Option("--docs-dir", help="Root directory for generated documentation."),
    ] = Path("docs"),
    data_dir: Annotated[
        Path,
        typer.Option("--data-dir", help="Root directory for generated data artifacts."),
    ] = Path("data"),
    reports_dir: Annotated[
        Path,
        typer.Option("--reports-dir", help="Directory for generated report artifacts."),
    ] = Path("reports"),
) -> None:
    """Generate the Phase 1 database inventory and data dictionary."""

    try:
        artifacts = write_inventory_reports(
            Database(Settings()),
            docs_dir,
            data_dir,
            reports_dir,
        )
    except (OmpDatabaseError, UnsafeQueryError, ValueError) as exc:
        _handle_error(exc)
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("artifact")
    table.add_column("path")
    for name, path in artifacts.items():
        table.add_row(name, str(path))
    console.print(table)


@app.command("info")
def info() -> None:
    """Print non-secret configuration information."""

    try:
        settings = Settings()
    except ValueError as exc:
        _handle_error(exc)
        return
    payload: dict[str, Any] = {
        "target": settings.safe_target,
        "encrypt": settings.db_encrypt,
        "trust_server_certificate": settings.db_trust_server_certificate,
        "query_row_limit": settings.query_row_limit,
    }
    table = Table(show_header=True, header_style="bold")
    table.add_column("setting")
    table.add_column("value")
    for key, value in payload.items():
        table.add_row(key, str(value))
    console.print(table)


if __name__ == "__main__":
    app()
