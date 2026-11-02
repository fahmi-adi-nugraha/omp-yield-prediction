# Phase 5 — Splits, Data Contracts, and Evaluation Protocol

Status: **complete**

## Overview

Define the exact evaluation protocol, data contracts, and leakage-safe splits
before model selection. This prevents tuning against the test set or leaking
future years/blocks.

## Goals and deliverables

- `src/omp_yield/splits.py` — temporal, grouped, and rolling-origin splitters.
- `config/evaluation.yaml` — split definitions, metrics, seed, baseline rules.
- `data/processed/splits.json` — train/validation/test membership and hashes.
- `docs/data_contract.md` — schema, uniqueness, ranges, categories, nullability.
- `docs/phase-5-splits-contracts/README.md`.
- Tests for split integrity and future-data leakage.

## Technical details

Yield prediction:

- Primary: chronological train 2019–2023, validation 2024, test 2025; after
  tuning, refit on 2019–2024 and report 2025 once.
- Secondary benchmark: grouped 80/10/10 by block (`GroupShuffleSplit`).
- CV: `GroupKFold` by block inside training and `TimeSeriesSplit` where useful.

Forecast:

- Rolling origin: train ≤2022 → validate 2023; ≤2023 → 2024; ≤2024 → 2025.
- Final fit ≤2024; forecast 2026–2028 (optional 2029–2030 as experimental).
- Never use future records in origin features.

Data contract:

- Unique `(NAME, UNIT, BLOCK, YEAR)`.
- Target non-negative; mature population; allowed `Growth_Period` values.
- Area/tree-age/stand bounds.
- Feature availability metadata present.
- All dates parseable; category sets controlled.

Metrics:

- Point accuracy: RMSE, MAE, MAPE/sMAPE, R², bias.
- Forecast: MASE, RMSE, MAPE, bias, interval coverage.
- Estate-level aggregate error and bias.
- Baselines: global mean, last-year yield, 3-year average, linear trend, budget.

## Locations

- `src/omp_yield/splits.py`
- `config/evaluation.yaml`
- `data/processed/splits.json` (gitignored)
- `docs/data_contract.md`
- `docs/phase-5-splits-contracts/`
- `tests/test_splits.py`

## Verification

- No block overlap in grouped splits.
- No future year in training for temporal folds.
- Test set membership is fixed and used once.
- Contract validation fails on duplicate keys, negative target, or unexpected
  categories.

## Completion summary

- Primary chronological split: 1,356 train rows (2019–2023), 404 validation rows
  (2024), 498 test rows (2025). Final refit: 1,760 train rows (2019–2024), 498
  test rows (2025).
- Grouped block split: 404/51/51 blocks and 1,770/234/254 rows.
- Five grouped CV folds and three expanding-window time-series folds.
- Three rolling forecast origins: 2022→2023, 2023→2024, 2024→2025.
- `data/processed/splits.json` contains membership and SHA256 hashes.
- `docs/data_contract.md` records 32 passing contract checks.
- `tests/test_splits.py` covers temporal order, grouped block isolation, CV
  isolation, rolling-origin leakage, contract failures, and determinism.

## Next

Phase 6 — model selection.
