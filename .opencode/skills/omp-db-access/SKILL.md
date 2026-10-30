---
name: OMP Database Access
description: Read-only access patterns, schema map, join keys, and safety rules for the OMP demo database
---

# OMP Database Access

Use this skill for any task that reads from the OMP demo SQL Server database.

## Connection

- Container: `omp-as-demo-db`
- Database: `omp_as_demo`
- Host/port: `localhost:1433`
- Local credentials: `docker-build/.env` (fallback for local development)
- Production/pipeline account: `omp_ds_readonly`, created in Phase 0

The CLI loads `.env` first and falls back to `docker-build/.env` when `.env`
does not exist. Shell environment variables take precedence.

```bash
uv run omp-yield db ping
uv run omp-yield db tables
uv run omp-yield db schema --table OILPALM
uv run omp-yield db query "SELECT TOP 5 NAME, UNIT, BLOCK, YEAR, Y_TOTAL_ton FROM OILPALM"
```

## Safety rules

- Only `SELECT` and `WITH` statements. One statement per call.
- No `INSERT`, `UPDATE`, `DELETE`, `MERGE`, `DROP`, `ALTER`, `CREATE`,
  `TRUNCATE`, `EXEC`, `GRANT`, `REVOKE`, `BACKUP`, `RESTORE`, `INTO`,
  `OPENROWSET`, or `OPENQUERY`.
- Use explicit column lists, not `SELECT *`, for extraction.
- Keep result sets small with `TOP`/`--limit` while exploring.
- The pipeline account must be read-only. `sa` is only for local bootstrap and
  for creating `omp_ds_readonly`.
- Never put credentials in notebooks, reports, or committed files.

## Core schema map

| Table | Grain | Join keys | Use |
|---|---|---|---|
| `OILPALM` | block-year | `NAME`, `UNIT`, `BLOCK`, `YEAR` | target, static/site, stand, leaf, weather key |
| `tbl_FN_nutActRec` | block-year | `suEstate`, `suDivision`, `suBlock`, `Yr` | applied/recommended nutrients; management levers |
| `tbl_HRR_harvests` | block-harvest event | `Estate`, `UNIT`, `BLOCK`, `Y_Harvest` | lagged harvest intensity, rounds, losses |
| `tbl_PD_surveys` | block-survey | `ESTATE`, `UNIT`, `BLOCK`, `yrFis` | Ganoderma, crown disease, pest pressure |
| `tbl_PD_controlAct` | block-control event | `ESTATE`, `UNIT`, `BLOCK`, `yrFis` | disease felling intensity (2022-2025) |
| `tbl_PCD_pesticideAct_dt` | block-application event | `suEstate`, `suDivision`, `suBlock`, `yrFis` | weed control; 2025 only |
| `tbl_CW_weatherAndWater` | station-year | `R_Name`, `R_UNIT`, `R_YEAR` | rainfall, dry months, water deficit |
| `tbl_areasPalmsBIY_blk_mts` | block-year-month | `suEstate`, `suDivision`, `suBlock`, `Yr` | stand/age validation, future projections |
| `tbl_SC_palmCensus` | block-year | `suEstate`, `suDivision`, `suBlock`, `validFromYr` | stand validation/backfill |
| `tbl_planting` | block | `Estate`, `Unit`, `Block` | planting material, density, planting date |
| `tbl_FN_soilAnalysis` | block-year | `NAME`, `UNIT`, `BLOCK`, `YEAR` | soil pH/CEC/SOM/texture; sparse |
| `tbl_BBC_bunchCounts` | block-month | `Estate`, `Unit`, `Block`, `CntDate` | BlackBunch; 2023-2025 only |
| `tbl_BBC_forecastABW` | block-year-month | `suEstate`, `suDivision`, `suBlock`, `Yr` | OMP ABW forecast; 2023-2025, 2026 null |
| `tbl_CB_cropBudgetMt` | block-year | `NAME`, `UNIT`, `BLOCK`, `YEAR` | benchmark only; likely backfilled |
| `tbl_CLA_auditResults` | block-year | `NAME`, `UNIT`, `BLOCK`, `YEAR` | 2025 only, 61 blocks |

## Join-key normalization

| OILPALM | Other tables |
|---|---|
| `NAME` | `suEstate`, `Estate`, `ESTATE`, `R_Name` |
| `UNIT` | `suDivision`, `Unit`, `UNIT`, `R_UNIT` (weather station is different) |
| `BLOCK` | `suBlock`, `Block`, `BLOCK` |
| `YEAR` | `Yr`, `Y_Harvest`, `yrFis` |

Trim whitespace and compare case-insensitively. Verify match rates; do not
assume a join works because the column names look similar.

`OILPALM.ID_WeatherStation` joins to `tbl_CW_weatherAndWater.R_UNIT`
(`C01`, `N01`, `S01`, `S02`), not to `OILPALM.UNIT`.

## Maturity definitions

From `tbl_sys_growthPeriods`:

| Code | Ages | Meaning |
|---|---:|---|
| `IGP` | 0-2 | Immature growth phase |
| `SAYP` | 3-7 | Steep ascent yield phase |
| `PYP` | 8-15 | Plateau yield phase |
| `DYP` | 16-25 | Declining yield phase |

Mature model filter: `Growth_Period IN ('SAYP', 'PYP', 'DYP')` and
`YEAR <= 2025`. Do not use `palmStandMature_p > 0` as the primary filter.

## Known data quirks

- `OILPALM` has 2,909 rows; the 2026 row is a placeholder (target 0).
- 474 zero-yield rows are mostly `IGP`; 178 `IGP` rows have small positive
  yield and are documented anomalies.
- `204D` 2025 is mature but zero-yield; flag and keep by default.
- `124H` 2024/2025 has `areaIY_ha=0` but positive yield and
  `MarkerYield='0- No yield'`; flag and run a sensitivity check.
- `Y_TH`, `Y_KGB`, monthly `Y_*`, `Y_TH_GAP`, `Y_GAP_PERCENT`, and
  `Y_per_*` are target-derived. Do not use them as features.
- `tbl_CB_cropBudgetMt` is likely backfilled; use as a benchmark, not a feature.
- `tbl_BBC_forecastABW` has a single null 2026 row; it cannot support 2026.
- `RipeBunch`, `MaleFlowerNo`, and `FemaleFlowerNo` are all zero in
  `tbl_BBC_bunchCounts`; only `BlackBunch` has signal.
- `tbl_PCD_pesticideAct_dt` is 2025 only; use it for scenario inputs, not
  historical training features.

## Phase 0 read-only account

Use `sa` only to create this account:

```sql
CREATE LOGIN omp_ds_readonly WITH PASSWORD = '<strong-password>';
CREATE USER omp_ds_readonly FOR LOGIN omp_ds_readonly;
ALTER ROLE db_datareader ADD MEMBER omp_ds_readonly;
GRANT VIEW DEFINITION TO omp_ds_readonly;
```

Then set `OMP_DB_USER=omp_ds_readonly` and the password in `.env`, and verify:

```bash
uv run omp-yield db ping
uv run omp-yield db query "SELECT TOP 1 NAME FROM OILPALM"
```

A write attempt must fail.
