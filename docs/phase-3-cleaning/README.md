# Phase 3 — Cleaning, Profiling, and Feature Decisions

Status: **approved**

Phase 3 cleans the mature 2019–2025 block-year population, audits target
leakage, profiles missingness and outliers, and produces feature and
management-lever configurations. This revision is **approved**.

## Key counts

| Item | Value |
|---|---:|
| Usable rows | 2,908 |
| Mature rows | 2,258 |
| Mature positive-target rows | 2,257 |
| Anomaly rows flagged | 182 |
| Candidate feature decisions | 230 |
| Keep decisions | 61 |
| Drop decisions | 168 |
| Review decisions | 0 |

## Key anomaly

`204D` 2025 has target `0` but HRR harvest FFB totals about `759 t`. Treat it as
a source-data inconsistency before training.

## Derived and renamed features

Several external candidate names are **not raw columns**:

- `yield_lag1`, `bunch_weight_lag1`, `harvest_interval_lag1` are lagged
  `OILPALM` fields.
- `soil_ph`, `soil_cec`, `soil_som` rename `SA_PH_H2O`, `SA_CEC`, `SA_SOM`
  from `tbl_FN_soilAnalysis`.
- `black_bunch_per_palm` is `BlackBunch / NoOfPalm` from
  `tbl_BBC_bunchCounts`.
- Weather, pest, budget, and ABW aliases are also documented.

Exact formulas are in `cleaning_report.md` and the `derivation` fields in
`config/features.yaml`.

## Approval status

- `config/features.yaml` is `status: approved`.
- `config/management_levers.yaml` is `status: approved`.
- Review decisions remaining: **0**.
- The final modeling table is not built until Phase 4.
- Re-running `omp-yield clean` preserves existing edited configs and writes
  `*.generated.yaml` drafts unless `--overwrite-config` is used.

## Artifacts

- `cleaning_report.md` — detailed Phase 3 report
- `../../data/phase-3-cleaning/` — CSVs for missingness, leakage, outliers, consistency, decisions
- `../../config/features.yaml` — approved feature decisions
- `../../config/management_levers.yaml` — approved levers
- `../../data/interim/phase-3/` — cleaned intermediate Parquet files
- `../../reports/03_cleaning_report.html` — interactive Marimo report

## Next

Phase 3 is approved. Proceed to Phase 4 — feature engineering and the final modeling table.
