# Documentation Index

Phase documentation, generated inventories, and reproducible setup notes for the
OMP yield pipeline.

## Phase directories

| Directory | Contents |
|---|---|
| `phase-minus-1-harness/` | Agent/CLI/MCP harness, verification, and known limitations |
| `phase-0-access/` | Read-only account summary and bootstrap SQL |
| `phase-1-inventory/` | Database inventory, data dictionary, ERD, and CSV artifacts |
| `phase-2-extraction/` | Raw extraction snapshot summary and reproducibility notes |

## Phase -1

- `phase-minus-1-harness/README.md` — harness report and limitations

## Phase 0

- `phase-0-access/README.md` — access summary
- `phase-0-access/create_readonly_user.sql` — idempotent bootstrap
- `../reports/00_access.md` — full access report

## Phase 1

- `phase-1-inventory/README.md` — phase summary and key findings
- `phase-1-inventory/db_inventory.md` — detailed table/join inventory
- `phase-1-inventory/data_dictionary.md` — readable OILPALM dictionary
- `phase-1-inventory/erd.md` — core ERD and join map
- `phase-1-inventory/data/schema_tables.csv`
- `phase-1-inventory/data/schema_columns.csv`
- `phase-1-inventory/data/key_constraints.csv`
- `phase-1-inventory/data/foreign_keys.csv`
- `phase-1-inventory/data/key_uniqueness.csv`
- `phase-1-inventory/data/date_ranges.csv`
- `phase-1-inventory/data/join_coverage.csv`
- `phase-1-inventory/data/oilpalm_dictionary.csv`
- `../reports/01_db_inventory.html` — exported Marimo inventory notebook

## Phase 2

- `phase-2-extraction/README.md` — snapshot summary and reproducibility
- `../reports/02_extract_report.md` — full extraction report
- `config/extraction.yaml` — extraction table configuration

## Current status

- Phase -1 — complete
- Phase 0 — complete
- Phase 1 — complete
- Phase 2 — complete
- Phase 3 — next: cleaning, profiling, leakage audit, and feature decisions

## Credential files

The pipeline resolves credentials in this order:

1. `OMP_ENV_FILE`
2. project `.env`
3. `~/.config/omp-yield/env`
4. `docker-build/.env` (local demo fallback only)

The recommended local secret location is `~/.config/omp-yield/env`, outside the
Syncthing-synced project tree.
