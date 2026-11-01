# Phase 4 — Feature Engineering and Modeling Table

Status: **planned — blocked by Phase 3 approval**

## Overview

Apply the approved feature decisions and transforms, build cutoff-safe derived
features, and assemble the final block-year modeling table for both yield
cutoffs and the forecast panel.

## Goals and deliverables

- `src/omp_yield/features.py` with a declarative transform/feature registry.
- `config/transforms.yaml` — approved transform list and parameters.
- `src/omp_yield/splits.py` may be scaffolded here; split design is finalized
  in Phase 5.
- `data/processed/modeling_table.parquet` — one row per block-year with target,
  keys, future-known features, and cutoff-specific feature values.
- `docs/phase-4-feature-engineering/README.md`.
- `reports/04_feature_engineering.html` — before/after distributions, VIF,
  ablation, leakage checks, and feature approval summary.
- Updated `docs/README.md`, `reports/README.md`, and `README.md` status.

## Technical details

- Enforce `available_at` from the approved feature config:
  `pre_season`, `mid_season`, `post_season`.
- Build two feature views:
  - `pre_season`: data through 31 Dec of `t-1`.
  - `mid_season`: records with date `<= cutoff` in `t`.
- Derived features to implement:
  - lag 1/2 yield and 3-year rolling yield
  - prior-year harvest interval/rounds/losses and bunch weight
  - weather lags, anomalies, dry-month counts, water deficit
  - nutrient application rates/balances and recommendation gaps
  - stand, mature fraction, tree age, growth period
  - leaf/soil nutrient ratios
  - cumulative Ganoderma/pest pressure
  - estate/division aggregates from cutoff-safe data only
- Categorical handling: one-hot for low-cardinality; ordinal for ordered
  categories; no raw high-cardinality IDs.
- Numeric handling: tree models may use native missing values; linear models
  require median imputation, missing indicators, and standardization.
- Target: `Y_TOTAL_ton` in metric tons. Do not mix current-year target-derived
  fields into features.
- Generate feature-group ablation and VIF on the training fold only.

## Locations

- `src/omp_yield/features.py`
- `config/transforms.yaml`
- `data/processed/modeling_table.parquet` (gitignored)
- `docs/phase-4-feature-engineering/`
- `reports/04_feature_engineering.html`
- `tests/test_features.py`

## Verification

- No `Y_*` current-year target-derived feature in the final list.
- Every feature has `available_at` and passes cutoff tests.
- Modeling table key `(NAME, UNIT, BLOCK, YEAR)` is unique.
- All approved `review` items are resolved.
- Tests cover lag direction, cutoff filtering, and missing-value handling.

## Next

Phase 5 — data contracts, splits, and evaluation protocol.
