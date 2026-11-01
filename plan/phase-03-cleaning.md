# Phase 3 — Cleaning, Leakage Audit, and Feature Decisions

Status: **draft — awaiting approval**

## Overview

Profile the mature 2019–2025 block-year population, audit target leakage,
identify data-quality anomalies, assess feature signal/redundancy, and produce
draft feature and management-lever decisions for user approval.

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
- `config/features.yaml` — draft feature decisions.
- `config/management_levers.yaml` — draft levers.

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
features. `Y_TH_POT` and `MarkerYield` are `review` because formula checks alone
cannot establish their timing/source.

Feature decisions use missingness, distinct counts, leakage rules, univariate
Pearson signal, approximate VIF, and correlation pairs. Management levers are
kept even if marginal predictive importance is low.

Known anomalies:

- `204D` 2025 target `0` vs HRR harvest FFB about `759 t` — source
  inconsistency; decide whether to exclude.
- `124H` 2024/2025 `areaIY_ha=0` with positive yield.
- 178 `IGP` rows have positive yield despite immature status.
- 9 mature rows have mature stand > total stand.
- 228 rows have a one-year tree-age/planting-year discrepancy.

Current decision counts: 49 keep, 147 drop, 33 review, 1 target. The 33 review
items include `Y_TH_POT`, `MarkerYield`, derived leaf/LA features, `TC_*`, and
sparse soil/bunch features.

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

Do not proceed to Phase 4 until:

- Every `review` feature in `config/features.yaml` is resolved.
- `config/management_levers.yaml` is approved or edited.
- The `204D` 2025 decision is documented.
- The mature filter and target definition are confirmed.

## Next

Phase 4 — feature engineering and the final modeling table.
