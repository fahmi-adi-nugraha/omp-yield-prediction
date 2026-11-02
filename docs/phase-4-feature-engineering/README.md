# Phase 4 — Feature Engineering and Modeling Table

Status: **complete**

## Summary

Phase 4 applies the approved feature and management-lever decisions to the
mature block-year panel and writes the first modeling table.

| Item | Value |
|---|---|
| Source snapshot | `data/raw/20261030T000000Z` |
| Modeling rows | 2,258 |
| Target | `Y_TOTAL_ton` metric tons |
| Modeling-table columns | 139 |
| Feature columns | 132 |
| Pre-season features | 107 |
| Mid-season features | 132 (107 pre-season + 25 mid-season-only) |
| Target mean | 680.23 t |
| Target median | 754.95 t |
| Flagged anomaly rows | 3 (`124H` 2024/2025, `204D` 2025) |

The mature filter is `YEAR <= 2025` and
`Growth_Period IN ('SAYP', 'PYP', 'DYP')`. The 2026 placeholder is excluded.
The 2,258 mature rows include the `204D` 2025 zero-yield row and the two `124H`
area anomalies; they are flagged with `anomaly_flags`/`has_anomaly`, not
silently dropped.

## Cutoff design

- **Pre-season** — data through 31 Dec of `t-1`: context, management,
  prior-year yield/harvest history, prior-year weather, soil, Ganoderma, nutrient
  applications, and cutoff-safe division/estate aggregates.
- **Mid-season** — pre-season features plus current-year records with dates on
  or before the configured cutoff. The default cutoff is **30 June** in
  `config/transforms.yaml`.

The table stores pre-season features under `pre_*` columns and mid-season-only
features under `mid_*` columns. The mid-season view is `pre_* + mid_*`. A
feature is never moved between cutoffs.

## Feature groups

| Group | Features |
|---|---:|
| context | 69 |
| management | 18 |
| leaf | 24 |
| weather | 5 |
| history | 8 |
| soil | 4 |
| pest | 3 |
| leading indicator | 1 |

Management features include all approved levers: inorganic N/P/K/Mg/Ca/B,
organic N/P/K, pruning, harvester access, and the prior-year harvest interval.
The `harvest_interval_lag1` lever is deliberately a prior-year lag; the
current-year `Y_AVG_harvest_int` is target-derived and excluded.

## Derived features

The main derived features are:

- `pre_yield_lag1`, `pre_yield_lag2`, `pre_yield_roll3_mean`
- `pre_bunch_weight_lag1`
- `pre_harvest_interval_lag1`, `pre_harvest_rounds_lag1`
- `pre_harvest_loss_rate_lag1`
- `pre_division_yield_lag1_mean`, `pre_estate_yield_lag1_mean`
- `pre_rain_annual_mm_lag1`, `pre_dry_months_lag1`,
  `pre_water_deficit_lag1`, `pre_rain_anomaly_lag1`,
  `pre_rain_roll3_mean_lag1`
- `pre_soil_ph`, `pre_soil_cec`, `pre_soil_som`,
  `pre_soil_cec_som_ratio`
- `pre_ganoderma_affected_area`, `pre_ganoderma_severity`,
  `pre_ganoderma_cumulative_area`
- `pre_nutrient_balance_NK`
- `pre_mature_fraction`
- leaf ratios `mid_LA_NK_ratio`, `mid_LA_NP_ratio`, `mid_LA_KMg_ratio`,
  `mid_LA_CaMg_ratio`
- `mid_black_bunch_per_palm` from the latest pre-cutoff bunch count
- marker-product indicators and counts for the high-cardinality `markerFert`
  text field

Weather is joined through `OILPALM.ID_WeatherStation = tbl_CW_weatherAndWater.R_UNIT`.
The lag and anomaly values use prior weather years only. Soil uses the latest
sample on or before 31 Dec of `t-1`. Ganoderma uses prior-year survey maxima.
Nutrient applications follow the approved pre-season lever decision.

## Leakage controls

Current-year target-derived columns are excluded, including `Y_TH`, `Y_KGB`,
monthly `Y_*`, `Y_TH_GAP`, `Y_GAP_PERCENT`, `Y_per_manday`, `Y_TH_POT`, and
`MarkerYield`. Only explicit prior-year history is allowed:

- `pre_yield_lag1`
- `pre_yield_lag2`
- `pre_yield_roll3_mean`
- `pre_bunch_weight_lag1`
- `pre_harvest_interval_lag1`
- `pre_harvest_rounds_lag1`
- `pre_harvest_loss_rate_lag1`

The feature schema records `available_at`, `pre_season`, `mid_season`, group,
role, adjustable flag, encoding status, source, and derivation for every
column.

## Categorical handling

- Ordinal: `growth_period_code` (`SAYP`=0, `PYP`=1, `DYP`=2),
  `harvester_access_code` (`None`=0, `Incomplete`=1, `Full`=2).
- One-hot: low-cardinality context and pruning categories.
- High-cardinality `markerFert` text is reduced to product count, known flag,
  and product-family indicators; the raw text is not a model feature.

Missing numeric values are preserved for tree models. Linear-model imputation
and missing indicators are deferred to the Phase 5/6 model-specific pipelines.

## Artifacts

Generated (gitignored):

- `data/processed/modeling_table.parquet`
- `data/processed/feature_schema.csv`
- `data/processed/feature_schema.parquet`
- `reports/04_feature_engineering.html`

Committed inputs:

- `config/features.yaml`
- `config/management_levers.yaml`
- `config/transforms.yaml`
- `feature_engineering_summary.md` — full feature-family, derivation, and model-mapping reference

## Commands

```bash
# Build the table, schema, and report from the latest snapshot
uv run omp-yield features

# Verify the feature contract and lag/cutoff behavior
uv run pytest tests/test_features.py

# Full suite
uv run pytest
uv run ruff check .
uv run mypy src tests
```

## Report notes

`reports/04_feature_engineering.html` includes the modeling-table summary,
feature approval counts, cutoff/group counts, leakage checks, missingness,
distribution summaries, a full-data VIF diagnostic, and a chronological
feature-group ablation diagnostic.

The VIF and ablation tables are engineering diagnostics only. The final VIF,
ablation, and evaluation protocol will be computed on Phase 5 training folds.

## Next

Phase 5 — data contracts, splits, and evaluation protocol.
