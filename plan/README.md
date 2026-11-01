# OMP Yield Prediction — Implementation Plan

This directory is the durable, phase-based implementation plan for the OMP oil
palm yield prediction project. It is written so a new human or LLM with blank
context can understand what exists, what is next, how each phase is verified,
and where every artifact lives.

The plan is the source of truth for phase scope, status, approval gates, and
artifact locations. Update the relevant phase document and this roadmap whenever
a phase changes.

## How to use this plan

1. Read this file completely.
2. Read the phase document for the current phase and the next phase.
3. Inspect the referenced code, configs, tests, reports, and docs.
4. Do not skip an approval gate or proceed past a draft phase.
5. After a phase, update status, artifacts, verification results, and any
   changed decisions.

## Current state

As of 2026-11-01:

| Phase | Status | Phase document |
|---|---|---|
| Phase -1 — Agent/CLI/MCP harness | Complete | `phase-minus-1-harness.md` |
| Phase 0 — Read-only database access | Complete | `phase-00-access.md` |
| Phase 1 — Database inventory and data dictionary | Complete | `phase-01-inventory.md` |
| Phase 2 — Raw extraction and immutable snapshots | Complete | `phase-02-extraction.md` |
| Phase 3 — Cleaning, leakage audit, feature decisions | Draft — awaiting approval | `phase-03-cleaning.md` |
| Phase 4 — Feature engineering and modeling table | Next after Phase 3 approval | `phase-04-feature-engineering.md` |
| Phase 5 — Splits, contracts, evaluation protocol | Planned | `phase-05-splits-contracts.md` |
| Phase 6 — Model selection | Planned | `phase-06-model-selection.md` |
| Phase 7 — Hyperparameter search | Planned | `phase-07-hyperparameter-search.md` |
| Phase 8 — Final training and evaluation | Planned | `phase-08-final-training.md` |
| Phase 9 — Explainability and what-if | Planned | `phase-09-explainability.md` |
| Phase 10 — ONNX export and parity | Planned | `phase-10-onnx.md` |
| Phase 11 — Packaging, reproducibility, operations | Planned | `phase-11-packaging.md` |
| Phase 12 — Freeze, release, handover | Planned | `phase-12-freeze.md` |

**Current gate:** Phase 3 has generated draft `config/features.yaml` and
`config/management_levers.yaml`. They are not approved. Phase 4 must not start
until the `review` decisions and levers are resolved.

## Project goals

The project builds two models:

1. **Crop yield prediction model** — predicts mature block-year
   `Y_TOTAL_ton` in metric tons at a `pre_season` or `mid_season` cutoff.
   It supports what-if analysis over management levers only.
2. **Crop yield forecasting model** — produces estate-level multi-year
   forecasts with division/block detail, 3-year default horizon, optional
   experimental 5-year horizon, and scenario-based management/weather inputs.

The Python pipeline produces the data, models, reports, and ONNX artifacts. A
separate Go REST API loads ONNX models for local inference; future deployment is
via a Docker image/cloud. The serving layer is not part of this Python repo.

## Non-negotiable decisions

- Target: `OILPALM.Y_TOTAL_ton` in metric tons.
- Mature population: `Growth_Period IN ('SAYP', 'PYP', 'DYP')`.
- Exclude `IGP` immature rows and the 2026 placeholder row from modeling.
- Two cutoffs: `pre_season` (31 Dec t-1) and `mid_season` (configurable cutoff
  in t). Never mix features across cutoffs.
- Exclude current-year target-derived `Y_*` fields from features.
- Every feature has an `available_at` value and is validated at the cutoff.
- Forecast output is estate-level; training uses the block panel and aggregates
  through `UNIT` to `NAME`.
- What-if exposes management levers only. Weather, soil, age, stand, leaf
  analysis, pest pressure, and prior yield are read-only context.
- Use time-aware validation. The test set is used once, after iteration.
- Keep management levers even if marginal predictive importance is low.
- MLflow is optional and local only.
- No REST API, monorepo migration, or serving layer in this repo.
- Python 3.12, `uv`, Polars, scikit-learn, Marimo.

