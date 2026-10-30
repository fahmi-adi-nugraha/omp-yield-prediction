# Phase 1 — Database Inventory and Data Dictionary

Status: **complete**

## Generated artifacts

| Artifact | Purpose |
|---|---|
| `db_inventory.md` | Main inventory report |
| `data_dictionary.md` | Readable OILPALM data dictionary |
| `erd.md` | Core ERD and join map |
| `data/schema_tables.csv` | All tables, row counts, column counts |
| `data/schema_columns.csv` | All visible columns and types |
| `data/key_constraints.csv` | Primary and unique keys |
| `data/foreign_keys.csv` | Foreign keys |
| `data/key_uniqueness.csv` | Candidate business-key duplicate checks |
| `data/date_ranges.csv` | Min/max coverage per date-like column |
| `data/join_coverage.csv` | Candidate table coverage against OILPALM |
| `data/oilpalm_dictionary.csv` | OILPALM dictionary as CSV |
| `../../reports/01_db_inventory.html` | Exported Marimo inventory notebook |

## Key findings

- 274 user tables.
- 4,458 visible columns.
- 266 key constraints and 137 foreign keys.
- 177 date-like columns with recorded min/max coverage.
- `OILPALM`: 2,909 rows, 207 columns, unique on
  `(NAME, UNIT, BLOCK, YEAR)`.
- 553 distinct block codes, 9 divisions, 1 estate.
- `tbl_FN_nutActRec`, `tbl_areasPalmsBIY_blk_mts`, and
  `tbl_SC_palmCensus` cover 100% of OILPALM block-years.
- `tbl_HRR_harvests` covers 83.7% of OILPALM block-years.
- `tbl_PD_surveys` covers 89.7%.
- `tbl_FN_soilAnalysis` covers only 11.6%.
- `tbl_BBC_bunchCounts` covers 23.8% and only 2023–2025.
- `tbl_CB_cropBudgetMt` covers 100% but is a benchmark, not a feature.
- `tbl_CLA_auditResults` is 2025-only and 2.1% block-year coverage.

## Important schema notes

- The operational key chain is
  `NAME/suEstate/Estate/ESTATE/R_Name` → `UNIT/suDivision/Unit/UNIT` →
  `BLOCK/suBlock/Block` → `YEAR/Yr/yrFis/Y_Harvest`.
- Weather joins through `OILPALM.ID_WeatherStation` to
  `tbl_CW_weatherAndWater.R_UNIT`, not through `OILPALM.UNIT`.
- Event tables must be aggregated before joining:
  `tbl_HRR_harvests`, `tbl_PD_surveys`, `tbl_BBC_bunchCounts`,
  `tbl_FN_soilAnalysis`, and the fertilizer product tables.
- `tbl_CLA_auditResults` is unique on
  `(NAME, UNIT, BLOCK, YEAR, AuditDate, Row_1, Row_2)`, not on block-year
  alone.
- `tbl_BBC_forecastABW` has 2023–2025 data and one null 2026 row.
- `tbl_PCD_pesticideAct_dt` is 2025-only; use it for scenario inputs, not
  historical training features.

## Growth periods

| Code | Ages | Meaning |
|---|---:|---|
| `IGP` | 0–2 | Immature growth phase |
| `SAYP` | 3–7 | Steep ascent yield phase |
| `PYP` | 8–15 | Plateau yield phase |
| `DYP` | 16–25 | Declining yield phase |
| `LDYP` | 26+ | Late declining phase; should be replanted |

Mature model filter: `Growth_Period IN ('SAYP', 'PYP', 'DYP')`.

## Data dictionary notes

The OILPALM dictionary includes descriptions from `tbl_sys_fldDefs` and
`tbl_sys_UDE_fields`, null counts, distinct counts, preliminary roles, and
availability timing.

Known leakage and quality flags are listed in `data_dictionary.md`. Notable
items:

- `Y_TH`, `Y_KGB`, monthly `Y_*`, `Y_TH_GAP`, `Y_GAP_Percent`, and
  `Y_per_manday` are target-derived.
- `BlockInYield` is a maturity flag.
- `Y_TH_POT` and `MarkerYield` require timing/source review.
- `SA_TextClass` is 99.1% missing.
- `areaIY_ha` is inconsistent for `124H`.

## Next

Phase 2 — raw extraction and immutable Parquet snapshots.
