from __future__ import annotations

import os

import pytest

from omp_yield.db import Database
from omp_yield.inventory import (
    column_inventory,
    estate_hierarchy,
    growth_periods,
    join_coverage,
    key_uniqueness,
    oilpalm_dictionary,
    table_inventory,
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


def test_oilpalm_dictionary_has_target_and_leakage_notes() -> None:
    dictionary = oilpalm_dictionary(Database())
    target = dictionary.filter(dictionary["column_name"] == "Y_TOTAL_ton").row(0, named=True)
    assert target["preliminary_role"] == "target"

    y_th = dictionary.filter(dictionary["column_name"] == "Y_TH").row(0, named=True)
    assert "Derived" in y_th["notes"]

    sa_text = dictionary.filter(dictionary["column_name"] == "SA_TextClass").row(0, named=True)
    assert sa_text["null_pct"] > 99.0
