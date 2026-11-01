# Phase 3 — Cleaning, Leakage Audit, and Feature Decisions

Status: **approved**

## Overview

Profile the mature 2019–2025 block-year population, audit target leakage,
identify data-quality anomalies, assess feature signal/redundancy, and produce
feature and management-lever decisions for approval. The decisions are now
approved and frozen for Phase 4.

## Goals and deliverables

- `src/omp_yield/cleaning.py` — population split, missingness, duplicates,
  leakage checks, outliers, domain/consistency checks, numeric signal, VIF,
  redundancy, feature decisions, management levers, report generation.
- CLI `uv run omp-yield clean`.
- `notebooks/02_cleaning_report.py` and `reports/03_cleaning_report.html`.
- `docs/phase-3-cleaning/README.md` and `cleaning_report.md`.
- `data/phase-3-cleaning/*.csv` — missingness, leakage, outliers, consistency,
  signal, VIF, redundancy, feature decisions.
- `data/interim/phase-3/*.parquet` — mature, mature-positive, and anomaly
  datasets (gitignored).
- `config/features.yaml` — approved feature decisions.
- `config/management_levers.yaml` — approved levers.

## Technical details

Population:

- Usable: 2,908 rows (2019–2025).
- Mature: 2,258 rows (`SAYP`, `PYP`, `DYP`).
- Mature positive-target: 2,257 rows.
- Immature: 650 rows; 2026 placeholder: 1 row.
- Flagged anomalies: 182 rows.

Leakage checks verify target-derived identities such as:

- `Y_TH = Y_TOTAL_ton / area_ha`
- `Y_KGB = 1000 * Y_TOTAL_ton / Y_TOTAL_bunches`
- monthly `Y_*` sums equal annual totals
- `Y_TH_GAP`, `Y_GAP_Percent`, `Y_per_manday`, `Y_BNTREE`

All identities pass, so current-year `Y_*` fields are dropped from candidate
features. `Y_TH_POT` and `MarkerYield` were reviewed and are approved as `drop`.

Feature decisions use missingness, distinct counts, leakage rules, univariate
Pearson signal, approximate VIF, and correlation pairs. Management levers are
kept even if marginal predictive importance is low.

Derived/renamed provenance: several external feature names are not exact raw
columns. `soil_ph`, `soil_cec`, and `soil_som` rename
`SA_PH_H2O`, `SA_CEC`, and `SA_SOM` from `tbl_FN_soilAnalysis`.
`black_bunch_per_palm` is `BlackBunch / NoOfPalm` from
`tbl_BBC_bunchCounts`. `yield_lag1`, `bunch_weight_lag1`, and
`harvest_interval_lag1` are lagged `OILPALM` fields. Weather, pest, budget, and
ABW aliases are also derived/renamed. See `phase-04-feature-engineering.md`.

Known anomalies:

- `204D` 2025 target `0` vs HRR harvest FFB about `759 t` — source
  inconsistency; exclude from training unless the source is corrected.
- `124H` 2024/2025 `areaIY_ha=0` with positive yield.
- 178 `IGP` rows have positive yield despite immature status.
- 9 mature rows have mature stand > total stand.
- 228 rows have a one-year tree-age/planting-year discrepancy.

Approved decision counts: 61 keep, 168 drop, 0 review, 1 target. User-edited
roles include `no_correlation`, `sparse_no_info`, `minimal_info`,
`missing_values`, and `no_info` for the rejected features.

## Locations

- `src/omp_yield/cleaning.py`
- `notebooks/02_cleaning_report.py`
- `reports/03_cleaning_report.html`
- `docs/phase-3-cleaning/`
- `data/phase-3-cleaning/`
- `data/interim/phase-3/` (gitignored)
- `config/features.yaml`
- `config/management_levers.yaml`

## Verification

```bash
uv run omp-yield clean
uv run --with marimo marimo export html notebooks/02_cleaning_report.py   -o reports/03_cleaning_report.html
uv run pytest
OMP_RUN_INTEGRATION=1 uv run pytest tests/test_db_integration.py
uv run ruff check .
uv run mypy src tests
```

## Approval gate

**Passed.** The feature list and management levers are approved. The `204D` 2025
anomaly is documented and must be handled in Phase 4/5; it must not be used for
training without an explicit exclusion decision.

## Next

Phase 4 — feature engineering and the final modeling table.
