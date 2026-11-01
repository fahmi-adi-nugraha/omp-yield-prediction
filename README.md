# OMP Yield Prediction

A repeatable data science pipeline for OMP oil palm yield prediction and
multi-year yield forecasting. The project covers database access, immutable raw
extraction, data cleaning, feature engineering, model training and validation,
what-if analysis, and ONNX export.

The Python pipeline produces the model artifacts. A separate Go REST API loads
the exported ONNX models for inference.

## Start here — LLMs and new contributors

This project is documented as a phase-based plan in `plan/`. If you have blank
context, read `plan/README.md` end-to-end before changing code. Then read the
document for the current phase and the next phase, inspect the referenced code,
configs, tests, and reports, and respect every approval gate. The plan is the
source of truth for phase status, scope, deliverables, technical decisions, and
artifact locations.

Current phase document: `plan/phase-03-cleaning.md`

Next phase document: `plan/phase-04-feature-engineering.md`

**Current phase:** Phase 3 approved — feature and management-lever decisions
approved. Next: Phase 4 — feature engineering and the final modeling table.

## What this project builds

The project develops two machine learning models:

1. **Crop yield prediction model**
   - Predicts block-year fresh fruit bunch yield, `Y_TOTAL_ton`, in metric tons.
   - Trained on mature blocks: `Growth_Period IN ('SAYP', 'PYP', 'DYP')`.
   - Supports two information cutoffs:
     - `pre_season` — prior-year data only
     - `mid_season` — current-year data only up to a configurable cutoff
   - Supports what-if analysis over **management levers only**, such as nutrient
     application rates, pruning, harvester access, harvest interval, and
     pest/disease control. Weather, soil, age, stand, leaf analysis, pest
     pressure, and prior yield are read-only context features.

2. **Crop yield forecasting model**
   - Produces estate-level multi-year forecasts, with division/block detail.
   - Default horizon: 3 years. A 5-year horizon is an experimental extension.
   - Uses a hierarchical approach: train on the mature block panel, aggregate
     through `UNIT` to `NAME`, and report estate totals.
   - Supports scenario-based forecasts driven by management levers and weather
     assumptions, plus an unconditional baseline.
   - Reports prediction intervals and widening uncertainty at longer horizons.

## Training data

The source is the company demo SQL Server database `omp_as_demo` in the
`omp-as-demo-db` container. The pipeline connects through the least-privilege
account `omp_ds_readonly`.

The main table is `OILPALM`, a block-year panel containing:

- Estate, division, block, and year keys
- Static site and planting attributes
- Palm stand and growth-period context
- Leaf and soil analysis
- Annual yield and harvest-derived columns
- Weather-station linkage

Supporting tables provide nutrient applications and recommendations, harvest
events, pest and disease surveys, weather and water balance, palm census and
stand projections, soil analysis, bunch counts, crop budgets, and planting
records.

Current data scope:

| Item | Value |
|---|---|
| Usable years | 2019–2025 |
| 2026 rows | 1 placeholder row, excluded from modeling |
| Blocks | 553 unique block codes |
| Divisions | 9 |
| Estates | 1 in the demo |
| Raw snapshot | `data/raw/20261030T000000Z` |
| Snapshot contents | 28 tables, 140,004 rows |
| Snapshot provenance | Manifest, per-table SHA256, and `manifest.sha256` |

`data/raw/` is gitignored. Phase 2 snapshots are immutable local inputs with
row-count and checksum verification. See
`docs/phase-2-extraction/README.md` and `reports/02_extract_report.md`.

Data directory layout:

```text
data/
  db-json-exports/     # legacy JSON exports; gitignored
  phase-1-inventory/   # generated inventory CSVs
  phase-3-cleaning/    # cleaning, leakage, and feature-decision tables
  raw/                 # immutable extraction snapshots; gitignored
  interim/             # cleaned/intermediate data; gitignored
  processed/           # modeling tables; gitignored
```

## Data cleaning and feature preparation

The planned and partially implemented pipeline uses:

### Cleaning

- Key, type, date, category, and blank-value normalization
- Exact and business-key duplicate checks
- Missingness analysis by year and division
- Constant/near-constant column removal
- Outlier detection with domain bounds, not automatic deletion
- Consistency checks across monthly/annual yield, area, stand, tree age, and
  harvest tables
- Mature-block filtering and exclusion of the 2026 placeholder
- Explicit flagging of known anomalies such as `204D` 2025 and `124H`

### Leakage control

All current-year target-derived `Y_*` columns are excluded from features,
including `Y_TH`, `Y_KGB`, monthly yield totals, `Y_TH_GAP`,
`Y_GAP_PERCENT`, and `Y_per_manday`. Ambiguous fields such as `Y_TH_POT` and
`MarkerYield` require explicit approval.

Every feature carries an `available_at` value (`pre_season`, `mid_season`, or
`post_season`) and is validated against the selected cutoff.

### Feature selection

- Remove identifiers, constants, and target leakage
- Univariate association, mutual information, VIF, permutation importance, and
  group ablation
- Preserve management levers even when their marginal predictive importance is
  low, because they are the what-if controls

### Feature engineering

Planned transformations include:

- Lagged and rolling yield, harvest, weather, nutrient, and pest features
- Weather anomalies, dry-month counts, water deficit, and seasonal rainfall
- Nutrient application rates, balances, and recommendation gaps
- Stand, mature fraction, tree age, and growth-period features
- Leaf and soil nutrient ratios
- Harvest interval, rounds, losses, and bunch-weight history
- Estate/division aggregates built only from prior or cutoff-safe data

