# Phase 4 Feature Engineering Summary

Status: **complete**

This document describes every feature family and every feature column in the
Phase 4 modeling table. The authoritative machine-readable list is
`data/processed/feature_schema.csv`; this document explains the intent behind
that schema.

## 1. Model mapping and cutoffs

The target is `OILPALM.Y_TOTAL_ton` in metric tons. The modeling panel contains
2,258 mature block-years (`YEAR <= 2025`,
`Growth_Period IN ('SAYP','PYP','DYP')`). The 2026 placeholder is excluded.

The same block panel feeds the following model uses:

| Model use | Features | Cutoff / information set |
|---|---|---|
| Pre-season yield prediction | 107 `pre_*` features | Data through 31 Dec of `t-1`. |
| Mid-season yield prediction | 132 features = 107 `pre_*` + 25 `mid_*` | Pre-season data plus current-year records with date `<= 30 Jun` of `t` (configurable in `config/transforms.yaml`). |
| Hierarchical yield forecasting | Pre-season `pre_*` features, plus management levers for scenarios | Block-panel predictions aggregated through `UNIT` to `NAME`. Mid-season-only `mid_*` features are for within-season forecast updates, not future horizon years. |
| What-if / scenario layer | Features with `adjustable = true` | Management levers only: nutrient rates, pruning, harvester access, harvest interval, and the derived N/K balance. Weather, soil, age, stand, leaf, pest, history, and context are read-only. |

`pre_*` columns are available at both cutoffs. `mid_*` columns are
mid-season-only. The mid-season view is `pre_* + mid_*`; no feature is moved
between cutoffs.

## 2. How features were selected

The feature list comes from the approved Phase 3 decisions:

- `config/features.yaml`: 61 keep, 154 drop, 0 unresolved review.
- `config/management_levers.yaml`: 12 approved management levers, all retained.
- `config/transforms.yaml`: approved cutoff, encoding, and derived-feature
  parameters.

Selection rules:

- Keep non-leaky features with acceptable variation, coverage, and domain
  relevance.
- Drop current-year target-derived fields, identifiers, constants, structurally
  redundant fields, and fields with no useful signal.
- Keep management levers even when marginal predictive importance is low,
  because they are the what-if controls.
- Do not use future records. Prior-year history is allowed only through explicit
  lag names.
- Preserve missing values in the modeling table. Imputation is a model-specific
  Phase 5/6 decision, not a Phase 4 transformation.

The 154 dropped decisions break down as:

| Drop reason | Count |
|---|---:|
| Current-year leakage | 70 |
| Empty or constant | 48 |
| Redundant | 16 |
| Leaf with insufficient coverage | 5 |
| Explicit drop | 3 |
| No correlation / no information | 4 |
| Benchmark-only | 2 |
| Other sparse/minimal/missing-value reasons | 6 |

Examples of excluded current-year leakage include `Y_TH`, `Y_KGB`, the monthly
`Y_*` totals, `Y_TH_GAP`, `Y_GAP_Percent`, `Y_per_manday`, `Y_BNTREE`,
`Y_TH_POT`, and `MarkerYield`. `Y_TOTAL_ton` is the target, not a feature.

## 3. Feature families

| Group | Columns | Model use | Why this family is included |
|---|---:|---|---|
| context | 69 | Pre + Mid + forecast baseline | Site, planting, stand, soil type, topography, land history, mill, and fertilizer-program context define the block's yield potential. |
| management | 18 | Pre + Mid + forecast baseline; what-if lever | Nutrient applications, pruning, harvester access, and prior-year harvest interval are the controllable inputs. |
| leaf | 24 | Mid-season only | Mid-season leaf nutrient and vegetative status are leading indicators of bunch formation and current yield potential. |
| history | 8 | Pre + Mid + forecast baseline | Block yield has strong year-to-year persistence; lags, rolling means, harvest outcomes, and hierarchical aggregates capture that memory. |
| weather | 5 | Pre + Mid + forecast baseline | Prior-year rainfall, dry months, water deficit, and anomalies capture water stress and drought exposure. |
| soil | 4 | Pre + Mid + forecast baseline | Soil pH, CEC, organic matter, and the CEC/SOM ratio describe nutrient-holding capacity and site response. |
| pest | 3 | Pre + Mid + forecast baseline | Ganoderma affected area and severity capture chronic disease pressure and stand decline. |
| leading indicator | 1 | Mid-season only | Black bunch per palm is an early bunch-formation signal available only after surveys. |

## 4. Context and management features

### 4.1 Numeric and date context

| Source field | Output column | Model use | Transformation | Why |
|---|---|---|---|---|
| `OILPALM.area_ha` | `pre_area_ha` | Pre + Mid + forecast baseline | Direct numeric copy. | Block size scales total yield and harvest logistics. |
| `OILPALM.D_PLANTED` | `pre_planting_year` | Pre + Mid + forecast baseline | Extract calendar year. | Planting cohort identifies the age/development phase. |
| `OILPALM.D_TREEAGE` | `pre_tree_age` | Pre + Mid + forecast baseline | Direct numeric copy. | Yield follows a pronounced age curve. |
| `OILPALM.palmStand_p_ha` | `pre_stand_per_ha` | Pre + Mid + forecast baseline | Direct numeric copy. | Stand density affects competition, light capture, and yield per hectare. |
| `OILPALM.palmStandMature_p` | `pre_stand_mature` | Pre + Mid + forecast baseline | Direct numeric copy. | Mature stand count scales productive capacity. |
| `OILPALM.ALTITUDE` | `pre_altitude` | Pre + Mid + forecast baseline | Direct numeric copy. | Altitude is a proxy for climate and site potential. |
| `OILPALM.AblReps` | `pre_ablation_reps` | Pre + Mid + forecast baseline | Direct numeric copy. | Ablation/replanting history affects stand and future yield. |
| `OILPALM.palmStandMature_p`, `palmStand_p` | `pre_mature_fraction` | Pre + Mid + forecast baseline | `palmStandMature_p / palmStand_p`, null when the denominator is zero. | Fractions the stand that is productive, independent of block size. |

### 4.2 Ordinal and one-hot encodings

Ordinal features preserve the order where the domain has a meaningful order:

| Source | Output | Mapping | Model use | Why |
|---|---|---|---|---|
| `OILPALM.Growth_Period` | `pre_growth_period_code` | `SAYP=0`, `PYP=1`, `DYP=2` | Pre + Mid + forecast baseline | Ordered maturity phase; captures the transition from young to fully productive palms. |
| `OILPALM.HarvesterAccess` | `pre_harvester_access_code` | `None=0`, `Incomplete=1`, `Full=2` | Pre + Mid + forecast baseline; what-if lever | Ordered access constraint; better access allows timely harvest. |
| `OILPALM.HarvesterAccess` | `pre_harvester_access_known` | 1 when the value is one of the three categories | Pre + Mid + forecast baseline; what-if lever | Separates a real constraint from missing/placeholder data. |
| `OILPALM.Pruning` | `pre_pruning_known` | 1 when the value is `Correct`, `Neglected`, `Over`, or `Under` | Pre + Mid + forecast baseline; what-if lever | Separates a recorded pruning state from missing data. |

