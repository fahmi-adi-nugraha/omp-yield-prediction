# Data Contract — OMP Yield Modeling

Status: **generated from the Phase 4 modeling table**

Generated at: `2026-11-02T08:50:10.218608+00:00`

## Table

| Property | Value |
|---|---|
| Rows | 2,258 |
| Feature columns | 132 |
| Schema features | 132 |
| Target | `Y_TOTAL_ton` metric tons |
| Keys | `NAME`, `UNIT`, `BLOCK`, `YEAR` |
| Target min / max | 0.0 / 1747.6692 |

## Key and target rules

- The business key `(NAME, UNIT, BLOCK, YEAR)` must be unique.
- The target must be non-null and non-negative.
- Rows must stay inside the mature 2019–2025 modeling range.
- The target is never a feature.
- Current-year target-derived `Y_*` columns are excluded.

## Numeric bounds

| Feature | Configured min | Configured max | Observed min | Observed max |
|---|---|---|---|---|
| `pre_area_ha` | 0.0 | 10000.0 | 2.0 | 69.96999999999998 |
| `pre_tree_age` | 0.0 | 60.0 | 3.0 | 19.0 |
| `pre_stand_per_ha` | 0.0 | 1000.0 | 126.83933933933935 | 142.8108108108108 |
| `pre_stand_mature` | 0.0 | 1000000.0 | 0.0 | 9909.0 |
| `pre_mature_fraction` | 0.0 | 1.1 | 0.0 | 1.0014645577035735 |

`pre_mature_fraction` may exceed 1.0 slightly because of the known mature-stand
greater-than-total-stand data-quality cases; it is flagged, not dropped.

## Categorical domains

- Mature `Growth_Period`: `SAYP`, `PYP`, `DYP`.
- `HarvesterAccess`: `None`, `Incomplete`, `Full`, plus missing/`No data`.
- `Pruning`: `Correct`, `Neglected`, `Over`, `Under`, plus missing/`No data`.
- One-hot families follow `config/transforms.yaml`; all encoded one-hot
  indicators must be binary.

## Feature availability

Every feature in `data/processed/feature_schema.csv` must have an
`available_at` of `pre_season` or `mid_season`, and the `pre_season` /
`mid_season` flags must identify its view. The mid-season view is
`pre_season + mid_season`.

## Missingness

Nulls are retained. Missing numeric values are allowed and must be handled by
the model-specific pipeline. No feature may be entirely null.

## Anomaly flags

`anomaly_flags` and `has_anomaly` mark the known `124H` 2024/2025 area anomaly
and the `204D` 2025 zero-yield anomaly. These rows remain in the modeling table;
Phase 5/6 must decide whether `204D` 2025 is excluded from training.

## Contract checks

| Check | Status | Details |
|---|---|---|
| unique business key | pass | 0 duplicate keys |
| target present, non-null, and within range | pass | nulls=0, min=0.0, max=1747.6692 |
| year range | pass | min=2019, max=2025, allowed=2019..2025 |
| feature schema covers every feature column | pass | schema=132, table_features=132 |
| feature availability metadata is complete | pass | available_at must be pre_season or mid_season |
| no current-year Y_* feature | pass | target-derived current-year columns must not be features |
| no all-null feature columns | pass | none |
| target is not a feature | pass | target column excluded from feature list |
| bounds pre_area_ha | pass | min=2.0, max=69.96999999999998, allowed=0.0..10000.0 |
| bounds pre_tree_age | pass | min=3.0, max=19.0, allowed=0.0..60.0 |
| bounds pre_stand_per_ha | pass | min=126.83933933933935, max=142.8108108108108, allowed=0.0..1000.0 |
| bounds pre_stand_mature | pass | min=0.0, max=9909.0, allowed=0.0..1000000.0 |
| bounds pre_mature_fraction | pass | min=0.0, max=1.0014645577035735, allowed=0.0..1.1 |
| domain pre_growth_period_code | pass | values=[0, 1, 2], unexpected=[] |
| domain pre_harvester_access_code | pass | values=[0, 1, 2], unexpected=[] |
| one-hot binary values LandClass | pass | all binary |
| one-hot binary values SOILTYPE | pass | all binary |
| one-hot binary values TOPOGRAPHY | pass | all binary |
| one-hot binary values PREV_CROP | pass | all binary |
| one-hot binary values LANDCLEARING | pass | all binary |
| one-hot binary values Erosion | pass | all binary |
| one-hot binary values Soil_Consv | pass | all binary |
| one-hot binary values GroundCover | pass | all binary |
| one-hot binary values Drainage | pass | all binary |
| one-hot binary values Pruning | pass | all binary |
| one-hot binary values MillName | pass | all binary |
| one-hot binary values TC_PMAT | pass | all binary |
| binary indicator values | pass | all binary |
| source dates parseable | pass | D_PLANTED and LA_DATE are temporal |
| growth-period domain in modeling rows | pass | observed=['DYP', 'PYP', 'SAYP'], allowed=['DYP', 'PYP', 'SAYP'] |
| source category domain Pruning | pass | unexpected=[] |
| source category domain HarvesterAccess | pass | unexpected=[] |