## Artifact policy

| Directory | Contents |
|---|---|
| `data/raw/<snapshot_id>/` | Immutable Phase 2 Parquet snapshots; gitignored |
| `data/phase-1-inventory/` | Phase 1 generated CSV inventory tables |
| `data/phase-3-cleaning/` | Phase 3 generated cleaning/leakage/decision CSVs |
| `data/interim/<phase>/` | Cleaned or intermediate data; gitignored |
| `data/processed/` | Final modeling tables and split manifests; gitignored |
| `data/db-json-exports/` | Legacy JSON exports; gitignored |
| `config/` | Extraction, features, transforms, model, and lever configs |
| `docs/phase-*/` | Phase documentation |
| `reports/` | Generated reports, HTML notebooks, and model cards |
| `models/<run_id>/` | Model artifacts and ONNX files |
| `notebooks/` | Marimo notebooks |
| `src/omp_yield/` | Pipeline code |
| `tests/` | Unit and integration tests |
| `plan/` | This implementation plan |

Detailed artifact locations, commands, and verification steps are in each phase
document. The table below is the quick roadmap.

## Phase map

| Phase | Goal | Main artifacts | Status |
|---|---|---|---|
| -1 | Agent/CLI/MCP harness | package scaffold, DB CLI, MCP server, `.opencode/` agents/skills | Complete |
| 0 | Minimum-privilege DB access | `omp_ds_readonly`, access report, bootstrap SQL | Complete |
| 1 | Understand the database | inventory CSVs, data dictionary, ERD, Marimo report | Complete |
| 2 | Immutable raw snapshot | Parquet snapshot, manifest, checksums, extraction report | Complete |
| 3 | Cleaning and feature decisions | cleaning report, draft features/levers, interim Parquet | Draft |
| 4 | Feature engineering | transforms, derived features, modeling table | Planned |
| 5 | Validation protocol | splits, data contracts, metrics, baselines | Planned |
| 6 | Model selection | model comparison report and recommendation | Planned |
| 7 | Tuning | random-search trials, best parameters, tuning report | Planned |
| 8 | Final training | fitted models, test metrics, forecast backtest, model card | Planned |
| 9 | Explainability | SHAP/PDP/ICE, local what-if simulator, lever sensitivity | Planned |
| 10 | ONNX | end-to-end ONNX artifacts and parity tests | Planned |
| 11 | Packaging | CLI, CI, Docker, runbook, monitoring, local MLflow | Planned |
| 12 | Freeze | frozen configs, reproducibility report, release/handover | Planned |

## Approval gates

- **Gate 1:** Phase 3 feature list (`config/features.yaml`) and management levers
  (`config/management_levers.yaml`). All `review` decisions must be resolved.
- **Gate 2:** Phase 6 model family, target definition, and validation protocol.
- **Gate 3:** Phase 8 final metrics and model card.
- **Gate 4:** Phase 12 frozen release and reproducibility report.

## Current data and known anomalies

- Raw snapshot: `data/raw/20261030T000000Z` (28 tables, 140,004 rows,
  gitignored).
- Usable OILPALM rows: 2,908 (2019–2025).
- Mature rows: 2,258; mature positive-target rows: 2,257.
- `204D` 2025 has target `0` but HRR harvest FFB totals about `759 t`; treat as
  a source-data inconsistency and decide whether to exclude it.
- `124H` 2024/2025 has `areaIY_ha = 0` but positive yield.
- 178 `IGP` rows have positive yield despite being immature; excluded from the
  mature model.
- `tbl_GIS_blocks` is not extracted because it contains a SQL Server `geometry`
  column.

## If context is lost

Read `plan/README.md`, then the current phase document, then the next phase
document. Then inspect `README.md`, `docs/README.md`, `reports/README.md`,
`config/`, `src/omp_yield/`, and `tests/`. Do not infer phase status from file
existence alone; use this plan and the phase documents.
