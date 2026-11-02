from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from omp_yield.features import load_transforms
from omp_yield.splits import (
    BLOCK_KEYS,
    ChronologicalSplitter,
    GroupKFoldSplitter,
    GroupShuffleSplitter,
    RollingOriginSplitter,
    SplitError,
    TimeSeriesSplitter,
    build_splits,
    load_evaluation_config,
    validate_contract,
)

SNAPSHOT = Path("data/raw/20261030T000000Z")
TABLE = Path("data/processed/modeling_table.parquet")
SCHEMA = Path("data/processed/feature_schema.csv")
REAL_ARTIFACTS = TABLE.is_file() and SCHEMA.is_file() and (SNAPSHOT / "manifest.json").is_file()


def _frame(years: list[int], blocks: list[str]) -> pl.DataFrame:
    rows = []
    for year in years:
        for block in blocks:
            rows.append(
                {
                    "NAME": "Estate",
                    "UNIT": "Unit",
                    "BLOCK": block,
                    "YEAR": year,
                    "Y_TOTAL_ton": float(100 + year + len(block)),
                }
            )
    return pl.DataFrame(rows)


def _block_set(frame: pl.DataFrame, indices: tuple[int, ...]) -> set[tuple[str, str, str]]:
    subset = frame[list(indices)]
    return {
        (row["NAME"], row["UNIT"], row["BLOCK"])
        for row in subset.select(BLOCK_KEYS).iter_rows(named=True)
    }


def _year_set(frame: pl.DataFrame, indices: tuple[int, ...]) -> set[int]:
    return set(int(year) for year in frame[list(indices)]["YEAR"].unique().to_list())


def _contract_fixture() -> tuple[pl.DataFrame, pl.DataFrame]:
    table = pl.DataFrame(
        {
            "NAME": ["Estate"] * 3,
            "UNIT": ["Unit"] * 3,
            "BLOCK": ["A", "B", "C"],
            "YEAR": [2023, 2024, 2025],
            "Y_TOTAL_ton": [100.0, 110.0, 120.0],
            "pre_area_ha": [10.0, 12.0, 14.0],
            "pre_tree_age": [8.0, 9.0, 10.0],
            "pre_stand_per_ha": [130.0, 131.0, 132.0],
            "pre_stand_mature": [1000.0, 1001.0, 1002.0],
            "pre_mature_fraction": [1.0, 1.0, 1.0],
            "pre_growth_period_code": [1, 1, 1],
            "pre_harvester_access_code": [2, 2, 2],
        }
    )
    features = [
        ("pre_area_ha", "area_ha", "context"),
        ("pre_tree_age", "D_TREEAGE", "context"),
        ("pre_stand_per_ha", "palmStand_p_ha", "context"),
        ("pre_stand_mature", "palmStandMature_p", "context"),
        ("pre_mature_fraction", "palmStandMature_p", "context"),
        ("pre_growth_period_code", "Growth_Period", "context"),
        ("pre_harvester_access_code", "HarvesterAccess", "management"),
    ]
    schema = pl.DataFrame(
        {
            "feature": [item[0] for item in features],
            "base_feature": [item[1] for item in features],
            "group": [item[2] for item in features],
            "role": [item[2] for item in features],
            "available_at": ["pre_season"] * len(features),
            "pre_season": [True] * len(features),
            "mid_season": [True] * len(features),
            "adjustable": [item[0] == "pre_harvester_access_code" for item in features],
            "encoded": [item[0] in {"pre_growth_period_code", "pre_harvester_access_code"} for item in features],
            "source": ["OILPALM"] * len(features),
            "derivation": [""] * len(features),
            "dtype": ["Float64", "Float64", "Float64", "Float64", "Float64", "Int8", "Int8"],
            "missing_pct": [0.0] * len(features),
            "n_unique": [3] * len(features),
        }
    )
    return table, schema


def test_chronological_split_has_no_future_training_years() -> None:
    frame = _frame([2019, 2020, 2021, 2022, 2023, 2024, 2025], ["A", "B"])
    fold = ChronologicalSplitter().split(
        frame,
        train_years=[2019, 2020, 2021, 2022, 2023],
        validation_years=[2024],
        test_years=[2025],
    )

    assert max(_year_set(frame, fold.train_indices)) <= 2023
    assert _year_set(frame, fold.validation_indices) == {2024}
    assert _year_set(frame, fold.test_indices) == {2025}
    assert not set(fold.train_indices) & set(fold.validation_indices)
    assert not set(fold.train_indices) & set(fold.test_indices)
    assert not set(fold.validation_indices) & set(fold.test_indices)
    assert len(set(fold.train_indices) | set(fold.validation_indices) | set(fold.test_indices)) == frame.height


def test_chronological_split_rejects_overlapping_years() -> None:
    frame = _frame([2022, 2023, 2024], ["A"])
    with pytest.raises(SplitError):
        ChronologicalSplitter().split(
            frame,
            train_years=[2022, 2023],
            validation_years=[2023],
            test_years=[2024],
        )


def test_grouped_split_has_no_block_overlap() -> None:
    blocks = [f"B{index:02d}" for index in range(20)]
    frame = _frame([2022, 2023, 2024], blocks)
    fold = GroupShuffleSplitter(seed=42).split(frame, validation_size=0.1, test_size=0.1)

    train_blocks = _block_set(frame, fold.train_indices)
    validation_blocks = _block_set(frame, fold.validation_indices)
    test_blocks = _block_set(frame, fold.test_indices)

    assert not train_blocks & validation_blocks
    assert not train_blocks & test_blocks
    assert not validation_blocks & test_blocks
    assert train_blocks | validation_blocks | test_blocks == set(
        (row["NAME"], row["UNIT"], row["BLOCK"])
        for row in frame.select(BLOCK_KEYS).unique().iter_rows(named=True)
    )
    assert len(set(fold.train_indices) | set(fold.validation_indices) | set(fold.test_indices)) == frame.height


