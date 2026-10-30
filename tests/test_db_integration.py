from __future__ import annotations

import os

import pytest

from omp_yield.db import Database

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
