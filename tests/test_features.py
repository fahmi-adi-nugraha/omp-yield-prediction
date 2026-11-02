from __future__ import annotations

from datetime import datetime
from pathlib import Path

import polars as pl
import pytest

from omp_yield.features import (
    KEYS,
    FeatureBuilder,
    FeatureEngineeringError,
    _add_black_bunch_feature,
    _add_lag_features,
    _add_leaf_features,
    _add_weather_features,
    _derived_by_name,
    _validate_result,
    build_modeling_table,
    load_approved_features,
    load_transforms,
    write_modeling_outputs,
)

SNAPSHOT = Path("data/raw/20261030T000000Z")
SNAPSHOT_PRESENT = (SNAPSHOT / "manifest.json").is_file()


def _builder(frame: pl.DataFrame) -> FeatureBuilder:
    sort_columns = [
        column
        for column in ("ID_WeatherStation", "NAME", "UNIT", "BLOCK", "YEAR")
        if column in frame.columns
    ]
    return FeatureBuilder(frame.sort(sort_columns))


def test_lag_features_use_only_prior_years() -> None:
    frame = pl.DataFrame(
        {
            "NAME": ["Estate"] * 3,
            "UNIT": ["Unit"] * 3,
            "BLOCK": ["Block"] * 3,
            "YEAR": [2020, 2021, 2022],
            "Y_TOTAL_ton": [100.0, 200.0, 300.0],
            "Y_KGB": [10.0, 11.0, 12.0],
            "Y_AVG_harvest_int": [10.0, 11.0, 12.0],
            "Y_TOTAL_rounds": [5, 6, 7],
        }
    )
    transforms = load_transforms()
    builder = _builder(frame)

    _add_lag_features(builder, _derived_by_name(transforms))
    result = builder.frame.sort("YEAR")

    assert result["pre_yield_lag1"].to_list() == [None, 100.0, 200.0]
    assert result["pre_yield_lag2"].to_list() == [None, None, 100.0]
    assert result["pre_yield_roll3_mean"].to_list() == [None, 100.0, 150.0]
    assert result["pre_bunch_weight_lag1"].to_list() == [None, 10.0, 11.0]
    assert result["pre_harvest_interval_lag1"].to_list() == [None, 10.0, 11.0]
    assert result["pre_harvest_rounds_lag1"].to_list() == [None, 5, 6]


def test_leaf_features_respect_mid_season_cutoff() -> None:
    approved = load_approved_features()
    transforms = load_transforms()
    leaf_names = [
        feature["name"]
        for feature in approved["features"]
        if feature.get("decision") == "keep"
        and str(feature.get("name", "")).startswith("LA_")
    ]
    data: dict[str, list[object]] = {
        name: [1.0, 1.0, 1.0, 1.0] for name in leaf_names
    }
    data.update(
        {
            "NAME": ["Estate"] * 4,
            "UNIT": ["Unit"] * 4,
            "BLOCK": ["A", "B", "C", "D"],
            "YEAR": [2024] * 4,
            "LA_DATE": [
                datetime(2024, 6, 15),
                datetime(2024, 7, 15),
                datetime(2023, 6, 15),
                None,
            ],
        }
    )
    frame = pl.DataFrame(data)
    builder = _builder(frame)

    _add_leaf_features(
        builder,
        approved,
        transforms,
        _derived_by_name(transforms),
    )
    result = builder.frame.sort("BLOCK")

    assert result["mid_LA_N"].to_list() == [1.0, None, None, None]
    assert result["mid_LA_NK_ratio"].to_list() == [1.0, None, None, None]


def test_black_bunch_uses_latest_survey_before_cutoff() -> None:
    approved = load_approved_features()
    transforms = load_transforms()
    frame = pl.DataFrame(
        {
            "NAME": ["Estate", "Estate"],
            "UNIT": ["Unit", "Unit"],
            "BLOCK": ["B", "B"],
            "YEAR": [2024, 2025],
        }
    )
    bunch = pl.DataFrame(
        {
            "Estate": ["Estate", "Estate", "Estate"],
            "Unit": ["Unit", "Unit", "Unit"],
            "Block": ["B", "B", "B"],
            "CntDate": [
                datetime(2024, 5, 1),
                datetime(2024, 7, 1),
                datetime(2025, 6, 1),
            ],
            "NoOfPalm": [10, 10, 10],
            "BlackBunch": [20, 99, 30],
        }
    )
    builder = _builder(frame)

    _add_black_bunch_feature(
        builder,
        {"tbl_BBC_bunchCounts": bunch},
        approved,
        transforms,
    )
    result = builder.frame.sort("YEAR")

    assert result["mid_black_bunch_per_palm"].to_list() == [2.0, 3.0]


