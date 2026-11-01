# Phase 3 — Cleaning and Feature Decisions

Status: **approved**

Snapshot: `data/raw/20261030T000000Z`  
Snapshot verified: **True**  
Target: `Y_TOTAL_ton` metric tons  
Mature periods: `SAYP`, `PYP`, `DYP`

## Population

| Slice | Rows |
|---|---:|
| All OILPALM rows | 2,909 |
| Usable 2019–2025 | 2,908 |
| Mature | 2,258 |
| Mature and positive target | 2,257 |
| Immature | 650 |
| 2026 placeholder | 1 |
| Flagged anomaly rows | 182 |

## Known anomalies

| flag | len |
|---|---|
| areaIY_zero_positive_yield | 2 |
| immature_positive_yield | 178 |
| mature_zero_yield | 1 |
| placeholder_2026 | 1 |

- `204D` 2025 has target `0` but HRR harvest FFB totals about `759 t`. Treat it
  as a source-data inconsistency; do not train on it without correction or an
  explicit exclusion decision.
- `124H` 2024/2025 has `areaIY_ha = 0` but positive target yield.
- 178 `IGP` rows have small positive yield despite being immature; they are
  excluded from the mature model and documented.
- The 2026 row is a placeholder.

## Target

| population | rows | zeros | negatives | min | p01 | median | mean | p99 | max | std |
|---|---|---|---|---|---|---|---|---|---|---|
| usable | 2908 | 473 | 0 | 0.0 | 0.0 | 565.7061500000001 | 529.002866127923 | 1364.8776 | 1747.6692 | 434.7053861130667 |
| mature | 2258 | 1 | 0 | 0.0 | 17.1786 | 754.94515 | 680.2310966784764 | 1389.4343000000001 | 1747.6692 | 375.497105384755 |
| mature_positive | 2257 | 0 | 0 | 7.769299999999999 | 17.468000000000004 | 755.1996 | 680.5324839610103 | 1389.4343000000001 | 1747.6692 | 375.3070483600363 |

### Target by year

| YEAR | rows | zeros | mean_ton | median_ton | total_ton |
|---|---|---|---|---|---|
| 2019 | 252 | 0 | 777.6866146825397 | 837.7290999999999 | 195977.0269 |
| 2020 | 255 | 0 | 816.9724258823529 | 851.7998 | 208327.9686 |
| 2021 | 265 | 0 | 808.2683837735849 | 847.0983 | 214191.1217 |
| 2022 | 273 | 0 | 789.3877915750916 | 826.5549 | 215502.8671 |
| 2023 | 311 | 0 | 698.6873151125402 | 768.8823000000001 | 217291.755 |
| 2024 | 404 | 0 | 569.6418462871287 | 617.4030499999999 | 230135.3059 |
| 2025 | 498 | 1 | 511.11600622489965 | 438.7025 | 254535.7711 |

## Missingness

Top partially-missing mature columns (excluding the fully empty columns that are
dropped automatically):

| column_name | dtype | missing_pct | distinct_count | constant |
|---|---|---|---|---|
| Supervisor | String | 99.9 | 1 | True |
| SA_TextClass | String | 99.4 | 4 | False |
| SH_GROUPmember | String | 95.7 | 15 | False |
| marker1 | String | 91.9 | 4 | False |
| AblStart | Datetime(time_unit='us', time_zone=None) | 91.2 | 62 | False |
| AblEnd | Datetime(time_unit='us', time_zone=None) | 91.2 | 62 | False |
| marker2 | String | 89.7 | 1 | True |
| LA_Remark | String | 87.6 | 9 | False |
| LA_leaf_ProdRate | Float64 | 85.0 | 105 | False |
| LA_Leaf_Prod | Float64 | 85.0 | 105 | False |
| LA_METHOD | String | 63.2 | 1 | True |
| LA_VN | Int64 | 56.9 | 3 | False |
| LA_VB | Int64 | 52.0 | 4 | False |
| LA_VMG | Int64 | 49.0 | 4 | False |
| LA_tree_height | Float64 | 47.5 | 531 | False |
| LA_tree_heightIncrement | Float64 | 47.5 | 829 | False |
| LA_VK | Int64 | 46.8 | 4 | False |
| LA_LABNAME | String | 39.1 | 1 | True |
| LA_cross_section | Float64 | 29.3 | 1244 | False |
| markerFert | String | 24.9 | 96 | False |
| HarvesterAccess | String | 24.1 | 4 | False |
| Pruning | String | 22.9 | 5 | False |
| LA_DATE | Datetime(time_unit='us', time_zone=None) | 17.1 | 31 | False |
| LA_LABNO | String | 17.1 | 1078 | False |
| LA_FROND | Float64 | 11.4 | 3 | False |

