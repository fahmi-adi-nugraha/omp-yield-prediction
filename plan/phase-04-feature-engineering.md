# Phase 4 — Feature Engineering and Modeling Table

Status: **planned — next**

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
  - `yield_lag1`: `OILPALM.Y_TOTAL_ton` shifted 1 year within block;
    equivalent to prior-year HRR harvest FFB
  - `bunch_weight_lag1`: `OILPALM.Y_KGB` shifted 1 year within block;
    `Y_KGB = 1000 * Y_TOTAL_ton / Y_TOTAL_bunches`; alternative from
    `tbl_HRR_harvests` `sum(Y_FFB) / sum(Y_BunchNo)`
  - `harvest_interval_lag1`: `OILPALM.Y_AVG_harvest_int` shifted 1 year within
    block; alternative from `tbl_HRR_harvests` `mean(prevRoundLength_d)` or
    gaps between distinct `D_Harvest` dates
  - lag 2 yield and 3-year rolling yield
  - prior-year harvest rounds/losses and weather lags/anomalies
  - dry-month counts and water deficit
  - nutrient application rates/balances and recommendation gaps
  - stand, mature fraction, tree age, growth period
  - leaf/soil nutrient ratios
  - cumulative Ganoderma/pest pressure
  - estate/division aggregates from cutoff-safe data only

The three `*_lag1` features are derived, not raw `tbl_HRR_harvests` columns.
Current-year `Y_TOTAL_ton`, `Y_KGB`, and `Y_AVG_harvest_int` are leakage; only
their prior-year lags are safe. `tbl_HRR_harvests` can provide alternative
raw-event derivations.

Other non-raw external names must be implemented explicitly: `soil_ph` from
`SA_PH_H2O`, `soil_cec` from `SA_CEC`, `soil_som` from `SA_SOM`,
`black_bunch_per_palm` from `BlackBunch / NoOfPalm`, and the documented
weather/pest/budget/ABW aliases. Do not look for these names as table columns.
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
