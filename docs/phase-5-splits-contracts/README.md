# Phase 5 — Splits, Data Contracts, and Evaluation Protocol

Status: **complete**

## Summary

Phase 5 freezes the evaluation protocol before model selection. It defines:

- chronological train/validation/test splits;
- a grouped block holdout;
- grouped and chronological cross-validation folds;
- rolling-origin forecast backtests;
- data-contract validation for the Phase 4 modeling table;
- the metric and baseline rules for Phase 6 onward.

## Yield prediction protocol

Primary chronological split:

| Split | Years | Rows |
|---|---|---:|
| Train | 2019–2023 | 1,356 |
| Validation | 2024 | 404 |
| Test | 2025 | 498 |
| Final refit | 2019–2024 | 1,760 |
| Final test | 2025 | 498 |

The test years are fixed. Model selection and hyperparameter search use the
training and validation years only; the test set is reserved for the final
evaluation after tuning.

Secondary grouped block split (80/10/10 by block):

| Split | Blocks | Rows |
|---|---:|---:|
| Train | 404 | 1,770 |
| Validation | 51 | 234 |
| Test | 51 | 254 |

No block appears in more than one grouped split.

Cross-validation inside the primary training years:

- `GroupKFold` by block: 5 folds.
- `TimeSeriesSplit`: 3 expanding-window folds with validation years 2021, 2022,
  and 2023.

## Forecast protocol

Rolling origins:

| Train through | Validation | Train rows | Validation rows |
|---:|---:|---:|---:|
| 2022 | 2023 | 1,045 | 311 |
| 2023 | 2024 | 1,356 | 404 |
| 2024 | 2025 | 1,760 | 498 |

Final forecast fit uses data through 2024. The default forecast horizon is
2026–2028; 2029–2030 is reserved as an experimental extension. Future origin
features must never use records after the origin.

## Metrics and baselines

Yield prediction point accuracy:

- RMSE, MAE, MAPE, sMAPE, R², and bias.
- Error and bias by year, division, and age band in the evaluation report.

Forecast metrics:

- MASE, RMSE, MAPE, bias, and prediction-interval coverage.
- Estate-level aggregate error and bias after aggregating block forecasts
  through `UNIT` to `NAME`.

Baselines:

- Global mean.
- Last-year yield.
- Three-year average.
- Linear trend.
- Company budget for forecast benchmarking.

## Data contract

The generated contract is `docs/data_contract.md`. It records:

- unique `(NAME, UNIT, BLOCK, YEAR)` key;
- non-negative target;
- mature 2019–2025 year range;
- feature-schema coverage and cutoff metadata;
- numeric bounds for area, tree age, stand, and mature fraction;
- ordinal and one-hot categorical domains;
- source date parsing and source category sets;
- nullability and all-null-column checks.

The contract check currently passes all 32 checks.

## Artifacts

Generated (gitignored):

- `data/processed/splits.json` — memberships, fold definitions, and hashes.
- `data/processed/contract_report.csv` — check-by-check contract results.

Committed:

- `config/evaluation.yaml`
- `src/omp_yield/splits.py`
- `docs/data_contract.md`
- `docs/phase-5-splits-contracts/README.md`
- `tests/test_splits.py`

## Commands

```bash
# Validate the contract and write splits.json, contract_report.csv, and data_contract.md
uv run omp-yield splits

# Split and contract tests
uv run pytest tests/test_splits.py

# Full suite
uv run pytest
uv run ruff check .
uv run mypy src tests
```

## Verification

- Primary train years stop at 2023; validation is 2024; test is 2025.
- The grouped split has zero block overlap.
- Grouped CV folds have zero block overlap.
- Time-series folds never train on future years.
- Rolling-origin train membership stops at the origin year.
- Duplicate keys, negative targets, out-of-range numerics, and unexpected
  ordinal categories fail the contract.

## Next

Phase 6 — model selection.
