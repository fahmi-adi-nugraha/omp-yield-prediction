from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from omp_yield.db import Database
from omp_yield.extract import (
    ExtractionConfig,
    extract_snapshot,
    verify_snapshot,
    write_extraction_report,
)
from omp_yield.inventory import (
    column_inventory,
    estate_hierarchy,
    growth_periods,
    join_coverage,
    key_uniqueness,
    oilpalm_dictionary,
    table_inventory,
    write_inventory_reports,
)

pytestmark = pytest.mark.skipif(
    os.getenv("OMP_RUN_INTEGRATION") != "1",
    reason="Set OMP_RUN_INTEGRATION=1 to run live database tests.",
)


def test_ping_returns_oilpalm_count() -> None:
    row = Database().ping().row(0, named=True)
    assert row["database_name"] == "omp_as_demo"
    assert row["oilpalm_rows"] == 2909


def test_read_only_guard_blocks_writes() -> None:
    with pytest.raises(ValueError):
        Database().query("DELETE FROM OILPALM")


def test_inventory_core_counts() -> None:
    db = Database()
    tables = table_inventory(db)
    assert tables.height == 274
    assert tables.filter(tables["table_name"] == "OILPALM")["row_count"].item() == 2909

    columns = column_inventory(db)
    assert columns.filter(columns["table_name"] == "OILPALM").height == 207

    periods = growth_periods(db)
    assert periods["Growth_Period"].sort().to_list() == ["DYP", "IGP", "LDYP", "PYP", "SAYP"]

    hierarchy = estate_hierarchy(db)
    assert hierarchy.height == 9
    assert hierarchy["estate"].n_unique() == 1


def test_inventory_keys_and_coverage() -> None:
    db = Database()
    keys = key_uniqueness(db)
    oilpalm = keys.filter(keys["table_name"] == "OILPALM").row(0, named=True)
    assert oilpalm["duplicate_rows"] == 0

    coverage = join_coverage(db)
    nutrition = coverage.filter(coverage["source_table"] == "tbl_FN_nutActRec").row(0, named=True)
    assert nutrition["matched_source_pct"] == 100.0
    assert nutrition["matched_oil_rows"] == 2909


def test_inventory_writes_csvs_to_data_directory() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        artifacts = write_inventory_reports(
            Database(),
            root / "docs",
            root / "data",
            root / "reports",
        )
        assert (root / "data" / "phase-1-inventory" / "schema_tables.csv").is_file()
        assert (root / "data" / "phase-1-inventory" / "oilpalm_dictionary.csv").is_file()
        assert (root / "docs" / "phase-1-inventory" / "db_inventory.md").is_file()
        assert artifacts["schema_tables.csv"].parent == root / "data" / "phase-1-inventory"


def test_oilpalm_dictionary_has_target_and_leakage_notes() -> None:
    dictionary = oilpalm_dictionary(Database())
    target = dictionary.filter(dictionary["column_name"] == "Y_TOTAL_ton").row(0, named=True)
    assert target["preliminary_role"] == "target"

    y_th = dictionary.filter(dictionary["column_name"] == "Y_TH").row(0, named=True)
    assert "Derived" in y_th["notes"]

    sa_text = dictionary.filter(dictionary["column_name"] == "SA_TextClass").row(0, named=True)
    assert sa_text["null_pct"] > 99.0


def _small_extraction_config(tmp: str) -> ExtractionConfig:
    return ExtractionConfig(
        tables=("OILPALM", "tbl_CW_weatherAndWater"),
        output_dir=Path(tmp) / "raw",
        compression="zstd",
        excluded_tables=(),
    )


def test_extract_snapshot_manifest_and_report() -> None:
    with TemporaryDirectory() as tmp:
        result = extract_snapshot(
            Database(),
            _small_extraction_config(tmp),
            snapshot_id="test-phase2",
        )
        assert result.snapshot_dir.exists()
        assert (result.snapshot_dir / "manifest.json").is_file()
        assert (result.snapshot_dir / "manifest.sha256").is_file()
        assert (result.snapshot_dir / "OILPALM.parquet").is_file()
        assert result.manifest["summary"]["table_count"] == 2
        assert result.manifest["summary"]["row_count"] == 2938
        assert all(t["verified"] for t in result.manifest["tables"])

        report = write_extraction_report(result, Path(tmp) / "report.md")
        text = report.read_text()
        assert "Phase 2" in text
        assert "Snapshot ID" in text

        verification = verify_snapshot(result.snapshot_dir)
        assert verification["manifest_ok"]
        assert verification["all_ok"]


def test_extract_snapshot_force_is_reproducible() -> None:
    with TemporaryDirectory() as tmp:
        cfg = _small_extraction_config(tmp)
        first = extract_snapshot(Database(), cfg, snapshot_id="same-snapshot")
        first_hashes = {
            t["table"]: t["parquet_sha256"] for t in first.manifest["tables"]
        }
        second = extract_snapshot(
            Database(),
            cfg,
            snapshot_id="same-snapshot",
            force=True,
        )
        second_hashes = {
            t["table"]: t["parquet_sha256"] for t in second.manifest["tables"]
        }
        assert first_hashes == second_hashes