## Duplicates and key checks

| check | table | rows | duplicate_rows | key_columns |
|---|---|---|---|---|
| OILPALM business key | OILPALM | 2909 | 0 | NAME, UNIT, BLOCK, YEAR |
| OILPALM exact duplicate rows | OILPALM | 2909 | 0 |  |
| Phase 1 candidate key | OILPALM | 2909 | 0 | NAME, UNIT, BLOCK, YEAR |
| Phase 1 candidate key | tbl_areasPalmsBIY_blk_mts | 2909 | 0 | suEstate, suDivision, suBlock, Yr |
| Phase 1 candidate key | tbl_BBC_bunchCounts | 8316 | 0 | Estate, Unit, Block, CntDate |
| Phase 1 candidate key | tbl_BBC_forecastABW | 1653 | 0 | suEstate, suDivision, suBlock, Yr |
| Phase 1 candidate key | tbl_CB_cropBudgetMt | 2908 | 0 | NAME, UNIT, BLOCK, YEAR |
| Phase 1 candidate key | tbl_CLA_auditResults | 1762 | 0 | NAME, UNIT, BLOCK, YEAR, AuditDate, Row_1, Row_2 |
| Phase 1 candidate key | tbl_CW_weatherAndWater | 29 | 0 | R_Name, R_UNIT, R_YEAR |
| Phase 1 candidate key | tbl_FN_fertActInorg_mts | 10626 | 0 | suEstate, suDivision, suBlock, Yr, fertName, fertAppMeth |
| Phase 1 candidate key | tbl_FN_fertActOrg_mts | 253 | 0 | suEstate, suDivision, suBlock, Yr, fertName, fertAppMeth |
| Phase 1 candidate key | tbl_FN_fertRecInorg_mts | 10951 | 0 | suEstate, suDivision, suBlock, Yr, fertName, fertAppMeth |
| Phase 1 candidate key | tbl_FN_fertRecOrg_mts | 147 | 0 | suEstate, suDivision, suBlock, Yr, fertName, fertAppMeth |
| Phase 1 candidate key | tbl_FN_nutActRec | 2909 | 0 | suEstate, suDivision, suBlock, Yr |
| Phase 1 candidate key | tbl_FN_soilAnalysis | 671 | 0 | NAME, UNIT, BLOCK, SA_DATE, SA_TYPE |
| Phase 1 candidate key | tbl_GIS_blocks | 2870 | 0 | Yr, suEstate, suDivision, suBlock, fragmentIdx |
| Phase 1 candidate key | tbl_HRR_harvests | 74986 | 0 | Estate, UNIT, BLOCK, ID_Card, D_Harvest |
| Phase 1 candidate key | tbl_PCD_pesticideAct_dt | 2369 | 0 | suEstate, suDivision, suBlock, pcdAppDt, pcdProdName, pestEventID |
| Phase 1 candidate key | tbl_PCD_pesticideRec_mts | 2211 | 0 | suEstate, suDivision, suBlock, Yr, pcdProdName |
| Phase 1 candidate key | tbl_PD_controlAct | 812 | 0 | ESTATE, UNIT, BLOCK, ID_Rep, Dt_App, Control_Name |
| Phase 1 candidate key | tbl_PD_surveys | 8132 | 0 | ESTATE, UNIT, BLOCK, ID_Rep, D_Survey, PestName |
| Phase 1 candidate key | tbl_planting | 557 | 0 | Estate, Unit, Block, plantingCycle |
| Phase 1 candidate key | tbl_SC_areas | 1130 | 0 | suEstate, suDivision, suBlock, validFromYr, validFromMt |
| Phase 1 candidate key | tbl_SC_palmCensus | 2908 | 0 | suEstate, suDivision, suBlock, validFromYr, validFromMt |
| Phase 1 candidate key | tbl_suDivisions | 9 | 0 | suEstate, suDivision |
| Phase 1 candidate key | tbl_suFields | 68 | 0 | suEstate, suDivision, suField |