Low-cardinality categorical families are one-hot encoded. Each category becomes
its own 0/1 column; `No data`, blank, and null values produce all-zero rows
unless a `*_known` flag is present. The exact columns are listed below and again
in the appendix.

| Source family | Categories | Generated columns | Model use | Why chosen |
|---|---|---|---|---|
| `LandClass` (12) | LC1_Marihat_135, LC1_Marihat_143, LC1_Other_135, LC1_Other_143, LC2_Marihat_135, LC2_Marihat_143, LC2_Other_135, LC2_Other_143, LC3_Marihat_135, LC3_Marihat_143, LC3_Other_135, LC3_Other_143 | `pre_LandClass_lc1_marihat_135`, `pre_LandClass_lc1_marihat_143`, `pre_LandClass_lc1_other_135`, `pre_LandClass_lc1_other_143`, `pre_LandClass_lc2_marihat_135`, `pre_LandClass_lc2_marihat_143`, `pre_LandClass_lc2_other_135`, `pre_LandClass_lc2_other_143`, `pre_LandClass_lc3_marihat_135`, `pre_LandClass_lc3_marihat_143`, `pre_LandClass_lc3_other_135`, `pre_LandClass_lc3_other_143` | Pre + Mid + forecast baseline | Land suitability/classification; captures site productivity and soil-land constraints. |
| `SOILTYPE` (3) | Acrisol, Andosol, Gleysol | `pre_SOILTYPE_acrisol`, `pre_SOILTYPE_andosol`, `pre_SOILTYPE_gleysol` | Pre + Mid + forecast baseline | Soil parent material and fertility/water behavior; broad site potential. |
| `TOPOGRAPHY` (4) | Flat, Hilly, Sloping, Steep | `pre_TOPOGRAPHY_flat`, `pre_TOPOGRAPHY_hilly`, `pre_TOPOGRAPHY_sloping`, `pre_TOPOGRAPHY_steep` | Pre + Mid + forecast baseline | Slope and relief affect drainage, erosion, and harvest access. |
| `PREV_CROP` (4) | 2nd forest, Coconut, Prim forest, Scrub/beluka | `pre_PREV_CROP_2nd_forest`, `pre_PREV_CROP_coconut`, `pre_PREV_CROP_prim_forest`, `pre_PREV_CROP_scrub_beluka` | Pre + Mid + forecast baseline | Previous land use leaves different soil organic matter and nutrient legacies. |
| `LANDCLEARING` (3) | Full Man, Full Mech, Manfell Mechrow | `pre_LANDCLEARING_full_man`, `pre_LANDCLEARING_full_mech`, `pre_LANDCLEARING_manfell_mechrow` | Pre + Mid + forecast baseline | Clearing method affects soil disturbance, compaction, and establishment. |
| `Erosion` (4) | Moderate, No erosion, Severe, Slight | `pre_Erosion_moderate`, `pre_Erosion_no_erosion`, `pre_Erosion_severe`, `pre_Erosion_slight` | Pre + Mid + forecast baseline | Erosion state reflects soil depth and fertility loss. |
| `Soil_Consv` (5) | Bunding, None, Platform, Silt traps, Terrace | `pre_Soil_Consv_bunding`, `pre_Soil_Consv_none`, `pre_Soil_Consv_platform`, `pre_Soil_Consv_silt_traps`, `pre_Soil_Consv_terrace` | Pre + Mid + forecast baseline | Conservation practice affects soil and water retention. |
| `GroundCover` (5) | < 50 % LCP, > 50 % LCP, Bare soil, Hard weeds, Soft weeds | `pre_GroundCover_lt_50_lcp`, `pre_GroundCover_gt_50_lcp`, `pre_GroundCover_bare_soil`, `pre_GroundCover_hard_weeds`, `pre_GroundCover_soft_weeds` | Pre + Mid + forecast baseline | Ground cover and weed state affect competition, soil cover, and moisture. |
| `Drainage` (4) | Poorly drained, Seasonal flood, Waterlogged, Well drained | `pre_Drainage_poorly_drained`, `pre_Drainage_seasonal_flood`, `pre_Drainage_waterlogged`, `pre_Drainage_well_drained` | Pre + Mid + forecast baseline | Drainage class captures waterlogging and root-health risk. |
| `Pruning` (4) | Correct, Neglected, Over, Under | `pre_Pruning_correct`, `pre_Pruning_neglected`, `pre_Pruning_over`, `pre_Pruning_under`, `pre_pruning_known` | Pre + Mid + forecast baseline; what-if lever | Pruning is an approved management lever affecting canopy health and harvest access. |
| `MillName` (3) | Mill C, Mill N, Mill S | `pre_MillName_mill_c`, `pre_MillName_mill_n`, `pre_MillName_mill_s` | Pre + Mid + forecast baseline | Mill/estate logistics and local site context. |
| `TC_PMAT` (4) | ASD, Marihat, Mixed, Socfindo | `pre_TC_PMAT_asd`, `pre_TC_PMAT_marihat`, `pre_TC_PMAT_mixed`, `pre_TC_PMAT_socfindo` | Pre + Mid + forecast baseline | Terrain/soil parent-material context for site potential. |

`markerFert` is a high-cardinality free-text field (97 observed values). It is
not one-hot encoded. Instead it is reduced to:

| Output column | Derivation | Model use | Why |
|---|---|---|---|
| `pre_marker_fert_product_count` | Number of semicolon-separated products; 0 when unknown. | Pre + Mid + forecast baseline | Captures fertilizer-program breadth without 97 dummy columns. |
| `pre_marker_fert_known` | 1 when the text is non-empty and not `No data`. | Pre + Mid + forecast baseline | Distinguishes unknown from a genuine no-product record. |
| `pre_marker_fert_has_urea` | 1 when the text contains `Urea`. | Pre + Mid + forecast baseline | Nitrogen program context. |
| `pre_marker_fert_has_kcl` | 1 when the text contains `KCL`. | Pre + Mid + forecast baseline | Potassium program context. |
| `pre_marker_fert_has_rp` | 1 when the text contains `RP`. | Pre + Mid + forecast baseline | Phosphorus program context. |
| `pre_marker_fert_has_kieserite` | 1 when the text contains `Kieserite`. | Pre + Mid + forecast baseline | Magnesium/sulfur program context. |
| `pre_marker_fert_has_borate` | 1 when the text contains `Borate`. | Pre + Mid + forecast baseline | Boron program context. |
| `pre_marker_fert_has_efb` | 1 when the text contains `EFB`. | Pre + Mid + forecast baseline | Organic-matter/nutrient program context. |
| `pre_marker_fert_has_compound` | 1 when the text contains `12:12:17`. | Pre + Mid + forecast baseline | Balanced compound-fertilizer program context. |

## 5. Management levers

The management features are all `adjustable = true` and are the only features
that what-if tools may change:

