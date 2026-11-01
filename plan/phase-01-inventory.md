# Phase 1 — Database Inventory and Data Dictionary

Status: **complete**

## Overview

Understand the database before transforming it: table grains, row counts,
columns, keys, date ranges, candidate joins, growth periods, estate/division
hierarchy, and an OILPALM data dictionary.

## Goals and deliverables

- `src/omp_yield/inventory.py` with table/column/key/foreign-key/date-range/
  join-coverage/hierarchy/dictionary queries.
- `uv run omp-yield inventory`.
- `notebooks/01_db_inventory.py` — Marimo interactive inventory.
- `docs/phase-1-inventory/README.md`, `db_inventory.md`, `data_dictionary.md`,
  `erd.md`.
- `data/phase-1-inventory/*.csv` — generated inventory tables.
- `reports/01_db_inventory.html` — exported Marimo report.

## Technical details

- Uses `INFORMATION_SCHEMA`, `sys.tables`, `sys.columns`, `sys.partitions`,
  `sys.key_constraints`, and `sys.foreign_keys`.
- Table row counts use `sys.partitions` for speed; exact `COUNT_BIG(*)` is used
  later during extraction.
- Join coverage measures distinct source keys against OILPALM.
- Growth definitions come from `tbl_sys_growthPeriods`:
  `IGP` 0–2, `SAYP` 3–7, `PYP` 8–15, `DYP` 16–25, `LDYP` 26+.
- The data dictionary combines `tbl_SYS_fldDefs` and `tbl_sys_UDE_fields`
  descriptions with null counts, distinct counts, preliminary roles, and
  availability timing.
- Key finding: OILPALM is unique on `(NAME, UNIT, BLOCK, YEAR)`; weather joins
  through `ID_WeatherStation` to `R_UNIT`, not `UNIT`.

## Locations

- `src/omp_yield/inventory.py`
- `notebooks/01_db_inventory.py`
- `docs/phase-1-inventory/`
- `data/phase-1-inventory/`
- `reports/01_db_inventory.html`

## Verification

```bash
uv run omp-yield inventory
uv run --with marimo marimo export html notebooks/01_db_inventory.py   -o reports/01_db_inventory.html
uv run pytest
uv run ruff check .
uv run mypy src tests
```

## Next

Phase 2 — extract immutable raw snapshots.
