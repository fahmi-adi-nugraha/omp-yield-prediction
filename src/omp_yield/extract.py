"""Phase 2 immutable raw-data extraction and snapshot manifests."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

import polars as pl
import yaml

from omp_yield.db import Database
from omp_yield.inventory import KEY_SPECS, column_inventory, markdown_table, quote_ident

_UNSUPPORTED_TYPES = {
    "geometry",
    "geography",
    "image",
    "varbinary",
    "binary",
    "xml",
    "sql_variant",
    "text",
    "ntext",
    "rowversion",
    "timestamp",
    "hierarchyid",
}

_SNAPSHOT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_KEY_COLUMNS = {spec.table.lower(): spec.columns for spec in KEY_SPECS}


@dataclass(frozen=True)
class ExtractionConfig:
    """Configuration for one extraction run."""

    tables: tuple[str, ...]
    output_dir: Path
    compression: str
    excluded_tables: tuple[dict[str, str], ...]
    config_path: Path = Path("config/extraction.yaml")
    config_sha256: str = ""


@dataclass(frozen=True)
class ExtractionResult:
    """Result of a completed snapshot extraction."""

    snapshot_id: str
    snapshot_dir: Path
    manifest: dict[str, Any]
    manifest_sha256: str


def load_extraction_config(path: Path) -> ExtractionConfig:
    """Load and validate a YAML extraction configuration."""

    if not path.is_file():
        raise FileNotFoundError(f"Extraction config not found: {path}")

    raw = path.read_bytes()
    data = yaml.safe_load(raw) or {}
    tables = tuple(str(t) for t in data.get("tables", []))
    if not tables:
        raise ValueError(f"No tables configured in {path}")

    duplicate = len(tables) != len(set(tables))
    if duplicate:
        raise ValueError(f"Duplicate table names in {path}")

    compression = str(data.get("compression", "zstd"))
    if compression not in {"zstd", "snappy", "gzip", "lz4", "brotli", "uncompressed"}:
        raise ValueError(f"Unsupported Parquet compression: {compression}")

    excluded = tuple(data.get("excluded_tables", []))
    return ExtractionConfig(
        tables=tables,
        output_dir=Path(data.get("output_dir", "data/raw")),
        compression=compression,
        excluded_tables=excluded,
        config_path=path,
        config_sha256=hashlib.sha256(raw).hexdigest(),
    )


def validate_snapshot_id(snapshot_id: str) -> str:
    """Reject unsafe snapshot IDs before creating directories."""

    if not snapshot_id or not _SNAPSHOT_ID_RE.fullmatch(snapshot_id):
        raise ValueError(
            "snapshot_id must start with an alphanumeric character and contain "
            "only letters, digits, dots, underscores, or hyphens."
        )
    return snapshot_id


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_commit() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() or None


def _git_dirty() -> bool | None:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return bool(result.stdout.strip())


def _select_columns(
    columns: pl.DataFrame, table: str
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]], str]:
    matches = columns.filter(
        pl.col("table_name").str.to_lowercase() == table.lower()
    )
    if matches.height == 0:
        raise ValueError(f"Table not found in INFORMATION_SCHEMA: {table}")

    actual_tables = matches["table_name"].unique().to_list()
    if len(actual_tables) != 1:
        raise ValueError(f"Ambiguous table name in INFORMATION_SCHEMA: {table}")
    actual_table = str(actual_tables[0])

    unsupported = pl.col("data_type").str.to_lowercase().is_in(sorted(_UNSUPPORTED_TYPES))
    supported = matches.filter(~unsupported)
    excluded = matches.filter(unsupported)

    if supported.height == 0:
        raise ValueError(f"Table has no supported columns: {actual_table}")

    selected = supported.select(
        "ordinal",
        "column_name",
        "data_type",
        "is_nullable",
        "char_max_length",
        "numeric_precision",
        "numeric_scale",
        "datetime_precision",
    ).to_dicts()
    excluded_columns = excluded.select("column_name", "data_type").to_dicts()
    select_list = ", ".join(
        quote_ident(str(row["column_name"])) for row in selected
    )
    return actual_table, selected, excluded_columns, select_list


def _table_query(table: str, select_list: str) -> str:
    order_columns = _KEY_COLUMNS.get(table.lower(), ())
    order_by = ""
    if order_columns:
        order_by = " ORDER BY " + ", ".join(quote_ident(c) for c in order_columns)
    return f"SELECT {select_list} FROM [dbo].{quote_ident(table)}{order_by}"


def _source_info(db: Database) -> dict[str, Any]:
    row = db.ping().row(0, named=True)
    return {
        "target": db.settings.safe_target,
        "database": row["database_name"],
        "login": row["login_name"],
        "server_version": row["server_version"],
    }


def extract_snapshot(
    db: Database,
    config: ExtractionConfig,
    *,
    snapshot_id: str | None = None,
    force: bool = False,
) -> ExtractionResult:
    """Extract configured tables to an immutable Parquet snapshot.

    The snapshot is built in a temporary directory and renamed into place only
    after all tables and the manifest have been written. Reusing an existing
    snapshot ID requires ``force=True``.
    """

    snapshot_id = validate_snapshot_id(
        snapshot_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    )
    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot_dir = output_dir / snapshot_id
    temp_dir = output_dir / f".{snapshot_id}.tmp"
    backup_dir = output_dir / f".{snapshot_id}.old"

    if snapshot_dir.exists() and not force:
        raise FileExistsError(
            f"Snapshot already exists: {snapshot_dir}. Use --force to replace it."
        )
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    temp_dir.mkdir(parents=True)

    columns = column_inventory(db)
    table_entries: list[dict[str, Any]] = []
    try:
        for table in config.tables:
            actual_table, selected_columns, excluded_columns, select_list = _select_columns(
                columns, table
            )
            query = _table_query(actual_table, select_list)
            query_sha256 = hashlib.sha256(query.encode("utf-8")).hexdigest()
            frame = db.read_frame(query)
            source_count = int(
                db.read_frame(
                    f"SELECT COUNT_BIG(*) AS row_count FROM [dbo].{quote_ident(actual_table)}"
                ).item()
            )
            if frame.height != source_count:
                raise RuntimeError(
                    f"Row-count mismatch for {actual_table}: "
                    f"file={frame.height}, source={source_count}"
                )

            parquet_path = temp_dir / f"{actual_table}.parquet"
            frame.write_parquet(
                parquet_path,
                compression=cast(
                    Literal["lz4", "uncompressed", "snappy", "gzip", "brotli", "zstd"],
                    config.compression,
                ),
                statistics=True,
            )
            parquet_sha256 = _sha256_file(parquet_path)
            table_entries.append(
                {
                    "table": actual_table,
                    "query": query,
                    "query_sha256": query_sha256,
                    "row_count_source": source_count,
                    "row_count_file": frame.height,
                    "verified": True,
                    "column_count": frame.width,
                    "columns": selected_columns,
                    "excluded_columns": excluded_columns,
                    "parquet_file": parquet_path.name,
                    "parquet_bytes": parquet_path.stat().st_size,
                    "parquet_sha256": parquet_sha256,
                }
            )

        manifest: dict[str, Any] = {
            "snapshot_id": snapshot_id,
            "extracted_at": datetime.now(UTC).isoformat(),
            "source": _source_info(db),
            "git_commit": _git_commit(),
            "git_dirty": _git_dirty(),
            "config_path": str(config.config_path),
            "config_sha256": config.config_sha256,
            "snapshot_dir": str(snapshot_dir),
            "compression": config.compression,
            "excluded_tables": list(config.excluded_tables),
            "tables": table_entries,
            "summary": {
                "table_count": len(table_entries),
                "row_count": sum(t["row_count_file"] for t in table_entries),
                "total_bytes": sum(t["parquet_bytes"] for t in table_entries),
            },
        }
        manifest_text = json.dumps(manifest, indent=2, sort_keys=True, default=str)
        manifest_path = temp_dir / "manifest.json"
        manifest_path.write_text(manifest_text + "\n")
        manifest_sha256 = hashlib.sha256((manifest_text + "\n").encode("utf-8")).hexdigest()
        (temp_dir / "manifest.sha256").write_text(manifest_sha256 + "\n")

        if snapshot_dir.exists():
            snapshot_dir.rename(backup_dir)
        try:
            temp_dir.rename(snapshot_dir)
        except Exception:
            if backup_dir.exists():
                backup_dir.rename(snapshot_dir)
            raise
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
    except Exception:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        raise

    return ExtractionResult(
        snapshot_id=snapshot_id,
        snapshot_dir=snapshot_dir,
        manifest=manifest,
        manifest_sha256=manifest_sha256,
    )


def verify_snapshot(snapshot_dir: Path) -> dict[str, Any]:
    """Re-verify a snapshot's manifest, checksums, row counts, and columns."""

    manifest_path = snapshot_dir / "manifest.json"
    checksum_path = snapshot_dir / "manifest.sha256"
    if not manifest_path.is_file() or not checksum_path.is_file():
        raise FileNotFoundError(f"Snapshot manifest not found under {snapshot_dir}")

    manifest_text = manifest_path.read_text()
    manifest = json.loads(manifest_text)
    expected_manifest_sha = checksum_path.read_text().strip()
    actual_manifest_sha = hashlib.sha256(manifest_text.encode("utf-8")).hexdigest()

    table_results: list[dict[str, Any]] = []
    for entry in manifest["tables"]:
        path = snapshot_dir / entry["parquet_file"]
        exists = path.is_file()
        actual_sha = _sha256_file(path) if exists else ""
        frame = pl.read_parquet(path) if exists else None
        row_count = frame.height if frame is not None else -1
        columns = frame.columns if frame is not None else []
        expected_columns = [c["column_name"] for c in entry["columns"]]
        checks = {
            "file_exists": exists,
            "sha256_ok": actual_sha == entry["parquet_sha256"],
            "row_count_ok": row_count == entry["row_count_file"],
            "columns_ok": columns == expected_columns,
        }
        table_results.append(
            {
                "table": entry["table"],
                "row_count": row_count,
                "expected_rows": entry["row_count_file"],
                **checks,
                "ok": all(checks.values()),
            }
        )

    return {
        "snapshot_dir": str(snapshot_dir),
        "manifest_sha256_expected": expected_manifest_sha,
        "manifest_sha256_actual": actual_manifest_sha,
        "manifest_ok": expected_manifest_sha == actual_manifest_sha,
        "tables": table_results,
        "all_ok": expected_manifest_sha == actual_manifest_sha
        and all(t["ok"] for t in table_results),
    }