## Leakage checks

| check | max_abs_diff | tolerance | status |
|---|---|---|---|
| Y_TH = Y_TOTAL_ton / area_ha | 2.1316282072803006e-14 | 1e-06 | pass |
| Y_KGB = 1000 * Y_TOTAL_ton / Y_TOTAL_bunches | 0.0 | 1e-06 | pass |
| Y_TH_GAP = Y_TH - Y_TH_POT | 0.0 | 1e-06 | pass |
| Y_GAP_Percent = 100 * (Y_TH - Y_TH_POT) / Y_TH_POT | 1.4210854715202004e-14 | 1e-06 | pass |
| Y_TOTAL_ton = sum monthly ton | 4.547473508864641e-13 | 1e-06 | pass |
| Y_TOTAL_bunches = sum monthly bunches | 0.0 | 1e-06 | pass |
| Y_TOTAL_mandays = sum monthly mandays | 9.094947017729282e-13 | 1e-06 | pass |
| Y_per_manday = Y_TOTAL_ton / Y_TOTAL_mandays | 0.0 | 1e-06 | pass |
| Y_BNTREE ~= Y_TOTAL_bunches / palmStandMature_p | 0.21046416121004263 | 0.5 | pass |

Leakage rules: all current-year `Y_*` fields are excluded from candidate
features. `Y_TH`, `Y_KGB`, monthly totals, `Y_TH_GAP`, `Y_GAP_Percent`,
`Y_per_manday`, and `Y_BNTREE` are confirmed target-derived. `Y_TH_POT` and
`MarkerYield` were reviewed and are approved as `drop`.

## Domain checks

| check | rows |
|---|---|
| target zero | 1 |
| target negative | 0 |
| area_ha <= 0 | 0 |
| tree age < 3 | 0 |
| tree age > 30 | 0 |
| yield per ha > 40 | 0 |
| mature stand > total stand | 9 |

## Outliers

Top numeric IQR outliers:

| column_name | missing_pct | outlier_count | outlier_pct | q1 | q3 | lower | upper |
|---|---|---|---|---|---|---|---|
| Y_TH_POT | 0.0 | 482 | 21.3 | 28.6 | 31.1 | 24.85 | 34.85 |
| Y_TH | 0.1 | 441 | 19.5 | 24.13755748594788 | 27.788745376955905 | 18.66077564943584 | 33.26552721346794 |
| palmStand_p_ha | 0.0 | 427 | 18.9 | 130.8638272345531 | 132.8711727325246 | 127.85280898759585 | 135.88219097948183 |
| Y_GAP_Percent | 0.1 | 279 | 12.4 | -18.980716253443514 | -11.438967065417218 | -30.29334003548296 | -0.12634328337777312 |
| Y_BNTREE | 0.1 | 254 | 11.3 | 8.582720588235293 | 10.841459137144861 | 5.194612764870942 | 14.229566960509214 |
| Y_03_mandays | 0.0 | 214 | 9.5 | 19.4 | 46.5 | -21.250000000000007 | 87.15 |
| Y_11_mandays | 0.0 | 205 | 9.1 | 21.099999999999998 | 44.9 | -14.600000000000005 | 80.6 |
| Y_12_mandays | 0.0 | 204 | 9.0 | 18.6 | 42.6 | -17.4 | 78.6 |
| Y_01_mandays | 0.0 | 200 | 8.9 | 16.5 | 41.300000000000004 | -20.700000000000003 | 78.5 |
| Y_06_mandays | 0.0 | 200 | 8.9 | 22.0 | 47.599999999999994 | -16.39999999999999 | 85.99999999999999 |
| Y_02_mandays | 0.0 | 198 | 8.8 | 17.6 | 40.800000000000004 | -17.200000000000003 | 75.60000000000001 |
| Y_TOTAL_mandays | 0.0 | 197 | 8.7 | 268.2 | 544.5 | -146.25000000000006 | 958.95 |
| Y_04_mandays | 0.0 | 197 | 8.7 | 20.8 | 46.6 | -17.900000000000002 | 85.30000000000001 |
| Y_08_mandays | 0.0 | 196 | 8.7 | 23.400000000000002 | 52.7 | -20.55 | 96.65 |
| Y_05_mandays | 0.0 | 191 | 8.5 | 20.3 | 47.2 | -20.05 | 87.55000000000001 |
| Y_10_mandays | 0.0 | 193 | 8.5 | 22.5 | 50.699999999999996 | -19.799999999999997 | 93.0 |
| Y_07_mandays | 0.0 | 190 | 8.4 | 22.7 | 51.19999999999999 | -20.049999999999986 | 93.94999999999997 |
| Y_09_mandays | 0.0 | 188 | 8.3 | 21.8 | 48.9 | -18.849999999999998 | 89.55 |
| LA_VMG | 49.0 | 82 | 7.1 | 0.0 | 1.0 | -1.5 | 2.5 |
| LA_tree_heightIncrement | 47.5 | 75 | 6.3 | 0.31375 | 0.425 | 0.14687499999999995 | 0.591875 |

Full table: `data/phase-3-cleaning/outliers.csv`.

## Consistency checks

| check | rows_checked | failing_rows | max_abs_diff | max_rel_diff |
|---|---|---|---|---|
| tree age vs planting year | 2258 | 228 | 1.0 |  |
| area_ha vs areaIY_ha | 2258 | 2 | 4.520000000000001 |  |
| OILPALM target vs HRR harvest FFB | 2258 | 10 | 759.0098 | 0.14631813422039028 |

## Numeric signal

Top associations with the mature target (Pearson):

| feature | pearson_r | abs_r | n |
|---|---|---|---|
| palmStandMature_p | 0.9056806765798319 | 0.9056806765798319 | 2258 |
| area_ha | 0.8907141858870967 | 0.8907141858870967 | 2258 |
| LA_LSU | 0.8753292764162207 | 0.8753292764162207 | 2258 |
| D_TREEAGE | 0.747542562254183 | 0.747542562254183 | 2258 |
| LA_tree_height | 0.7139178558745032 | 0.7139178558745032 | 1185 |
| palmStand_p_ha | -0.7077616339351872 | 0.7077616339351872 | 2258 |
| TC_DENS | -0.639538958602172 | 0.639538958602172 | 2258 |
| LA_cross_section | 0.6333013619028499 | 0.6333013619028499 | 1596 |
| LA_P | -0.5646672018366536 | 0.5646672018366536 | 2258 |
| IsAbblation | 0.45189000491174663 | 0.45189000491174663 | 2258 |
| LA_Zn | -0.367725464543115 | 0.367725464543115 | 2258 |
| AblReps | -0.33225260395013323 | 0.33225260395013323 | 2258 |
| LA_K | -0.3263096910786898 | 0.3263096910786898 | 2258 |
| LA_TLB | -0.2864053885466426 | 0.2864053885466426 | 2258 |
| ALTITUDE | 0.20217849621341435 | 0.20217849621341435 | 2258 |
| LA_tree_heightIncrement | 0.20146429091967694 | 0.20146429091967694 | 1185 |
| LA_PK | -0.18560046831421712 | 0.18560046831421712 | 2258 |
| LA_N | -0.18544243322771128 | 0.18544243322771128 | 2258 |
| LA_PCRIT | -0.18544243322771123 | 0.18544243322771123 | 2258 |
| LA_Mg | -0.17630324579989282 | 0.17630324579989282 | 2258 |
| LA_leaf_ProdRate | -0.10124264880150559 | 0.10124264880150559 | 338 |
| LA_Leaf_Prod | -0.10124264880150553 | 0.10124264880150553 | 338 |
| areaHCV_ha | 0.0894703591187545 | 0.0894703591187545 | 2258 |
| LA_PMG | -0.03257618826444091 | 0.03257618826444091 | 2258 |
| LA_Mn | -0.02340536691723544 | 0.02340536691723544 | 2258 |