def test_weather_features_use_prior_year_and_expanding_climatology() -> None:
    transforms = load_transforms()
    frame = pl.DataFrame(
        {
            "ID_WeatherStation": ["C01"] * 4,
            "YEAR": [2020, 2021, 2022, 2023],
        }
    )
    weather = pl.DataFrame(
        {
            "R_UNIT": ["C01"] * 4,
            "R_YEAR": [2019, 2020, 2021, 2022],
            "R_Total Rainfall": [100.0, 200.0, 300.0, 400.0],
            "R_NO_dry_month": [1, 2, 3, 4],
            "R_waterdeficit": [-10.0, -20.0, -30.0, -40.0],
        }
    )
    builder = _builder(frame)

    _add_weather_features(
        builder,
        {"tbl_CW_weatherAndWater": weather},
        _derived_by_name(transforms),
    )
    result = builder.frame.sort("YEAR")

    assert result["pre_rain_annual_mm_lag1"].to_list() == [100.0, 200.0, 300.0, 400.0]
    assert result["pre_dry_months_lag1"].to_list() == [1.0, 2.0, 3.0, 4.0]
    assert result["pre_water_deficit_lag1"].to_list() == [-10.0, -20.0, -30.0, -40.0]
    assert result["pre_rain_roll3_mean_lag1"].to_list() == [
        100.0,
        150.0,
        200.0,
        300.0,
    ]
    assert result["pre_rain_anomaly_lag1"].to_list() == [None, 100.0, 150.0, 200.0]


def test_validate_rejects_current_year_target_feature() -> None:
    table = pl.DataFrame(
        {
            "NAME": ["Estate"],
            "UNIT": ["Unit"],
            "BLOCK": ["B"],
            "YEAR": [2024],
            "Y_TOTAL_ton": [100.0],
            "Y_TH": [1.0],
        }
    )
    schema = pl.DataFrame(
        {
            "feature": ["Y_TH"],
            "available_at": ["pre_season"],
            "pre_season": [True],
            "mid_season": [True],
        }
    )

    with pytest.raises(FeatureEngineeringError, match="target-derived"):
        _validate_result(table, schema)


@pytest.mark.skipif(not SNAPSHOT_PRESENT, reason="Phase 2 snapshot is not present")
def test_real_modeling_table_contract() -> None:
    result = build_modeling_table(SNAPSHOT)

    assert result.table.height == 2258
    assert result.table.select(KEYS).unique().height == result.table.height
    assert result.summary["feature_columns"] == result.schema.height
    assert result.summary["feature_columns"] > 100
    assert "Y_TOTAL_ton" not in result.schema["feature"].to_list()
    assert result.schema.filter(pl.col("feature").str.starts_with("Y_")).height == 0
    assert result.schema.filter(pl.col("missing_pct") == 100).height == 0
    assert set(result.schema["available_at"].to_list()) <= {
        "pre_season",
        "mid_season",
    }
    assert result.schema.filter(~pl.col("pre_season") & ~pl.col("mid_season")).height == 0
    assert result.schema.filter(pl.col("pre_season") & ~pl.col("mid_season")).height == 0
    assert result.table.filter(pl.col("has_anomaly")).height == 3
    assert result.schema.filter(pl.col("feature") == "pre_yield_lag1").height == 1


@pytest.mark.skipif(not SNAPSHOT_PRESENT, reason="Phase 2 snapshot is not present")
def test_real_modeling_table_categories_and_missingness() -> None:
    result = build_modeling_table(SNAPSHOT)
    table = result.table

    assert set(table["pre_growth_period_code"].unique().to_list()) <= {0, 1, 2}
    landclass_columns = [
        column for column in table.columns if column.startswith("pre_LandClass_")
    ]
    assert landclass_columns
    sums = table.select(pl.sum_horizontal(landclass_columns).alias("sum"))["sum"]
    assert set(sums.unique().to_list()) == {1}
    assert table["pre_soil_ph"].null_count() > 0
    assert table["mid_LA_N"].null_count() > 0
    assert table["pre_marker_fert_product_count"].min() is not None


@pytest.mark.skipif(not SNAPSHOT_PRESENT, reason="Phase 2 snapshot is not present")
def test_write_modeling_outputs(tmp_path: Path) -> None:
    result = write_modeling_outputs(
        SNAPSHOT,
        output_path=tmp_path / "modeling_table.parquet",
        schema_csv_path=tmp_path / "feature_schema.csv",
        schema_parquet_path=tmp_path / "feature_schema.parquet",
        report_path=tmp_path / "04_feature_engineering.html",
    )

    assert result.output_path is not None and result.output_path.is_file()
    assert result.schema_csv_path is not None and result.schema_csv_path.is_file()
    assert result.schema_parquet_path is not None and result.schema_parquet_path.is_file()
    assert result.report_path is not None and result.report_path.is_file()
    assert pl.read_parquet(result.output_path).height == 2258
    assert "Phase 4" in result.report_path.read_text(encoding="utf-8")