- Inorganic N, P2O5, K2O, MgO, CaO, and B rates (`nutActInorg*_kg_p`).
- Organic N, P2O5, and K2O rates (`nutActOrg*_kg_p`).
- Pruning: four one-hot states plus `pre_pruning_known`.
- Harvester access: ordinal code plus `pre_harvester_access_known`.
- Prior-year harvest interval: `pre_harvest_interval_lag1`.
- Derived N/K balance: `pre_nutrient_balance_NK`.

The nutrient rates are joined from `tbl_FN_nutActRec` by
`(suEstate, suDivision, suBlock, Yr)`. The approved decision treats them as
pre-season levers. `nutRec*` recommendation fields are not model features; the
approved feature config marks them as drop.

Why these help: nutrient supply and balance drive bunch initiation, fruit
development, and yield response; pruning and harvester access affect canopy
health and harvest recovery; the prior-year harvest interval captures
operational intensity without using the current-year target-derived
`Y_AVG_harvest_int`.

## 6. Leaf features (mid-season only)

Leaf features are current-year `LA_*` measurements. A value is included only
when `LA_DATE` is in the current year and `LA_DATE <= 30 Jun`; otherwise the
mid-season value is null. They are not available to the pre-season model or to
future forecast years.

| Output column | Source field | Cutoff rule | Why it helps |
|---|---|---|---|
| `mid_LA_N` | `LA_N` | Latest current-year leaf sample with `LA_DATE <= 30 Jun`; null otherwise. | Mid-season leaf nutrient/vegetative status; current nutritional balance and canopy condition are leading indicators of bunch formation and yield. |
| `mid_LA_P` | `LA_P` | Latest current-year leaf sample with `LA_DATE <= 30 Jun`; null otherwise. | Mid-season leaf nutrient/vegetative status; current nutritional balance and canopy condition are leading indicators of bunch formation and yield. |
| `mid_LA_K` | `LA_K` | Latest current-year leaf sample with `LA_DATE <= 30 Jun`; null otherwise. | Mid-season leaf nutrient/vegetative status; current nutritional balance and canopy condition are leading indicators of bunch formation and yield. |
| `mid_LA_Ca` | `LA_Ca` | Latest current-year leaf sample with `LA_DATE <= 30 Jun`; null otherwise. | Mid-season leaf nutrient/vegetative status; current nutritional balance and canopy condition are leading indicators of bunch formation and yield. |
| `mid_LA_Mg` | `LA_Mg` | Latest current-year leaf sample with `LA_DATE <= 30 Jun`; null otherwise. | Mid-season leaf nutrient/vegetative status; current nutritional balance and canopy condition are leading indicators of bunch formation and yield. |
| `mid_LA_Cl` | `LA_Cl` | Latest current-year leaf sample with `LA_DATE <= 30 Jun`; null otherwise. | Mid-season leaf nutrient/vegetative status; current nutritional balance and canopy condition are leading indicators of bunch formation and yield. |
| `mid_LA_S` | `LA_S` | Latest current-year leaf sample with `LA_DATE <= 30 Jun`; null otherwise. | Mid-season leaf nutrient/vegetative status; current nutritional balance and canopy condition are leading indicators of bunch formation and yield. |
| `mid_LA_Mn` | `LA_Mn` | Latest current-year leaf sample with `LA_DATE <= 30 Jun`; null otherwise. | Mid-season leaf nutrient/vegetative status; current nutritional balance and canopy condition are leading indicators of bunch formation and yield. |
| `mid_LA_B` | `LA_B` | Latest current-year leaf sample with `LA_DATE <= 30 Jun`; null otherwise. | Mid-season leaf nutrient/vegetative status; current nutritional balance and canopy condition are leading indicators of bunch formation and yield. |
| `mid_LA_Cu` | `LA_Cu` | Latest current-year leaf sample with `LA_DATE <= 30 Jun`; null otherwise. | Mid-season leaf nutrient/vegetative status; current nutritional balance and canopy condition are leading indicators of bunch formation and yield. |
| `mid_LA_Zn` | `LA_Zn` | Latest current-year leaf sample with `LA_DATE <= 30 Jun`; null otherwise. | Mid-season leaf nutrient/vegetative status; current nutritional balance and canopy condition are leading indicators of bunch formation and yield. |
| `mid_LA_TLB` | `LA_TLB` | Latest current-year leaf sample with `LA_DATE <= 30 Jun`; null otherwise. | Mid-season leaf nutrient/vegetative status; current nutritional balance and canopy condition are leading indicators of bunch formation and yield. |
| `mid_LA_PK` | `LA_PK` | Latest current-year leaf sample with `LA_DATE <= 30 Jun`; null otherwise. | Mid-season leaf nutrient/vegetative status; current nutritional balance and canopy condition are leading indicators of bunch formation and yield. |
| `mid_LA_Rachis_N` | `LA_Rachis_N` | Latest current-year leaf sample with `LA_DATE <= 30 Jun`; null otherwise. | Mid-season leaf nutrient/vegetative status; current nutritional balance and canopy condition are leading indicators of bunch formation and yield. |
| `mid_LA_Rachis_P` | `LA_Rachis_P` | Latest current-year leaf sample with `LA_DATE <= 30 Jun`; null otherwise. | Mid-season leaf nutrient/vegetative status; current nutritional balance and canopy condition are leading indicators of bunch formation and yield. |
| `mid_LA_Rachis_K` | `LA_Rachis_K` | Latest current-year leaf sample with `LA_DATE <= 30 Jun`; null otherwise. | Mid-season leaf nutrient/vegetative status; current nutritional balance and canopy condition are leading indicators of bunch formation and yield. |
| `mid_LA_Rachis_Mg` | `LA_Rachis_Mg` | Latest current-year leaf sample with `LA_DATE <= 30 Jun`; null otherwise. | Mid-season leaf nutrient/vegetative status; current nutritional balance and canopy condition are leading indicators of bunch formation and yield. |
| `mid_LA_cross_section` | `LA_cross_section` | Latest current-year leaf sample with `LA_DATE <= 30 Jun`; null otherwise. | Mid-season leaf nutrient/vegetative status; current nutritional balance and canopy condition are leading indicators of bunch formation and yield. |
| `mid_LA_tree_heightIncrement` | `LA_tree_heightIncrement` | Latest current-year leaf sample with `LA_DATE <= 30 Jun`; null otherwise. | Mid-season leaf nutrient/vegetative status; current nutritional balance and canopy condition are leading indicators of bunch formation and yield. |
| `mid_LA_leaf_ProdRate` | `LA_leaf_ProdRate` | Latest current-year leaf sample with `LA_DATE <= 30 Jun`; null otherwise. | Mid-season leaf nutrient/vegetative status; current nutritional balance and canopy condition are leading indicators of bunch formation and yield. |

Four leaf ratios are derived from these values:

| Output column | Actual derivation | Original fields | Model use | Why |
|---|---|---|---|---|
| `mid_LA_NK_ratio` | `LA_N / LA_K` when `LA_K > 0` and both are non-null. | `OILPALM.LA_N`, `LA_K` | Mid-season only | N/K balance affects bunch formation and yield response. |
| `mid_LA_NP_ratio` | `LA_N / LA_P` when `LA_P > 0` and both are non-null. | `OILPALM.LA_N`, `LA_P` | Mid-season only | Captures relative N and P status. |
| `mid_LA_KMg_ratio` | `LA_K / LA_Mg` when `LA_Mg > 0` and both are non-null. | `OILPALM.LA_K`, `LA_Mg` | Mid-season only | K/Mg interaction affects photosynthesis and bunch development. |
| `mid_LA_CaMg_ratio` | `LA_Ca / LA_Mg` when `LA_Mg > 0` and both are non-null. | `OILPALM.LA_Ca`, `LA_Mg` | Mid-season only | Cation balance and leaf structural health context. |

## 7. Weather, soil, pest, history, and leading-indicator features

### 7.1 Prior-year weather

Weather is joined by `OILPALM.ID_WeatherStation =
tbl_CW_weatherAndWater.R_UNIT`; values from weather year `t-1` are attached to
block-year `t`. No current-year weather is used.

| Output column | Actual derivation | Original fields | Model use | Why |
|---|---|---|---|---|
| `pre_rain_annual_mm_lag1` | Prior-year `R_Total Rainfall` for the block's station. | `R_Total Rainfall`, `R_UNIT`, `R_YEAR` | Pre + Mid + forecast baseline | Water supply affects bunch initiation and yield. |
| `pre_dry_months_lag1` | Prior-year `R_NO_dry_month`. | `R_NO_dry_month` | Pre + Mid + forecast baseline | Dry-month count captures water stress. |
| `pre_water_deficit_lag1` | Prior-year `R_waterdeficit`. | `R_waterdeficit` | Pre + Mid + forecast baseline | Direct water-balance stress indicator. |
| `pre_rain_anomaly_lag1` | Prior-year rainfall minus the station's expanding mean through `t-2`. | `R_Total Rainfall`, station history | Pre + Mid + forecast baseline | Separates unusual wet/dry years from the station baseline. |
| `pre_rain_roll3_mean_lag1` | Mean rainfall over the three weather years ending in `t-1`. | `R_Total Rainfall` | Pre + Mid + forecast baseline | Smoother water context less sensitive to one anomalous year. |

### 7.2 Soil

Soil is joined from `tbl_FN_soilAnalysis` by block. The latest sample with
`SA_DATE <= 31 Dec of t-1` is used; later samples are excluded to respect the
pre-season cutoff.

| Output column | Actual derivation | Original fields | Model use | Why |
|---|---|---|---|---|
| `pre_soil_ph` | Latest prior-year `SA_PH_H2O`. | `SA_PH_H2O`, `SA_DATE` | Pre + Mid + forecast baseline | Soil acidity affects nutrient availability. |
| `pre_soil_cec` | Latest prior-year `SA_CEC`. | `SA_CEC`, `SA_DATE` | Pre + Mid + forecast baseline | Cation-exchange capacity indicates nutrient-holding ability. |
| `pre_soil_som` | Latest prior-year `SA_SOM`. | `SA_SOM`, `SA_DATE` | Pre + Mid + forecast baseline | Organic matter supports soil fertility and water retention. |
| `pre_soil_cec_som_ratio` | `soil_cec / soil_som` when `soil_som > 0`. | `SA_CEC`, `SA_SOM` | Pre + Mid + forecast baseline | Relative nutrient-holding capacity vs organic matter. |

### 7.3 Ganoderma pressure

Ganoderma surveys are filtered to `PestName = 'Ganoderma'`, aggregated to the
maximum `AffectedArea` and `P_Severity` per block-year, and then shifted so the
current row sees only pressure through `t-1`.

| Output column | Actual derivation | Original fields | Model use | Why |
|---|---|---|---|---|
| `pre_ganoderma_affected_area` | Prior-year maximum `AffectedArea`. | `tbl_PD_surveys.AffectedArea`, `PestName`, `yrFis` | Pre + Mid + forecast baseline | Disease pressure reduces productive stand. |
| `pre_ganoderma_severity` | Prior-year maximum `P_Severity`. | `P_Severity`, `PestName`, `yrFis` | Pre + Mid + forecast baseline | Severity captures disease intensity. |
| `pre_ganoderma_cumulative_area` | Maximum `AffectedArea` observed through `t-1` (cumulative max). | `AffectedArea`, `PestName`, `yrFis` | Pre + Mid + forecast baseline | Chronic disease burden; longer history than a single prior year. |

### 7.4 Prior-year harvest history

| Output column | Actual derivation | Original fields | Model use | Why |
|---|---|---|---|---|
| `pre_yield_lag1` | `Y_TOTAL_ton` shifted 1 year within block. | `OILPALM.Y_TOTAL_ton` | Pre + Mid + forecast baseline | Strongest block-level yield persistence signal. |
| `pre_yield_lag2` | `Y_TOTAL_ton` shifted 2 years within block. | `OILPALM.Y_TOTAL_ton` | Pre + Mid + forecast baseline | Longer productivity memory. |
| `pre_yield_roll3_mean` | Mean `Y_TOTAL_ton` over the prior 3 years, excluding the current year. | `OILPALM.Y_TOTAL_ton` | Pre + Mid + forecast baseline | Smoothed productivity level. |
| `pre_bunch_weight_lag1` | `Y_KGB` shifted 1 year within block. | `Y_KGB` (`1000 * Y_TOTAL_ton / Y_TOTAL_bunches`) | Pre + Mid + forecast baseline | Prior-year fruit size and bunch weight. |
| `pre_harvest_interval_lag1` | `Y_AVG_harvest_int` shifted 1 year within block. | `OILPALM.Y_AVG_harvest_int` | Pre + Mid + forecast baseline; what-if lever | Operational harvest intensity without current-year leakage. |
| `pre_harvest_rounds_lag1` | `Y_TOTAL_rounds` shifted 1 year within block. | `OILPALM.Y_TOTAL_rounds` | Pre + Mid + forecast baseline | Prior-year harvest frequency. |
| `pre_harvest_loss_rate_lag1` | Prior-year `(sum(bunchesDiscarded_b) + sum(bunchesUnpoll_b)) / (sum(Y_BunchNo) + sum(bunchesDiscarded_b) + sum(bunchesUnpoll_b))`. | `tbl_HRR_harvests` | Pre + Mid + forecast baseline | Harvest quality and lost yield. |
| `pre_division_yield_lag1_mean` | Mean `Y_TOTAL_ton` by `UNIT` in `t-1`. | `Y_TOTAL_ton`, `UNIT` | Pre + Mid + forecast baseline | Shared division-level shocks and hierarchical context. |
| `pre_estate_yield_lag1_mean` | Mean `Y_TOTAL_ton` by `NAME` in `t-1`. | `Y_TOTAL_ton`, `NAME` | Pre + Mid + forecast baseline | Estate-level common shocks and forecast context. |

### 7.5 Black bunch leading indicator