## Feature schema

| Feature | Base feature | Group | Available at | Dtype | Missing % |
|---|---|---|---|---|---|
| `pre_area_ha` | `area_ha` | context | pre_season | Float64 | 0.0 |
| `pre_planting_year` | `D_PLANTED` | context | pre_season | Int64 | 0.0 |
| `pre_tree_age` | `D_TREEAGE` | context | pre_season | Float64 | 0.0 |
| `pre_growth_period_code` | `Growth_Period` | context | pre_season | Int8 | 0.0 |
| `pre_stand_per_ha` | `palmStand_p_ha` | context | pre_season | Float64 | 0.0 |
| `pre_stand_mature` | `palmStandMature_p` | context | pre_season | Float64 | 0.0 |
| `pre_LandClass_lc1_marihat_135` | `LandClass` | context | pre_season | Int8 | 0.0 |
| `pre_LandClass_lc1_marihat_143` | `LandClass` | context | pre_season | Int8 | 0.0 |
| `pre_LandClass_lc1_other_135` | `LandClass` | context | pre_season | Int8 | 0.0 |
| `pre_LandClass_lc1_other_143` | `LandClass` | context | pre_season | Int8 | 0.0 |
| `pre_LandClass_lc2_marihat_135` | `LandClass` | context | pre_season | Int8 | 0.0 |
| `pre_LandClass_lc2_marihat_143` | `LandClass` | context | pre_season | Int8 | 0.0 |
| `pre_LandClass_lc2_other_135` | `LandClass` | context | pre_season | Int8 | 0.0 |
| `pre_LandClass_lc2_other_143` | `LandClass` | context | pre_season | Int8 | 0.0 |
| `pre_LandClass_lc3_marihat_135` | `LandClass` | context | pre_season | Int8 | 0.0 |
| `pre_LandClass_lc3_marihat_143` | `LandClass` | context | pre_season | Int8 | 0.0 |
| `pre_LandClass_lc3_other_135` | `LandClass` | context | pre_season | Int8 | 0.0 |
| `pre_LandClass_lc3_other_143` | `LandClass` | context | pre_season | Int8 | 0.0 |
| `pre_SOILTYPE_acrisol` | `SOILTYPE` | context | pre_season | Int8 | 0.0 |
| `pre_SOILTYPE_andosol` | `SOILTYPE` | context | pre_season | Int8 | 0.0 |
| `pre_SOILTYPE_gleysol` | `SOILTYPE` | context | pre_season | Int8 | 0.0 |
| `pre_altitude` | `ALTITUDE` | context | pre_season | Float64 | 0.0 |
| `pre_TOPOGRAPHY_flat` | `TOPOGRAPHY` | context | pre_season | Int8 | 0.0 |
| `pre_TOPOGRAPHY_hilly` | `TOPOGRAPHY` | context | pre_season | Int8 | 0.0 |
| `pre_TOPOGRAPHY_sloping` | `TOPOGRAPHY` | context | pre_season | Int8 | 0.0 |
| `pre_TOPOGRAPHY_steep` | `TOPOGRAPHY` | context | pre_season | Int8 | 0.0 |
| `pre_PREV_CROP_2nd_forest` | `PREV_CROP` | context | pre_season | Int8 | 0.0 |
| `pre_PREV_CROP_coconut` | `PREV_CROP` | context | pre_season | Int8 | 0.0 |
| `pre_PREV_CROP_prim_forest` | `PREV_CROP` | context | pre_season | Int8 | 0.0 |
| `pre_PREV_CROP_scrub_beluka` | `PREV_CROP` | context | pre_season | Int8 | 0.0 |
| `pre_LANDCLEARING_full_man` | `LANDCLEARING` | context | pre_season | Int8 | 0.0 |
| `pre_LANDCLEARING_full_mech` | `LANDCLEARING` | context | pre_season | Int8 | 0.0 |
| `pre_LANDCLEARING_manfell_mechrow` | `LANDCLEARING` | context | pre_season | Int8 | 0.0 |
| `pre_Erosion_moderate` | `Erosion` | context | pre_season | Int8 | 0.0 |
| `pre_Erosion_no_erosion` | `Erosion` | context | pre_season | Int8 | 0.0 |
| `pre_Erosion_severe` | `Erosion` | context | pre_season | Int8 | 0.0 |
| `pre_Erosion_slight` | `Erosion` | context | pre_season | Int8 | 0.0 |
| `pre_Soil_Consv_bunding` | `Soil_Consv` | context | pre_season | Int8 | 0.0 |
| `pre_Soil_Consv_none` | `Soil_Consv` | context | pre_season | Int8 | 0.0 |
| `pre_Soil_Consv_platform` | `Soil_Consv` | context | pre_season | Int8 | 0.0 |
| `pre_Soil_Consv_silt_traps` | `Soil_Consv` | context | pre_season | Int8 | 0.0 |
| `pre_Soil_Consv_terrace` | `Soil_Consv` | context | pre_season | Int8 | 0.0 |
| `pre_GroundCover_lt_50_lcp` | `GroundCover` | context | pre_season | Int8 | 0.0 |
| `pre_GroundCover_gt_50_lcp` | `GroundCover` | context | pre_season | Int8 | 0.0 |
| `pre_GroundCover_bare_soil` | `GroundCover` | context | pre_season | Int8 | 0.0 |
| `pre_GroundCover_hard_weeds` | `GroundCover` | context | pre_season | Int8 | 0.0 |
| `pre_GroundCover_soft_weeds` | `GroundCover` | context | pre_season | Int8 | 0.0 |
| `pre_Drainage_poorly_drained` | `Drainage` | context | pre_season | Int8 | 0.0 |
| `pre_Drainage_seasonal_flood` | `Drainage` | context | pre_season | Int8 | 0.0 |
| `pre_Drainage_waterlogged` | `Drainage` | context | pre_season | Int8 | 0.0 |
| `pre_Drainage_well_drained` | `Drainage` | context | pre_season | Int8 | 0.0 |
| `pre_Pruning_correct` | `Pruning` | management | pre_season | Int8 | 0.0 |
| `pre_Pruning_neglected` | `Pruning` | management | pre_season | Int8 | 0.0 |
| `pre_Pruning_over` | `Pruning` | management | pre_season | Int8 | 0.0 |
| `pre_Pruning_under` | `Pruning` | management | pre_season | Int8 | 0.0 |
| `pre_pruning_known` | `Pruning` | management | pre_season | Int8 | 0.0 |
| `pre_harvester_access_code` | `HarvesterAccess` | management | pre_season | Int8 | 25.2 |
| `pre_harvester_access_known` | `HarvesterAccess` | management | pre_season | Int8 | 0.0 |
| `pre_MillName_mill_c` | `MillName` | context | pre_season | Int8 | 0.0 |
| `pre_MillName_mill_n` | `MillName` | context | pre_season | Int8 | 0.0 |
| `pre_MillName_mill_s` | `MillName` | context | pre_season | Int8 | 0.0 |
| `pre_TC_PMAT_asd` | `TC_PMAT` | context | pre_season | Int8 | 0.0 |
| `pre_TC_PMAT_marihat` | `TC_PMAT` | context | pre_season | Int8 | 0.0 |
| `pre_TC_PMAT_mixed` | `TC_PMAT` | context | pre_season | Int8 | 0.0 |
| `pre_TC_PMAT_socfindo` | `TC_PMAT` | context | pre_season | Int8 | 0.0 |
| `pre_ablation_reps` | `AblReps` | context | pre_season | Float64 | 0.0 |
| `pre_marker_fert_product_count` | `markerFert` | context | pre_season | Int16 | 0.0 |
| `pre_marker_fert_known` | `markerFert` | context | pre_season | Int8 | 0.0 |
| `pre_marker_fert_has_urea` | `markerFert` | context | pre_season | Int8 | 0.0 |
| `pre_marker_fert_has_kcl` | `markerFert` | context | pre_season | Int8 | 0.0 |
| `pre_marker_fert_has_rp` | `markerFert` | context | pre_season | Int8 | 0.0 |
| `pre_marker_fert_has_kieserite` | `markerFert` | context | pre_season | Int8 | 0.0 |
| `pre_marker_fert_has_borate` | `markerFert` | context | pre_season | Int8 | 0.0 |
| `pre_marker_fert_has_efb` | `markerFert` | context | pre_season | Int8 | 0.0 |
| `pre_marker_fert_has_compound` | `markerFert` | context | pre_season | Int8 | 0.0 |
| `pre_mature_fraction` | `palmStandMature_p` | context | pre_season | Float64 | 0.0 |
| `pre_yield_lag1` | `yield_lag1` | history | pre_season | Float64 | 22.4 |
| `pre_yield_lag2` | `yield_lag1` | history | pre_season | Float64 | 40.4 |
| `pre_yield_roll3_mean` | `yield_lag1` | history | pre_season | Float64 | 22.4 |
| `pre_bunch_weight_lag1` | `bunch_weight_lag1` | history | pre_season | Float64 | 22.4 |
| `pre_harvest_interval_lag1` | `harvest_interval_lag1` | management | pre_season | Float64 | 26.4 |
| `pre_harvest_rounds_lag1` | `harvest_rounds_lag1` | history | pre_season | Float64 | 22.4 |
| `pre_division_yield_lag1_mean` | `yield_lag1` | history | pre_season | Float64 | 11.4 |
| `pre_estate_yield_lag1_mean` | `yield_lag1` | history | pre_season | Float64 | 11.2 |
| `pre_nutActInorgN_kg_p` | `nutActInorgN_kg_p` | management | pre_season | Float64 | 0.0 |
| `pre_nutActInorgP2O5_kg_p` | `nutActInorgP2O5_kg_p` | management | pre_season | Float64 | 0.0 |
| `pre_nutActInorgK2O_kg_p` | `nutActInorgK2O_kg_p` | management | pre_season | Float64 | 0.0 |
| `pre_nutActInorgMgO_kg_p` | `nutActInorgMgO_kg_p` | management | pre_season | Float64 | 0.0 |
| `pre_nutActInorgCaO_kg_p` | `nutActInorgCaO_kg_p` | management | pre_season | Float64 | 0.0 |
| `pre_nutActInorgB_kg_p` | `nutActInorgB_kg_p` | management | pre_season | Float64 | 0.0 |
| `pre_nutActOrgN_kg_p` | `nutActOrgN_kg_p` | management | pre_season | Float64 | 0.0 |
| `pre_nutActOrgP2O5_kg_p` | `nutActOrgP2O5_kg_p` | management | pre_season | Float64 | 0.0 |
| `pre_nutActOrgK2O_kg_p` | `nutActOrgK2O_kg_p` | management | pre_season | Float64 | 0.0 |
| `pre_nutrient_balance_NK` | `nutActInorgN_kg_p` | management | pre_season | Float64 | 31.7 |
| `pre_rain_annual_mm_lag1` | `rain_annual_mm` | weather | pre_season | Float64 | 11.2 |
| `pre_dry_months_lag1` | `dry_months` | weather | pre_season | Float64 | 11.2 |
| `pre_water_deficit_lag1` | `water_deficit` | weather | pre_season | Float64 | 11.2 |
| `pre_rain_anomaly_lag1` | `rain_annual_mm` | weather | pre_season | Float64 | 22.5 |
| `pre_rain_roll3_mean_lag1` | `rain_annual_mm` | weather | pre_season | Float64 | 11.2 |
| `pre_soil_ph` | `soil_ph` | soil | pre_season | Float64 | 61.8 |
| `pre_soil_cec` | `soil_cec` | soil | pre_season | Float64 | 61.8 |
| `pre_soil_som` | `soil_som` | soil | pre_season | Float64 | 61.8 |
| `pre_soil_cec_som_ratio` | `soil_cec` | soil | pre_season | Float64 | 61.8 |
| `pre_ganoderma_affected_area` | `ganoderma_affected_area` | pest | pre_season | Float64 | 50.5 |
| `pre_ganoderma_severity` | `ganoderma_severity` | pest | pre_season | Float64 | 50.5 |
| `pre_ganoderma_cumulative_area` | `ganoderma_affected_area` | pest | pre_season | Float64 | 50.5 |
| `pre_harvest_loss_rate_lag1` | `harvest_loss_rate_lag1` | history | pre_season | Float64 | 16.7 |
| `mid_LA_N` | `LA_N` | leaf | mid_season | Float64 | 52.0 |
| `mid_LA_P` | `LA_P` | leaf | mid_season | Float64 | 52.0 |
| `mid_LA_K` | `LA_K` | leaf | mid_season | Float64 | 52.0 |
| `mid_LA_Ca` | `LA_Ca` | leaf | mid_season | Float64 | 52.0 |
| `mid_LA_Mg` | `LA_Mg` | leaf | mid_season | Float64 | 52.0 |
| `mid_LA_Cl` | `LA_Cl` | leaf | mid_season | Float64 | 52.0 |
| `mid_LA_S` | `LA_S` | leaf | mid_season | Float64 | 52.0 |
| `mid_LA_Mn` | `LA_Mn` | leaf | mid_season | Float64 | 52.0 |
| `mid_LA_B` | `LA_B` | leaf | mid_season | Float64 | 52.0 |
| `mid_LA_Cu` | `LA_Cu` | leaf | mid_season | Float64 | 52.0 |
| `mid_LA_Zn` | `LA_Zn` | leaf | mid_season | Float64 | 52.0 |
| `mid_LA_TLB` | `LA_TLB` | leaf | mid_season | Float64 | 52.0 |
| `mid_LA_PK` | `LA_PK` | leaf | mid_season | Float64 | 52.0 |
| `mid_LA_Rachis_N` | `LA_Rachis_N` | leaf | mid_season | Float64 | 52.0 |
| `mid_LA_Rachis_P` | `LA_Rachis_P` | leaf | mid_season | Float64 | 52.0 |
| `mid_LA_Rachis_K` | `LA_Rachis_K` | leaf | mid_season | Float64 | 52.0 |
| `mid_LA_Rachis_Mg` | `LA_Rachis_Mg` | leaf | mid_season | Float64 | 52.0 |
| `mid_LA_cross_section` | `LA_cross_section` | leaf | mid_season | Float64 | 52.2 |
| `mid_LA_tree_heightIncrement` | `LA_tree_heightIncrement` | leaf | mid_season | Float64 | 71.5 |
| `mid_LA_leaf_ProdRate` | `LA_leaf_ProdRate` | leaf | mid_season | Float64 | 85.1 |
| `mid_LA_NK_ratio` | `LA_N` | leaf | mid_season | Float64 | 52.0 |
| `mid_LA_NP_ratio` | `LA_N` | leaf | mid_season | Float64 | 52.0 |
| `mid_LA_KMg_ratio` | `LA_K` | leaf | mid_season | Float64 | 52.0 |
| `mid_LA_CaMg_ratio` | `LA_Ca` | leaf | mid_season | Float64 | 52.0 |
| `mid_black_bunch_per_palm` | `black_bunch_per_palm` | leading_indicator | mid_season | Float64 | 75.0 |