Phase 3 is approved. The feature and management-lever configs are frozen for
Phase 4, which builds the final modeling table and transforms.

## Proposed models and training

### Yield prediction

- Primary candidate: `HistGradientBoostingRegressor`
- Baselines: Ridge/ElasticNet
- Benchmark: Random Forest / ExtraTrees
- Optional challenger: LightGBM if cross-validated gain justifies the dependency
- Separate models for `pre_season` and `mid_season`
- Time-aware validation, grouped by block, with a chronological holdout
- Random search over learning rate, tree complexity, leaf size, regularization,
  and iteration count
- Metrics: RMSE, MAE, MAPE/sMAPE, R², bias, and error by year/division/age band

### Forecasting

- Hierarchical block-panel model aggregated to estate level
- Direct multi-horizon models rather than recursive one-step forecasting
- Scenario-conditional and unconditional variants
- Rolling-origin backtests and estate-level error reporting
- Metrics: RMSE, MAE, MAPE, MASE, bias, and prediction-interval coverage
- Baselines: last-year yield, 3-year average, linear trend, and company budget

Training runs log parameters, metrics, artifacts, and errors per iteration.
MLflow is optional and local only; runs fall back to local JSONL/Parquet files.
The test set is reserved for final evaluation, not iteration.

## Deployment

The Python pipeline exports:

- `model.onnx`
- `feature_schema.json`
- `target_schema.json` / `scenario_schema.json`
- `metrics.json`
- `model_card.md`
- ONNX-vs-scikit-learn parity results

The ONNX models are loaded by a separate **Go REST API** inference endpoint.
For now the endpoint runs locally. The deployment path is:

```text
Python training pipeline
        -> ONNX artifact
        -> Go REST API
        -> local inference
        -> future Docker image / cloud deployment
```

This repository owns the Python pipeline and ONNX artifacts, not the Go serving
layer.

## Setup

Requirements:

- Python 3.12
- `uv`
- Access to the `omp-as-demo-db` container and `omp_as_demo`
- The read-only credentials in `~/.config/omp-yield/env`

Install dependencies:

```bash
uv sync
```

Recommended credential location:

```bash
mkdir -p ~/.config/omp-yield
cp .env.example ~/.config/omp-yield/env
chmod 600 ~/.config/omp-yield/env
# edit ~/.config/omp-yield/env with the omp_ds_readonly credentials
```

The CLI resolves credentials in this order:

1. `OMP_ENV_FILE`
2. project `.env`
3. `~/.config/omp-yield/env`
4. `docker-build/.env` (local demo fallback only)

Verify access:

```bash
uv run omp-yield db ping
```

## Running the Marimo notebooks

Interactive notebook:

```bash
uv run --with marimo marimo edit notebooks/01_db_inventory.py
```

Export the inventory notebook to HTML:

```bash
uv run --with marimo marimo export html \
  notebooks/01_db_inventory.py \
  -o reports/01_db_inventory.html
```

Export the cleaning notebook:

```bash
uv run --with marimo marimo export html \
  notebooks/02_cleaning_report.py \
  -o reports/03_cleaning_report.html
```

For later modeling notebooks, install the optional data-science extras:

```bash
uv sync --extra ds
```

## CLI

Common user-facing commands:

```bash
# Database checks
uv run omp-yield db ping
uv run omp-yield db tables
uv run omp-yield db schema --table OILPALM
uv run omp-yield db query "SELECT TOP 5 NAME, UNIT, BLOCK, YEAR, Y_TOTAL_ton FROM OILPALM"

# Generate the database inventory and data dictionary
uv run omp-yield inventory

# Extract an immutable raw snapshot
uv run omp-yield extract \
  --snapshot-id 20261030T000000Z \
  --force \
  --report reports/02_extract_report.md

# Re-verify a snapshot's manifest, checksums, row counts, and columns
uv run omp-yield verify-snapshot data/raw/20261030T000000Z

# Refresh Phase 3 cleaning artifacts; existing approved configs are preserved
uv run omp-yield clean

# Show non-secret configuration
uv run omp-yield info
```

The extraction table list is in `config/extraction.yaml`. Snapshots are written
under `data/raw/<snapshot_id>/` and are intentionally gitignored.

## Documentation

Start here:

- `docs/README.md` — phase-based documentation index
- `docs/phase-minus-1-harness/README.md` — agent/CLI/MCP harness
- `docs/phase-0-access/README.md` — read-only database access
- `docs/phase-1-inventory/README.md` — database inventory summary
- `docs/phase-1-inventory/db_inventory.md` — table, join, and hierarchy report
- `docs/phase-1-inventory/data_dictionary.md` — OILPALM data dictionary
- `docs/phase-1-inventory/erd.md` — core ERD and join map
- `docs/phase-2-extraction/README.md` — raw snapshot summary
- `docs/phase-3-cleaning/README.md` — cleaning and feature-decision summary
- `docs/phase-3-cleaning/cleaning_report.md` — detailed cleaning report
- `config/features.yaml` — approved feature decisions
- `config/management_levers.yaml` — approved management levers
- `reports/00_access.md` — Phase 0 access report
- `reports/01_db_inventory.html` — interactive inventory notebook
- `reports/02_extract_report.md` — Phase 2 extraction and verification report
- `reports/03_cleaning_report.html` — interactive cleaning notebook

## Current status

- Phase -1 — agent/CLI/MCP harness: complete
- Phase 0 — read-only database access: complete
- Phase 1 — database inventory and data dictionary: complete
- Phase 2 — raw extraction and immutable snapshots: complete
- Phase 3 — cleaning, profiling, leakage audit, and feature decisions: approved
- Phase 4 — feature engineering and modeling table: next