High-VIF features (top 20):

| feature | vif |
|---|---|
| LA_N | inf |
| LA_PCRIT | inf |
| LA_leaf_ProdRate | inf |
| LA_Leaf_Prod | inf |
| area_ha | 1526.198251324302 |
| LA_LSU | 1462.5528031055453 |
| LA_K | 232.08984723393095 |
| LA_Mg | 230.66144338625224 |
| LA_TLB | 217.05299469531417 |
| LA_PK | 139.83850725576775 |
| LA_PMG | 139.30160173931273 |
| palmStand_p_ha | 78.13816090039397 |
| TC_DENS | 44.02737730341308 |
| D_TREEAGE | 15.323904546244705 |
| palmStandMature_p | 10.857973480489624 |
| AblReps | 4.205408247324677 |
| IsAbblation | 4.109551446415565 |
| LA_P | 2.2084074083726613 |
| LA_cross_section | 2.1039588905901567 |
| LA_tree_height | 1.7634451653064143 |

High-correlation pairs (`|r| >= 0.95`):

| feature_a | feature_b | pearson_r |
|---|---|---|
| LA_N | LA_PCRIT | 0.9999999999999997 |
| LA_leaf_ProdRate | LA_Leaf_Prod | 0.999999999999999 |
| area_ha | LA_LSU | 0.9989542485483466 |
| palmStand_p_ha | TC_DENS | 0.9631609175477517 |

## Derived feature provenance

These candidate features are **not raw database columns**. They are planned
derivations from `tbl_HRR_harvests`. The derivation must be implemented and
tested in Phase 4; it is not a direct table field.

| feature | derived_from | derivation |
|---|---|---|
| rain_annual_mm | tbl_CW_weatherAndWater.R_Total Rainfall | Renamed/standardized annual rainfall; equivalent to sum(R_rain_mm_1..12) |
| dry_months | tbl_CW_weatherAndWater.R_NO_dry_month | Renamed raw dry-month count |
| water_deficit | tbl_CW_weatherAndWater.R_waterdeficit | Renamed raw water-deficit field |
| yield_lag1 | OILPALM.Y_TOTAL_ton | Y_TOTAL_ton shifted 1 year within block; equivalent to prior-year HRR harvest FFB |
| bunch_weight_lag1 | OILPALM.Y_KGB | Y_KGB shifted 1 year within block; Y_KGB = 1000 * Y_TOTAL_ton / Y_TOTAL_bunches; alternative from tbl_HRR_harvests sum(Y_FFB)/sum(Y_BunchNo) |
| harvest_interval_lag1 | OILPALM.Y_AVG_harvest_int | Y_AVG_harvest_int shifted 1 year within block; alternative from tbl_HRR_harvests mean(prevRoundLength_d) or gaps between distinct D_Harvest dates |
| ganoderma_affected_area | tbl_PD_surveys.P_AffectedArea or AffectedArea filtered to PestName='Ganoderma' | Aggregate affected area by block-year; confirm whether P_AffectedArea or AffectedArea is the intended unit |
| ganoderma_severity | tbl_PD_surveys.P_Severity filtered to PestName='Ganoderma' | Aggregate severity by block-year (max or mean) |
| soil_ph | tbl_FN_soilAnalysis.SA_PH_H2O | Renamed H2O pH; alternative SA_PH_KCl |
| soil_cec | tbl_FN_soilAnalysis.SA_CEC | Renamed CEC; alternative ECEC (effective CEC) |
| soil_som | tbl_FN_soilAnalysis.SA_SOM | Renamed soil organic matter |
| black_bunch_per_palm | tbl_BBC_bunchCounts.BlackBunch / NoOfPalm | Per-survey bunch count per palm; aggregate to block-year by mean or latest survey before the cutoff |
| crop_budget_ton | tbl_CB_cropBudgetMt.Y_total_ton_bud | Renamed budget total; benchmark only |
| abw_forecast | tbl_BBC_forecastABW.ABWMt1_kg..ABWMt12_kg | Average or selected-month ABW forecast; benchmark/test only |

