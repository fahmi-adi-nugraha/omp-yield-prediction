# Phase 2 — Raw Extraction and Immutable Snapshots

Status: **complete**

## Snapshot

| Field | Value |
|---|---|
| Snapshot ID | `20261030T000000Z` |
| Source | `omp_ds_readonly@localhost:1433/omp_as_demo` |
| Tables | 28 |
| Rows | 140,004 |
| Parquet bytes | 4,591,906 |
| Snapshot directory | `data/raw/20261030T000000Z` (gitignored) |
| Manifest | `data/raw/20261030T000000Z/manifest.json` |
| Manifest checksum | `data/raw/20261030T000000Z/manifest.sha256` |
| Full report | `../../reports/02_extract_report.md` |

## What was extracted

- Core block-year panel and target: `OILPALM`
- Nutrient application/recommendation tables
- Harvest events, pest surveys, disease-control, and pesticide events
- Weather, stand, soil, bunch counts, forecast ABW, and crop budgets
- Planting, area, division/field hierarchy, and system lookup tables

The exact table list is in `config/extraction.yaml`. Each table was read with an
explicit column list derived from `INFORMATION_SCHEMA`; no `SELECT *` was used.
The selected and excluded columns are recorded per table in `manifest.json`.

## Excluded tables

| Table | Reason |
|---|---|
| `tbl_GIS_blocks` | Contains a SQL Server `geometry` column; not needed for Phase 2 yield modeling |
| `tbl_su_blocks` | Empty table |

## Verification

- The current snapshot records commit `ba043d0` with `Git dirty: False`.
- All 28 table row counts matched `COUNT_BIG(*)`.
- Every Parquet file has a SHA256 checksum in `manifest.json`.
- `manifest.sha256` matches the manifest contents.
- Re-running the extraction with the same snapshot ID and `--force` produced
  identical Parquet hashes for all 28 tables.
- `uv run omp-yield verify-snapshot data/raw/20261030T000000Z` reports
  `overall: ok`.

## Reproduce

```bash
uv run omp-yield extract \
  --snapshot-id 20261030T000000Z \
  --force \
  --report reports/02_extract_report.md

uv run omp-yield verify-snapshot data/raw/20261030T000000Z
```

## Notes

- `data/raw/` is gitignored, so snapshots remain local immutable inputs.
- The raw snapshot preserves the single 2026 `OILPALM` placeholder row and all
  2019–2025 rows. Filtering belongs to Phase 3.
- The extraction is built in a temporary directory and atomically renamed into
  place only after all tables and the manifest succeed.

## Next

Phase 3 is approved; see `../phase-3-cleaning/README.md` and
`../../reports/03_cleaning_report.html`. Phase 4 is next.
