"""Command-line entry points for the OMP yield pipeline."""

from __future__ import annotations

import json
from typing import Any

import polars as pl
import typer
from rich.console import Console
from rich.table import Table

from omp_yield import __version__
from omp_yield.config import Settings
from omp_yield.db import Database, OmpDatabaseError
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