## Feature decisions

Decision counts:

| decision | len |
|---|---|
| drop | 168 |
| keep | 61 |
| target | 1 |

- Feature decisions: `config/features.yaml` (approved)
- Management levers: `config/management_levers.yaml` (approved)
- Full decision table: `data/phase-3-cleaning/feature_decisions.csv`

The feature list is approved; no review decisions remain. Re-running
`omp-yield clean` preserves existing edited configs and writes regenerated
drafts as `*.generated.yaml`; use `--overwrite-config` only when you
intentionally want to replace them.

### Review decisions

| source | name | role | missing_pct | reason |
|---|---|---|---|---|

## Management levers

| lever | decision | reason |
|---|---|---|
| nutActInorgN_kg_p | keep | Primary nutrient management lever. |
| nutActInorgP2O5_kg_p | keep | Primary nutrient management lever. |
| nutActInorgK2O_kg_p | keep | Primary nutrient management lever. |
| nutActInorgMgO_kg_p | keep | Primary nutrient management lever. |
| nutActInorgCaO_kg_p | keep | Primary nutrient management lever. |
| nutActInorgB_kg_p | keep | Primary nutrient management lever. |
| nutRecInorgN_kg_p | drop | Confirm recommendation/organic input availability and operational meaning. |
| nutRecInorgP2O5_kg_p | drop | Confirm recommendation/organic input availability and operational meaning. |
| nutRecInorgK2O_kg_p | drop | Confirm recommendation/organic input availability and operational meaning. |
| nutActOrgN_kg_p | keep | Primary nutrient management lever. |
| nutActOrgP2O5_kg_p | keep | Primary nutrient management lever. |
| nutActOrgK2O_kg_p | keep | Primary nutrient management lever. |
| Pruning | keep | Operational management lever. |
| HarvesterAccess | keep | Operational management lever. |
| harvest_interval_target_d | keep | Target-derived in-year field; only a lagged operational lever is safe. |
| disease_control_felling | drop | Only 2022-2025 coverage; confirm operational interpretation. |
| weed_control_intensity | drop | 2025-only data; scenario-only lever until more history exists. |
| replanting_ablation | drop | Sparse intervention; test before exposing in what-if. |

## Interim data

- `data/interim/phase-3/oilpalm_mature.parquet`
- `data/interim/phase-3/oilpalm_mature_positive.parquet`
- `data/interim/phase-3/oilpalm_anomalies.parquet`

These are intermediate artifacts. The final modeling table is built in Phase 4
after feature approval.

## Approval checklist

- [x] Confirm mature filter: `SAYP`, `PYP`, `DYP`
- [x] Confirm target: `Y_TOTAL_ton` in metric tons
- [x] Resolve every `review` feature in `config/features.yaml`
- [x] Approve or edit `config/management_levers.yaml`
- [x] Confirm `Y_TH_POT` and `MarkerYield` timing/source
- [x] Confirm sparse features (`LA_tree_height`, soil analysis, bunch counts)