| Output column | Actual derivation | Original fields | Model use | Why |
|---|---|---|---|---|
| `mid_black_bunch_per_palm` | Latest `BlackBunch / NoOfPalm` survey in the current year with `CntDate <= 30 Jun`; null when no survey qualifies. | `tbl_BBC_bunchCounts.BlackBunch`, `NoOfPalm`, `CntDate` | Mid-season only | Early bunch formation signal; available only after current-year surveys and only for 2023-2025 coverage. |

## 8. Complete derived-feature table

These are the engineered columns in addition to the one-hot encodings in
section 4.2. The one-hot columns are listed in section 4.2 and the appendix;
the appendix also lists every final column.

| Output column | Model use | Original fields | Actual derivation | Why it helps |
|---|---|---|---|---|
| `pre_planting_year` | Pre-season + mid-season yield; forecast baseline | `OILPALM.D_PLANTED` | Year extracted from D_PLANTED. | Captures planting cohort and aging context; helps distinguish young from mature blocks beyond tree age. |
| `pre_mature_fraction` | Pre-season + mid-season yield; forecast baseline | `OILPALM.palmStandMature_p`, `OILPALM.palmStand_p` | palmStandMature_p / palmStand_p; null when palmStand_p <= 0. | Share of the stand that is mature; directly scales productive capacity per block. |
| `pre_growth_period_code` | Pre-season + mid-season yield; forecast baseline | `OILPALM.Growth_Period` | `SAYP=0`, `PYP=1`, `DYP=2`. | Ordered maturity phase; captures the transition from young to fully productive palms. |
| `pre_harvester_access_code` | Pre-season + mid-season yield; forecast baseline; what-if lever | `OILPALM.HarvesterAccess` | `None=0`, `Incomplete=1`, `Full=2`; missing/`No data` -> null. | Ordered access constraint; better access allows timely harvest. |
| `pre_yield_lag1` | Pre-season + mid-season yield; forecast baseline | `OILPALM.Y_TOTAL_ton` | Y_TOTAL_ton shifted 1 year within block. | Block-level yield persistence; captures stand, site, age, and management legacy. |
| `pre_yield_lag2` | Pre-season + mid-season yield; forecast baseline | `OILPALM.Y_TOTAL_ton` | Y_TOTAL_ton shifted 2 years within block. | Longer yield memory; helps separate persistent productivity from one-year noise. |
| `pre_yield_roll3_mean` | Pre-season + mid-season yield; forecast baseline | `OILPALM.Y_TOTAL_ton` | Mean of the prior 3 years of Y_TOTAL_ton, excluding the current year. | Smoothed productivity level; reduces the effect of a single unusual harvest year. |
| `pre_bunch_weight_lag1` | Pre-season + mid-season yield; forecast baseline | `OILPALM.Y_KGB` (`1000 * Y_TOTAL_ton / Y_TOTAL_bunches`) | Prior-year Y_KGB; Y_KGB = 1000 * Y_TOTAL_ton / Y_TOTAL_bunches. | Prior-year fruit size/quality; reflects palm condition and bunch development. |
| `pre_harvest_interval_lag1` | Pre-season + mid-season yield; forecast baseline; what-if lever | `OILPALM.Y_AVG_harvest_int` | Prior-year Y_AVG_harvest_int; the current-year value is target-derived and excluded. | Prior-year harvest interval; captures operational intensity and access. Approved what-if lever. |
| `pre_harvest_rounds_lag1` | Pre-season + mid-season yield; forecast baseline | `OILPALM.Y_TOTAL_rounds` | Prior-year Y_TOTAL_rounds. | Prior-year harvest rounds; captures harvest frequency and operational rhythm. |
| `pre_harvest_loss_rate_lag1` | Pre-season + mid-season yield; forecast baseline | `tbl_HRR_harvests.bunchesDiscarded_b`, `bunchesUnpoll_b`, `Y_BunchNo` | Prior-year (discarded + unpollinated bunches) / total bunches from tbl_HRR_harvests. | Prior-year discarded/unpollinated share; captures harvest quality and losses. |
| `pre_division_yield_lag1_mean` | Pre-season + mid-season yield; forecast baseline | `OILPALM.Y_TOTAL_ton`, `OILPALM.UNIT` | Prior-year mean target by UNIT; cutoff-safe division aggregate. | Prior-year division productivity; captures shared weather, mill, and management shocks and regularizes sparse blocks. |
| `pre_estate_yield_lag1_mean` | Pre-season + mid-season yield; forecast baseline | `OILPALM.Y_TOTAL_ton`, `OILPALM.NAME` | Prior-year mean target by NAME; cutoff-safe estate aggregate. | Prior-year estate productivity; hierarchical context for estate-level common shocks. |
| `pre_nutrient_balance_NK` | Pre-season + mid-season yield; forecast baseline; what-if lever | `tbl_FN_nutActRec.nutActInorgN_kg_p`, `nutActOrgN_kg_p`, `nutActInorgK2O_kg_p`, `nutActOrgK2O_kg_p` | (inorganic N + organic N) / (inorganic K2O + organic K2O); null when K2O <= 0. | Relative N vs K supply; nutrient balance affects bunch formation and yield response. Derived from what-if levers. |
| `pre_rain_annual_mm_lag1` | Pre-season + mid-season yield; forecast baseline | `tbl_CW_weatherAndWater.R_Total Rainfall`, `R_UNIT`, `R_YEAR` | Prior-year R_Total Rainfall by weather station. | Prior-year water supply; water availability affects bunch initiation and yield. |
| `pre_dry_months_lag1` | Pre-season + mid-season yield; forecast baseline | `tbl_CW_weatherAndWater.R_NO_dry_month`, `R_UNIT`, `R_YEAR` | Prior-year R_NO_dry_month by weather station. | Prior-year water-stress context; dry months capture drought exposure. |
| `pre_water_deficit_lag1` | Pre-season + mid-season yield; forecast baseline | `tbl_CW_weatherAndWater.R_waterdeficit`, `R_UNIT`, `R_YEAR` | Prior-year R_waterdeficit by weather station. | Prior-year water balance; a direct stress indicator. |
| `pre_rain_anomaly_lag1` | Pre-season + mid-season yield; forecast baseline | `tbl_CW_weatherAndWater.R_Total Rainfall`, station history | Prior-year rainfall minus the station's expanding prior-year climatology. | Prior-year rainfall relative to station history; isolates unusual wet/dry years from baseline climate. |
| `pre_rain_roll3_mean_lag1` | Pre-season + mid-season yield; forecast baseline | `tbl_CW_weatherAndWater.R_Total Rainfall`, station history | Mean rainfall over the 3 weather years ending in t-1. | Three-year water context; smooths year-to-year rainfall noise. |
| `pre_soil_cec_som_ratio` | Pre-season + mid-season yield; forecast baseline | `tbl_FN_soilAnalysis.SA_CEC`, `SA_SOM` | soil_cec / soil_som; null when soil_som <= 0. | Nutrient-holding capacity relative to organic matter; helps explain site response to fertilizer. |
| `pre_ganoderma_cumulative_area` | Pre-season + mid-season yield; forecast baseline | `tbl_PD_surveys.AffectedArea`, `PestName`, `D_Survey`/`yrFis` | Maximum Ganoderma affected area observed through t-1. | Chronic disease burden through t-1; Ganoderma reduces productive stand and yield. |
| `pre_marker_fert_product_count` | Pre-season + mid-season yield; forecast baseline | `OILPALM.markerFert` | Number of semicolon-separated products in markerFert. | Fertilizer program breadth; high product counts indicate more complex nutrient management. |
| `pre_marker_fert_known` | Pre-season + mid-season yield; forecast baseline | `OILPALM.markerFert` | 1 when markerFert is present and not 'No data'. | Marks whether the fertilizer program is recorded; helps separate unknown from no fertilizer. |
| `pre_marker_fert_has_urea` | Pre-season + mid-season yield; forecast baseline | `OILPALM.markerFert` | 1 when markerFert mentions Urea. | Presence of urea in the fertilizer program; nitrogen management context. |
| `pre_marker_fert_has_kcl` | Pre-season + mid-season yield; forecast baseline | `OILPALM.markerFert` | 1 when markerFert mentions KCL. | Presence of KCL; potassium management context. |
| `pre_marker_fert_has_rp` | Pre-season + mid-season yield; forecast baseline | `OILPALM.markerFert` | 1 when markerFert mentions RP. | Presence of rock phosphate; phosphorus management context. |
| `pre_marker_fert_has_kieserite` | Pre-season + mid-season yield; forecast baseline | `OILPALM.markerFert` | 1 when markerFert mentions Kieserite. | Presence of kieserite; magnesium/sulfur management context. |
| `pre_marker_fert_has_borate` | Pre-season + mid-season yield; forecast baseline | `OILPALM.markerFert` | 1 when markerFert mentions Borate. | Presence of borate; boron management context. |
| `pre_marker_fert_has_efb` | Pre-season + mid-season yield; forecast baseline | `OILPALM.markerFert` | 1 when markerFert mentions EFB. | Presence of EFB; organic matter/nutrient management context. |
| `pre_marker_fert_has_compound` | Pre-season + mid-season yield; forecast baseline | `OILPALM.markerFert` | 1 when markerFert mentions a 12:12:17 compound product. | Presence of 12:12:17 compound fertilizer; balanced NPK management context. |
| `pre_pruning_known` | Pre-season + mid-season yield; forecast baseline; what-if lever | `OILPALM.Pruning` | 1 when Pruning is one of Correct, Neglected, Over, or Under. | Marks whether pruning status is recorded; supports the pruning lever and data-quality interpretation. |
| `pre_harvester_access_known` | Pre-season + mid-season yield; forecast baseline; what-if lever | `OILPALM.HarvesterAccess` | 1 when HarvesterAccess is one of None, Incomplete, or Full. | Marks whether harvester access is recorded; supports the access lever and data-quality interpretation. |
| `mid_LA_NK_ratio` | Mid-season yield only | `OILPALM.LA_N`, `LA_K` | LA_N / LA_K; null when LA_K <= 0 or either input is missing. | Leaf N/K balance; nutrient imbalance can limit bunch formation and yield. |
| `mid_LA_NP_ratio` | Mid-season yield only | `OILPALM.LA_N`, `LA_P` | LA_N / LA_P; null when LA_P <= 0 or either input is missing. | Leaf N/P balance; captures relative nitrogen and phosphorus status. |
| `mid_LA_KMg_ratio` | Mid-season yield only | `OILPALM.LA_K`, `LA_Mg` | LA_K / LA_Mg; null when LA_Mg <= 0 or either input is missing. | Leaf K/Mg balance; K and Mg interact in bunch development and photosynthesis. |
| `mid_LA_CaMg_ratio` | Mid-season yield only | `OILPALM.LA_Ca`, `LA_Mg` | LA_Ca / LA_Mg; null when LA_Mg <= 0 or either input is missing. | Leaf Ca/Mg balance; captures cation balance and structural/leaf health context. |

