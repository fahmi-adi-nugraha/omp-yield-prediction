from __future__ import annotations

from pathlib import Path

import pytest

from omp_yield.extract import load_extraction_config, validate_snapshot_id


def test_validate_snapshot_id_accepts_safe_values() -> None:
    assert validate_snapshot_id("20261030T120000Z") == "20261030T120000Z"
    assert validate_snapshot_id("phase2.test-01") == "phase2.test-01"


@pytest.mark.parametrize("value", ["", "../escape", "a/b", "-leading", "has space"])
def test_validate_snapshot_id_rejects_unsafe_values(value: str) -> None:
    with pytest.raises(ValueError):
        validate_snapshot_id(value)


def test_load_extraction_config() -> None:
    cfg = load_extraction_config(Path("config/extraction.yaml"))
    assert "OILPALM" in cfg.tables
    assert "tbl_FN_nutActRec" in cfg.tables
    assert cfg.output_dir == Path("data/raw")
    assert cfg.compression == "zstd"
    assert cfg.config_sha256
    assert cfg.excluded_tables
