# Phase 2 — Raw Extraction and Immutable Snapshots

Status: **complete**

## Overview

Extract the candidate tables from the database into immutable Parquet snapshots
with explicit columns, row-count verification, checksums, and a manifest.

## Goals and deliverables

- `config/extraction.yaml` — 28-table allowlist and exclusions.
- `src/omp_yield/extract.py` — extractor, verifier, report writer.
- CLI `omp-yield extract` and `omp-yield verify-snapshot`.
- Snapshot `data/raw/20261030T000000Z/` (gitignored).
- `manifest.json`, `manifest.sha256`, one Parquet per table.
- `reports/02_extract_report.md` and `docs/phase-2-extraction/README.md`.

## Technical details

- Each table is read with an explicit column list derived from
  `INFORMATION_SCHEMA`; no `SELECT *`.
- Unsupported SQL types such as `geometry` are excluded. `tbl_GIS_blocks` is
  excluded entirely; `tbl_su_blocks` is empty.
- Tables with known business keys are ordered deterministically before writing.
- Parquet uses `zstd` compression and per-file SHA256.
- Row count is verified against `COUNT_BIG(*)`.
- Snapshot is written to a temp directory and atomically renamed after all
  tables and the manifest succeed.
- Manifest records source, login, server version, git commit/dirty state,
  config hash, queries, columns, row counts, and checksums.
- Current snapshot: 28 tables, 140,004 rows, 4,591,906 bytes.

## Locations

- `config/extraction.yaml`
- `src/omp_yield/extract.py`
- `data/raw/20261030T000000Z/` (gitignored)
- `reports/02_extract_report.md`
- `docs/phase-2-extraction/README.md`
- `tests/test_extract.py`, `tests/test_db_integration.py`

## Verification

```bash
uv run omp-yield extract   --snapshot-id 20261030T000000Z   --force   --report reports/02_extract_report.md
uv run omp-yield verify-snapshot data/raw/20261030T000000Z
uv run pytest
OMP_RUN_INTEGRATION=1 uv run pytest tests/test_db_integration.py
```

Expected: `Manifest: ok; overall: ok`; re-extraction produces identical table
hashes.

## Next

Phase 3 — cleaning, leakage audit, and draft feature decisions.
