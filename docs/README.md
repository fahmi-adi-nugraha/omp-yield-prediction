# Documentation Index

Phase documentation, generated inventories, and reproducible setup notes for the
OMP yield pipeline.

Implementation roadmap: `../plan/README.md`.

## Phase directories

| Directory | Contents |
|---|---|
| `phase-minus-1-harness/` | Agent/CLI/MCP harness, verification, and known limitations |
| `phase-0-access/` | Read-only account summary and bootstrap SQL |
| `phase-1-inventory/` | Database inventory, data dictionary, ERD, and CSV artifacts |
| `phase-2-extraction/` | Raw extraction snapshot summary and reproducibility notes |
| `phase-3-cleaning/` | Cleaning, leakage, feature decisions, and interim data summary |
| `phase-4-feature-engineering/` | Modeling table, transforms, feature schema, and diagnostics |
| `phase-5-splits-contracts/` | Evaluation splits, data contract, metrics, and baselines |

## Phase -1

- `phase-minus-1-harness/README.md` — harness report and limitations

## Phase 0

- `phase-0-access/README.md` — access summary
- `phase-0-access/create_readonly_user.sql` — idempotent bootstrap
- `../reports/00_access.md` — full access report

## Phase 1

Phase 1 CSV artifacts live under `data/phase-1-inventory/`.

- `phase-1-inventory/README.md` — phase summary and key findings
- `phase-1-inventory/db_inventory.md` — detailed table/join inventory
- `phase-1-inventory/data_dictionary.md` — readable OILPALM dictionary
- `phase-1-inventory/erd.md` — core ERD and join map
- `../data/phase-1-inventory/schema_tables.csv`
- `../data/phase-1-inventory/schema_columns.csv`
- `../data/phase-1-inventory/key_constraints.csv`
- `../data/phase-1-inventory/foreign_keys.csv`
- `../data/phase-1-inventory/key_uniqueness.csv`
- `../data/phase-1-inventory/date_ranges.csv`
- `../data/phase-1-inventory/join_coverage.csv`
- `../data/phase-1-inventory/oilpalm_dictionary.csv`
- `../reports/01_db_inventory.html` — exported Marimo inventory notebook

## Phase 2

- `phase-2-extraction/README.md` — snapshot summary and reproducibility
- `../reports/02_extract_report.md` — full extraction report
- `config/extraction.yaml` — extraction table configuration

## Phase 3

Phase 3 data artifacts live under `data/phase-3-cleaning/`; interim Parquet
files live under `data/interim/phase-3/`.

- `phase-3-cleaning/README.md` — cleaning summary and approval checklist
- `phase-3-cleaning/cleaning_report.md` — detailed cleaning/leakage report
- `../config/features.yaml` — approved feature decisions
- `../config/management_levers.yaml` — approved management levers
- `../reports/03_cleaning_report.html` — interactive Marimo cleaning notebook

## Phase 4

Phase 4 data artifacts live under `data/processed/`; the report is generated.

- `phase-4-feature-engineering/README.md` — modeling-table and transform summary
- `phase-4-feature-engineering/feature_engineering_summary.md` — full feature and derivation reference
- `../config/transforms.yaml` — approved cutoff, transform, and encoding parameters
- `../data/processed/modeling_table.parquet` — block-year modeling table
- `../data/processed/feature_schema.csv` — feature metadata and cutoff membership
- `../reports/04_feature_engineering.html` — feature-engineering and ablation report

## Phase 5

- `phase-5-splits-contracts/README.md` — split, contract, and evaluation protocol
- `data_contract.md` — generated data-contract reference
- `../config/evaluation.yaml` — approved split, metric, baseline, and contract rules
- `../src/omp_yield/splits.py` — temporal, grouped, CV, and rolling-origin splitters
- `../data/processed/splits.json` — generated train/validation/test membership
- `../data/processed/contract_report.csv` — generated contract check results

## Current status

- Phase -1 — complete
- Phase 0 — complete
- Phase 1 — complete
- Phase 2 — complete
- Phase 3 — approved
- Phase 4 — complete
- Phase 5 — complete
- Phase 6 — next

## Credential files

The pipeline resolves credentials in this order:

1. `OMP_ENV_FILE`
2. project `.env`
3. `~/.config/omp-yield/env`
4. `docker-build/.env` (local demo fallback only)

The recommended local secret location is `~/.config/omp-yield/env`, outside the
Syncthing-synced project tree.