def write_extraction_report(
    result: ExtractionResult,
    report_path: Path,
) -> Path:
    """Write a Markdown report for an extraction snapshot."""

    report_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = result.manifest
    rows = pl.DataFrame(
        [
            {
                "table": entry["table"],
                "rows": entry["row_count_file"],
                "columns": entry["column_count"],
                "bytes": entry["parquet_bytes"],
                "verified": entry["verified"],
                "query_sha256": entry["query_sha256"][:12],
                "parquet_sha256": entry["parquet_sha256"][:12],
            }
            for entry in manifest["tables"]
        ]
    ).sort("table")

    excluded_rows = pl.DataFrame(manifest.get("excluded_tables", []))
    excluded_md = (
        markdown_table(excluded_rows)
        if excluded_rows.height
        else "No tables excluded by configuration."
    )

    report = f"""# Phase 2 — Raw Extraction and Snapshot

Status: **complete**

## Snapshot

| Field | Value |
|---|---|
| Snapshot ID | `{manifest["snapshot_id"]}` |
| Extracted at | `{manifest["extracted_at"]}` |
| Snapshot directory | `{manifest["snapshot_dir"]}` |
| Source | `{manifest["source"]["target"]}` |
| Database | `{manifest["source"]["database"]}` |
| Login | `{manifest["source"]["login"]}` |
| Git commit | `{manifest["git_commit"] or "unavailable"}` |
| Git dirty | `{manifest.get("git_dirty")}` |
| Config | `{manifest["config_path"]}` |
| Config SHA256 | `{manifest["config_sha256"]}` |
| Manifest SHA256 | `{result.manifest_sha256}` |

## Summary

- Tables extracted: **{manifest["summary"]["table_count"]}**
- Rows extracted: **{manifest["summary"]["row_count"]:,}**
- Parquet bytes: **{manifest["summary"]["total_bytes"]:,}**
- All table row counts verified against `COUNT_BIG(*)`: **yes**
- Manifest: `{manifest["snapshot_dir"]}/manifest.json`
- Manifest checksum: `{manifest["snapshot_dir"]}/manifest.sha256`

## Tables

{markdown_table(rows)}

## Excluded tables

{excluded_md}

## Verification

- Every Parquet file was written with the configured compression
  (`{manifest["compression"]}`).
- Each table was read with an explicit column list; no `SELECT *`.
- `row_count_file` equals `row_count_source` for every table.
- Each Parquet file has a SHA256 checksum in `manifest.json`.
- The snapshot was written to a temporary directory and renamed into place only
  after all tables and the manifest succeeded.

## Reproduce

```bash
uv run omp-yield extract --snapshot-id {manifest["snapshot_id"]} --force
```

## Notes

- `data/raw/` is gitignored. Snapshots are local immutable inputs for later
  phases.
- If `Git dirty` is `True`, the code that produced this snapshot was not
  committed. Commit the pipeline before freezing a production snapshot.
- The 2026 `OILPALM` placeholder row and all 2019–2025 rows are preserved in the
  raw snapshot. Filtering belongs in Phase 3.
- `tbl_GIS_blocks` is excluded because it contains a SQL Server `geometry`
  column; it is not needed for yield modeling.
- `tbl_su_blocks` is excluded because it is empty.
"""
    report_path.write_text(report)
    return report_path
