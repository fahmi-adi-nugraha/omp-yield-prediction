---
name: OMP Data Profiling
description: Cleaning, missingness, leakage, outlier, and management-lever audit conventions for OMP yield data
---

# OMP Data Profiling

Use this skill during Phase 3 and whenever a new data snapshot is inspected.

## Scope

Produce a Marimo notebook and an exported HTML/Markdown report that let the
user choose the final feature set. Do not train a model in this phase.

## Mature filter

```text
YEAR <= 2025
Growth_Period IN ('SAYP', 'PYP', 'DYP')
```

Expected mature dataset: 2,258 block-years, 2,257 positive targets, one mature
zero-yield row (`204D` 2025). Flag the 178 `IGP` rows with positive yield and
the `124H` 2024/2025 inconsistency. Do not silently drop them.

## Required checks

### Duplicates

- Exact duplicate rows.
- Duplicate key rows on `(NAME, UNIT, BLOCK, YEAR)`.
- Duplicate or near-duplicate columns.
- Join-induced duplicates: nutrient products, monthly bunch counts, pest
  surveys, harvest events.

### Missingness

- Overall, by year, and by unit.
- Missingness patterns, not just counts.
- Treat `''`, `'No data'`, and `NULL` consistently.
- Known sparse/empty columns: `SA_TextClass`, `soilAcidity`,
  `waterTableDepth`, `trunkDiameter`, `LAI`, `LAI_FrondArea`,
  `LA_GreenLeaves`, `LA_Rachis_length`, `MillDistance`, `maturityAge_mt`.

### Constants and identifiers

- Zero-variance and near-zero-variance columns.
- Identifiers and sort orders that should not be features: `NAME`,
  `HarvestIndex`, `Upkeep_Index`, `BlockInYield`.

### Outliers

- Target: zeros, negatives, yield per hectare, extreme block totals.
- Area, stand, tree age, leaf nutrient ranges, fertilizer rates.
- Weather anomalies, especially the 2022 drought.
- Use IQR/robust z-scores and domain bounds. Flag; do not auto-delete.

### Leakage

Verify formulas and drop current-year target-derived columns:

- `Y_TH = Y_TOTAL_ton / area_ha`
- `Y_KGB = 1000 * Y_TOTAL_ton / Y_TOTAL_bunches`
- monthly `Y_*` sums equal annual totals
- `Y_TH_GAP`, `Y_GAP_Percent`, `Y_per_manday`, `Y_BNTREE` are derived
- `BlockInYield` is a maturity flag
- `Y_TH_POT` and `MarkerYield` require explicit approval and timing review

### Consistency

- Monthly sums vs annual totals.
- `area_ha` vs `areaIY_ha`; `palmStandMature_p` vs `area_ha`/stand.
- `D_TREEAGE` vs planting date and year.
- `tbl_HRR_harvests` aggregated FFB vs `Y_TOTAL_ton`.
- `tbl_areasPalmsBIY_blk_mts` and `tbl_SC_palmCensus` vs OILPALM stand.
- Fiscal-year alignment (`yrFis`, `FY_Harvest`) with `OILPALM.YEAR`.
- Key normalization and join match rates.

### Target and drift

- Distribution overall and by year.
- Block-count expansion (252 blocks in 2019 to 555 in 2024).
- 2022 drought and 2023-2025 recovery.
- Estate/division composition changes.

### Management-lever audit

For each candidate lever, report:

- Coverage by year and block.
- Missingness and variation.
- Observed range (5th-95th percentile).
- Whether it is available at `pre_season`, `mid_season`, or only post-season.
- Whether it is safe to expose in what-if.

Candidate levers: inorganic/organic N, P2O5, K2O, MgO, CaO, B; pruning;
harvester access; harvest interval/rounds; disease felling; weed control
(2025+ only); replanting/ablation.

Keep management levers in the model even if their marginal importance is low.
Report predictive importance and domain relevance separately.

## Marimo conventions

- One `.py` notebook per phase under `notebooks/`.
- No hidden state; all inputs from Parquet or the DB CLI.
- Use Polars, not pandas.
- Use `marimo export html` for the report.
- Use `marimo export ipynb` only if a Jupyter copy is requested.

## Feature decision table

Columns:

`feature`, `group`, `dtype`, `missing_pct`, `unique`, `univariate_signal`,
`vif`, `leakage_risk`, `available_at`, `role`, `adjustable`, `decision`,
`reason`.

Decisions: `keep`, `drop`, `review`. The pipeline must refuse to train while
any decision is still `review` or while the config is not approved.

## Approval gate

End the phase with:

- `config/features.yaml`
- `config/management_levers.yaml`
- `reports/03_cleaning_report.html`

Ask the user to approve the feature list, maturity rule, and levers before
feature engineering.
