from __future__ import annotations

from pathlib import Path

import polars as pl

from omp_yield.cleaning import _write_config, build_population, missingness_table


def test_build_population_separates_mature_and_placeholder() -> None:
    frame = pl.DataFrame(
        {
            "NAME": ["E"] * 4,
            "UNIT": ["D"] * 4,
            "BLOCK": ["1", "1", "2", "2"],
            "YEAR": [2024, 2025, 2025, 2026],
            "Growth_Period": ["SAYP", "IGP", "SAYP", "DYP"],
            "Y_TOTAL_ton": [100.0, 0.0, 0.0, 0.0],
            "areaIY_ha": [0.0, 10.0, 10.0, 10.0],
        }
    )
    population = build_population(frame)
    assert population["usable"].height == 3
    assert population["mature"].height == 2
    assert population["mature_positive"].height == 1
    assert population["immature"].height == 1
    assert population["placeholder"].height == 1
    assert set(population["anomalies"]["flag"].to_list()) == {
        "areaIY_zero_positive_yield",
        "mature_zero_yield",
        "placeholder_2026",
    }


def test_missingness_treats_blank_strings_as_missing() -> None:
    frame = pl.DataFrame(
        {
            "a": [1.0, None, 3.0],
            "b": ["x", " ", None],
        }
    )
    stats = missingness_table(frame)
    assert stats.filter(pl.col("column_name") == "a")["missing_pct"].item() == 33.3
    assert stats.filter(pl.col("column_name") == "b")["missing_pct"].item() == 66.7


def test_write_config_preserves_existing_edited_file(tmp_path: Path) -> None:
    path = tmp_path / "features.yaml"
    path.write_text("status: approved\n")
    actual, generated = _write_config(
        path,
        {"status": "draft", "features": []},
        overwrite=False,
    )
    assert actual == path
    assert path.read_text() == "status: approved\n"
    assert generated is not None
    assert generated.name == "features.generated.yaml"
    assert "status: draft" in generated.read_text()