def test_group_kfold_has_no_block_overlap() -> None:
    blocks = [f"B{index:02d}" for index in range(20)]
    frame = _frame([2020, 2021, 2022], blocks)
    folds = GroupKFoldSplitter(n_splits=5, seed=42).split(frame)

    assert len(folds) == 5
    for fold in folds:
        train_blocks = _block_set(frame, fold.train_indices)
        validation_blocks = _block_set(frame, fold.validation_indices)
        assert not train_blocks & validation_blocks
        assert train_blocks | validation_blocks == _block_set(frame, tuple(range(frame.height)))


def test_time_series_split_has_no_future_training_years() -> None:
    frame = _frame([2019, 2020, 2021, 2022, 2023], ["A", "B"])
    folds = TimeSeriesSplitter(n_splits=3).split(frame)

    assert len(folds) == 3
    for fold in folds:
        train_years = _year_set(frame, fold.train_indices)
        validation_years = _year_set(frame, fold.validation_indices)
        assert len(validation_years) == 1
        assert max(train_years) < min(validation_years)


def test_rolling_origin_has_no_future_training_records() -> None:
    frame = _frame([2019, 2020, 2021, 2022, 2023, 2024, 2025], ["A", "B"])
    folds = RollingOriginSplitter().split(
        frame,
        [
            {"train_through": 2022, "validation_year": 2023},
            {"train_through": 2023, "validation_year": 2024},
        ],
    )

    for fold in folds:
        train_years = _year_set(frame, fold.train_indices)
        validation_years = _year_set(frame, fold.validation_indices)
        assert max(train_years) <= int(fold.metadata["train_through"])
        assert validation_years == {int(fold.metadata["validation_year"])}
        assert not set(fold.train_indices) & set(fold.validation_indices)


def test_build_splits_is_deterministic() -> None:
    blocks = [f"B{index:02d}" for index in range(20)]
    frame = _frame([2019, 2020, 2021, 2022, 2023, 2024, 2025], blocks)
    evaluation = load_evaluation_config()

    first = build_splits(frame, evaluation)
    second = build_splits(frame, evaluation)

    assert first["primary"]["train"]["sha256"] == second["primary"]["train"]["sha256"]
    assert first["grouped"]["test"]["sha256"] == second["grouped"]["test"]["sha256"]
    assert [fold["train"]["sha256"] for fold in first["cv"]["group_kfold"]] == [
        fold["train"]["sha256"] for fold in second["cv"]["group_kfold"]
    ]
    assert [fold["validation"]["sha256"] for fold in first["rolling_origins"]] == [
        fold["validation"]["sha256"] for fold in second["rolling_origins"]
    ]


def test_contract_passes_on_fixture() -> None:
    table, schema = _contract_fixture()
    report = validate_contract(
        table,
        schema,
        load_evaluation_config(),
        load_transforms(),
        source_tables=None,
    )

    assert report.ok
    assert report.summary["failures"] == 0
    assert report.checks.filter(pl.col("status") == "warn").height == 1


def test_contract_rejects_duplicate_keys() -> None:
    table, schema = _contract_fixture()
    table = pl.concat([table, table.head(1)])
    report = validate_contract(table, schema, load_evaluation_config(), load_transforms())

    assert not report.ok
    assert "unique business key" in report.checks.filter(pl.col("status") == "fail")["check"].to_list()


def test_contract_rejects_negative_target() -> None:
    table, schema = _contract_fixture()
    table = table.with_columns(pl.when(pl.col("BLOCK") == "A").then(-1.0).otherwise(pl.col("Y_TOTAL_ton")).alias("Y_TOTAL_ton"))
    report = validate_contract(table, schema, load_evaluation_config(), load_transforms())

    assert not report.ok
    assert "target present, non-null, and within range" in report.checks.filter(
        pl.col("status") == "fail"
    )["check"].to_list()


def test_contract_rejects_unexpected_ordinal_category() -> None:
    table, schema = _contract_fixture()
    table = table.with_columns(pl.when(pl.col("BLOCK") == "A").then(3).otherwise(pl.col("pre_growth_period_code")).alias("pre_growth_period_code"))
    report = validate_contract(table, schema, load_evaluation_config(), load_transforms())

    assert not report.ok
    assert "domain pre_growth_period_code" in report.checks.filter(
        pl.col("status") == "fail"
    )["check"].to_list()


@pytest.mark.skipif(not REAL_ARTIFACTS, reason="Phase 4 artifacts are not present")
def test_real_contract_and_splits() -> None:
    table = pl.read_parquet(TABLE)
    schema = pl.read_csv(SCHEMA)
    evaluation = load_evaluation_config()
    report = validate_contract(
        table,
        schema,
        evaluation,
        load_transforms(),
        source_tables=None,
    )
    splits = build_splits(table, evaluation, table_path=TABLE, schema_path=SCHEMA)

    assert report.ok
    assert splits["primary"]["train"]["count"] > 0
    assert splits["primary"]["validation"]["years"] == [2024]
    assert splits["primary"]["test"]["years"] == [2025]
    assert splits["refit"]["train"]["years"] == [2019, 2020, 2021, 2022, 2023, 2024]
    assert splits["refit"]["test"]["years"] == [2025]
    assert splits["forecast"]["final_train"]["years"] == [2019, 2020, 2021, 2022, 2023, 2024]
    assert len(splits["cv"]["group_kfold"]) == 5
    assert len(splits["cv"]["time_series"]) == 3
    assert len(splits["rolling_origins"]) == 3