| `mid_black_bunch_per_palm` | Mid-season yield only | `tbl_BBC_bunchCounts.BlackBunch`, `NoOfPalm`, `CntDate` | Latest `BlackBunch / NoOfPalm` current-year survey with `CntDate <= 30 Jun`; null otherwise. | Early bunch formation signal; available only after current-year surveys. |

## 9. Missingness, coverage, and data-quality flags

No feature column is entirely null or constant. The largest missingness is
expected and cutoff-driven:

- Leaf features: about 52% missing because only current-year samples on or
  before 30 June are allowed; `mid_LA_leaf_ProdRate` is about 85% missing.
- `mid_black_bunch_per_palm`: about 75% missing because the survey source only
  covers 2023-2025 and only pre-cutoff surveys are used.
- Soil features: about 62% missing because only prior-year samples on or before
  31 Dec `t-1` are used.
- Ganoderma features: about 50% missing because only prior-year surveys are
  used and coverage is uneven.
- Weather lag features: about 20% missing because 2019/2020 have no earlier
  weather history.
- Yield/history lags: missing in the first one or two years of each block's
  history.

Missing values are preserved. Tree models can consume native missing values;
linear models will need median imputation and missing indicators in Phase 5/6.

Three rows carry `has_anomaly = true` and `anomaly_flags`:

| Block | Year | Target | Flag |
|---|---:|---:|---|
| `124H` | 2024 | 29.7657 | `areaIY_zero_positive_yield` |
| `124H` | 2025 | 63.5373 | `areaIY_zero_positive_yield` |
| `204D` | 2025 | 0.0 | `mature_zero_yield` |

These rows were not dropped. Phase 5 must decide whether to exclude `204D`
2025 from training, as required by the Phase 3 approval note.

## 10. Appendix: full feature-column list

Model use codes:

- **Pre + Mid + forecast baseline** — available at both cutoffs; safe for
  pre-season and mid-season yield models and for the forecasting baseline.
- **Mid-season only** — requires current-year data up to 30 June; not available
  for future forecast horizons.
- **What-if lever** — `adjustable = true`; may be changed by what-if/scenario
  tools.

| Feature column | Base approved feature | Group | Available at | Model use | Adjustable | Encoded | Missing % |
|---|---|---|---|---|---|---|---|
| `pre_area_ha` | `area_ha` | context | pre_season | Pre + Mid + forecast baseline | False | False | 0.0 |
| `pre_planting_year` | `D_PLANTED` | context | pre_season | Pre + Mid + forecast baseline | False | False | 0.0 |
| `pre_tree_age` | `D_TREEAGE` | context | pre_season | Pre + Mid + forecast baseline | False | False | 0.0 |
| `pre_growth_period_code` | `Growth_Period` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_stand_per_ha` | `palmStand_p_ha` | context | pre_season | Pre + Mid + forecast baseline | False | False | 0.0 |
| `pre_stand_mature` | `palmStandMature_p` | context | pre_season | Pre + Mid + forecast baseline | False | False | 0.0 |
| `pre_LandClass_lc1_marihat_135` | `LandClass` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_LandClass_lc1_marihat_143` | `LandClass` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_LandClass_lc1_other_135` | `LandClass` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_LandClass_lc1_other_143` | `LandClass` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_LandClass_lc2_marihat_135` | `LandClass` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_LandClass_lc2_marihat_143` | `LandClass` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_LandClass_lc2_other_135` | `LandClass` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_LandClass_lc2_other_143` | `LandClass` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_LandClass_lc3_marihat_135` | `LandClass` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_LandClass_lc3_marihat_143` | `LandClass` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_LandClass_lc3_other_135` | `LandClass` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_LandClass_lc3_other_143` | `LandClass` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_SOILTYPE_acrisol` | `SOILTYPE` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_SOILTYPE_andosol` | `SOILTYPE` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_SOILTYPE_gleysol` | `SOILTYPE` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_altitude` | `ALTITUDE` | context | pre_season | Pre + Mid + forecast baseline | False | False | 0.0 |
| `pre_TOPOGRAPHY_flat` | `TOPOGRAPHY` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_TOPOGRAPHY_hilly` | `TOPOGRAPHY` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_TOPOGRAPHY_sloping` | `TOPOGRAPHY` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_TOPOGRAPHY_steep` | `TOPOGRAPHY` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_PREV_CROP_2nd_forest` | `PREV_CROP` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_PREV_CROP_coconut` | `PREV_CROP` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_PREV_CROP_prim_forest` | `PREV_CROP` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_PREV_CROP_scrub_beluka` | `PREV_CROP` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_LANDCLEARING_full_man` | `LANDCLEARING` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_LANDCLEARING_full_mech` | `LANDCLEARING` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_LANDCLEARING_manfell_mechrow` | `LANDCLEARING` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_Erosion_moderate` | `Erosion` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_Erosion_no_erosion` | `Erosion` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_Erosion_severe` | `Erosion` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_Erosion_slight` | `Erosion` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_Soil_Consv_bunding` | `Soil_Consv` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_Soil_Consv_none` | `Soil_Consv` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_Soil_Consv_platform` | `Soil_Consv` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_Soil_Consv_silt_traps` | `Soil_Consv` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_Soil_Consv_terrace` | `Soil_Consv` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_GroundCover_lt_50_lcp` | `GroundCover` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_GroundCover_gt_50_lcp` | `GroundCover` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_GroundCover_bare_soil` | `GroundCover` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_GroundCover_hard_weeds` | `GroundCover` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_GroundCover_soft_weeds` | `GroundCover` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_Drainage_poorly_drained` | `Drainage` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_Drainage_seasonal_flood` | `Drainage` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_Drainage_waterlogged` | `Drainage` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_Drainage_well_drained` | `Drainage` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_Pruning_correct` | `Pruning` | management | pre_season | Pre + Mid + forecast baseline; what-if lever | True | True | 0.0 |
| `pre_Pruning_neglected` | `Pruning` | management | pre_season | Pre + Mid + forecast baseline; what-if lever | True | True | 0.0 |
| `pre_Pruning_over` | `Pruning` | management | pre_season | Pre + Mid + forecast baseline; what-if lever | True | True | 0.0 |
| `pre_Pruning_under` | `Pruning` | management | pre_season | Pre + Mid + forecast baseline; what-if lever | True | True | 0.0 |
| `pre_pruning_known` | `Pruning` | management | pre_season | Pre + Mid + forecast baseline; what-if lever | True | False | 0.0 |
| `pre_harvester_access_code` | `HarvesterAccess` | management | pre_season | Pre + Mid + forecast baseline; what-if lever | True | True | 25.2 |
| `pre_harvester_access_known` | `HarvesterAccess` | management | pre_season | Pre + Mid + forecast baseline; what-if lever | True | False | 0.0 |
| `pre_MillName_mill_c` | `MillName` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_MillName_mill_n` | `MillName` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_MillName_mill_s` | `MillName` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_TC_PMAT_asd` | `TC_PMAT` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_TC_PMAT_marihat` | `TC_PMAT` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_TC_PMAT_mixed` | `TC_PMAT` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_TC_PMAT_socfindo` | `TC_PMAT` | context | pre_season | Pre + Mid + forecast baseline | False | True | 0.0 |
| `pre_ablation_reps` | `AblReps` | context | pre_season | Pre + Mid + forecast baseline | False | False | 0.0 |
| `pre_marker_fert_product_count` | `markerFert` | context | pre_season | Pre + Mid + forecast baseline | False | False | 0.0 |
| `pre_marker_fert_known` | `markerFert` | context | pre_season | Pre + Mid + forecast baseline | False | False | 0.0 |
| `pre_marker_fert_has_urea` | `markerFert` | context | pre_season | Pre + Mid + forecast baseline | False | False | 0.0 |
| `pre_marker_fert_has_kcl` | `markerFert` | context | pre_season | Pre + Mid + forecast baseline | False | False | 0.0 |
| `pre_marker_fert_has_rp` | `markerFert` | context | pre_season | Pre + Mid + forecast baseline | False | False | 0.0 |
| `pre_marker_fert_has_kieserite` | `markerFert` | context | pre_season | Pre + Mid + forecast baseline | False | False | 0.0 |
| `pre_marker_fert_has_borate` | `markerFert` | context | pre_season | Pre + Mid + forecast baseline | False | False | 0.0 |
| `pre_marker_fert_has_efb` | `markerFert` | context | pre_season | Pre + Mid + forecast baseline | False | False | 0.0 |
| `pre_marker_fert_has_compound` | `markerFert` | context | pre_season | Pre + Mid + forecast baseline | False | False | 0.0 |
| `pre_mature_fraction` | `palmStandMature_p` | context | pre_season | Pre + Mid + forecast baseline | False | False | 0.0 |
| `pre_yield_lag1` | `yield_lag1` | history | pre_season | Pre + Mid + forecast baseline | False | False | 22.4 |
| `pre_yield_lag2` | `yield_lag1` | history | pre_season | Pre + Mid + forecast baseline | False | False | 40.4 |
| `pre_yield_roll3_mean` | `yield_lag1` | history | pre_season | Pre + Mid + forecast baseline | False | False | 22.4 |
| `pre_bunch_weight_lag1` | `bunch_weight_lag1` | history | pre_season | Pre + Mid + forecast baseline | False | False | 22.4 |
| `pre_harvest_interval_lag1` | `harvest_interval_lag1` | management | pre_season | Pre + Mid + forecast baseline; what-if lever | True | False | 26.4 |
| `pre_harvest_rounds_lag1` | `harvest_rounds_lag1` | history | pre_season | Pre + Mid + forecast baseline | False | False | 22.4 |
| `pre_division_yield_lag1_mean` | `yield_lag1` | history | pre_season | Pre + Mid + forecast baseline | False | False | 11.4 |
| `pre_estate_yield_lag1_mean` | `yield_lag1` | history | pre_season | Pre + Mid + forecast baseline | False | False | 11.2 |
| `pre_nutActInorgN_kg_p` | `nutActInorgN_kg_p` | management | pre_season | Pre + Mid + forecast baseline; what-if lever | True | False | 0.0 |
| `pre_nutActInorgP2O5_kg_p` | `nutActInorgP2O5_kg_p` | management | pre_season | Pre + Mid + forecast baseline; what-if lever | True | False | 0.0 |
| `pre_nutActInorgK2O_kg_p` | `nutActInorgK2O_kg_p` | management | pre_season | Pre + Mid + forecast baseline; what-if lever | True | False | 0.0 |
| `pre_nutActInorgMgO_kg_p` | `nutActInorgMgO_kg_p` | management | pre_season | Pre + Mid + forecast baseline; what-if lever | True | False | 0.0 |
| `pre_nutActInorgCaO_kg_p` | `nutActInorgCaO_kg_p` | management | pre_season | Pre + Mid + forecast baseline; what-if lever | True | False | 0.0 |
| `pre_nutActInorgB_kg_p` | `nutActInorgB_kg_p` | management | pre_season | Pre + Mid + forecast baseline; what-if lever | True | False | 0.0 |
| `pre_nutActOrgN_kg_p` | `nutActOrgN_kg_p` | management | pre_season | Pre + Mid + forecast baseline; what-if lever | True | False | 0.0 |
| `pre_nutActOrgP2O5_kg_p` | `nutActOrgP2O5_kg_p` | management | pre_season | Pre + Mid + forecast baseline; what-if lever | True | False | 0.0 |
| `pre_nutActOrgK2O_kg_p` | `nutActOrgK2O_kg_p` | management | pre_season | Pre + Mid + forecast baseline; what-if lever | True | False | 0.0 |
| `pre_nutrient_balance_NK` | `nutActInorgN_kg_p` | management | pre_season | Pre + Mid + forecast baseline; what-if lever | True | False | 31.7 |
| `pre_rain_annual_mm_lag1` | `rain_annual_mm` | weather | pre_season | Pre + Mid + forecast baseline | False | False | 11.2 |
| `pre_dry_months_lag1` | `dry_months` | weather | pre_season | Pre + Mid + forecast baseline | False | False | 11.2 |
| `pre_water_deficit_lag1` | `water_deficit` | weather | pre_season | Pre + Mid + forecast baseline | False | False | 11.2 |
| `pre_rain_anomaly_lag1` | `rain_annual_mm` | weather | pre_season | Pre + Mid + forecast baseline | False | False | 22.5 |
| `pre_rain_roll3_mean_lag1` | `rain_annual_mm` | weather | pre_season | Pre + Mid + forecast baseline | False | False | 11.2 |
| `pre_soil_ph` | `soil_ph` | soil | pre_season | Pre + Mid + forecast baseline | False | False | 61.8 |
| `pre_soil_cec` | `soil_cec` | soil | pre_season | Pre + Mid + forecast baseline | False | False | 61.8 |
| `pre_soil_som` | `soil_som` | soil | pre_season | Pre + Mid + forecast baseline | False | False | 61.8 |
| `pre_soil_cec_som_ratio` | `soil_cec` | soil | pre_season | Pre + Mid + forecast baseline | False | False | 61.8 |
| `pre_ganoderma_affected_area` | `ganoderma_affected_area` | pest | pre_season | Pre + Mid + forecast baseline | False | False | 50.5 |
| `pre_ganoderma_severity` | `ganoderma_severity` | pest | pre_season | Pre + Mid + forecast baseline | False | False | 50.5 |
| `pre_ganoderma_cumulative_area` | `ganoderma_affected_area` | pest | pre_season | Pre + Mid + forecast baseline | False | False | 50.5 |
| `pre_harvest_loss_rate_lag1` | `harvest_loss_rate_lag1` | history | pre_season | Pre + Mid + forecast baseline | False | False | 16.7 |
| `mid_LA_N` | `LA_N` | leaf | mid_season | Mid-season only | False | False | 52.0 |
| `mid_LA_P` | `LA_P` | leaf | mid_season | Mid-season only | False | False | 52.0 |
| `mid_LA_K` | `LA_K` | leaf | mid_season | Mid-season only | False | False | 52.0 |
| `mid_LA_Ca` | `LA_Ca` | leaf | mid_season | Mid-season only | False | False | 52.0 |
| `mid_LA_Mg` | `LA_Mg` | leaf | mid_season | Mid-season only | False | False | 52.0 |
| `mid_LA_Cl` | `LA_Cl` | leaf | mid_season | Mid-season only | False | False | 52.0 |
| `mid_LA_S` | `LA_S` | leaf | mid_season | Mid-season only | False | False | 52.0 |
| `mid_LA_Mn` | `LA_Mn` | leaf | mid_season | Mid-season only | False | False | 52.0 |
| `mid_LA_B` | `LA_B` | leaf | mid_season | Mid-season only | False | False | 52.0 |
| `mid_LA_Cu` | `LA_Cu` | leaf | mid_season | Mid-season only | False | False | 52.0 |
| `mid_LA_Zn` | `LA_Zn` | leaf | mid_season | Mid-season only | False | False | 52.0 |
| `mid_LA_TLB` | `LA_TLB` | leaf | mid_season | Mid-season only | False | False | 52.0 |
| `mid_LA_PK` | `LA_PK` | leaf | mid_season | Mid-season only | False | False | 52.0 |
| `mid_LA_Rachis_N` | `LA_Rachis_N` | leaf | mid_season | Mid-season only | False | False | 52.0 |
| `mid_LA_Rachis_P` | `LA_Rachis_P` | leaf | mid_season | Mid-season only | False | False | 52.0 |
| `mid_LA_Rachis_K` | `LA_Rachis_K` | leaf | mid_season | Mid-season only | False | False | 52.0 |
| `mid_LA_Rachis_Mg` | `LA_Rachis_Mg` | leaf | mid_season | Mid-season only | False | False | 52.0 |
| `mid_LA_cross_section` | `LA_cross_section` | leaf | mid_season | Mid-season only | False | False | 52.2 |
| `mid_LA_tree_heightIncrement` | `LA_tree_heightIncrement` | leaf | mid_season | Mid-season only | False | False | 71.5 |
| `mid_LA_leaf_ProdRate` | `LA_leaf_ProdRate` | leaf | mid_season | Mid-season only | False | False | 85.1 |
| `mid_LA_NK_ratio` | `LA_N` | leaf | mid_season | Mid-season only | False | False | 52.0 |
| `mid_LA_NP_ratio` | `LA_N` | leaf | mid_season | Mid-season only | False | False | 52.0 |
| `mid_LA_KMg_ratio` | `LA_K` | leaf | mid_season | Mid-season only | False | False | 52.0 |
| `mid_LA_CaMg_ratio` | `LA_Ca` | leaf | mid_season | Mid-season only | False | False | 52.0 |
| `mid_black_bunch_per_palm` | `black_bunch_per_palm` | leading_indicator | mid_season | Mid-season only | False | False | 75.0 |
