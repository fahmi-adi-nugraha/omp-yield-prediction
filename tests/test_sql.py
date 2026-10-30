from __future__ import annotations

import pytest

from omp_yield.sql import UnsafeQueryError, validate_read_only


def test_accepts_select() -> None:
    assert validate_read_only("SELECT 1 AS one;") == "SELECT 1 AS one"


def test_accepts_with_cte() -> None:
    sql = "WITH x AS (SELECT 1 AS one) SELECT * FROM x"
    assert validate_read_only(sql) == sql


def test_accepts_comments_before_select() -> None:
    sql = "-- a comment\nSELECT 1"
    assert validate_read_only(sql) == "SELECT 1"


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO t VALUES (1)",
        "UPDATE t SET x = 1",
        "DELETE FROM t",
        "DROP TABLE t",
        "EXEC sp_who",
        "SELECT 1; SELECT 2",
        "SELECT * INTO new_table FROM OILPALM",
        "SELECT * FROM OPENROWSET('x', 'y', 'z')",
    ],
)
def test_rejects_unsafe_sql(sql: str) -> None:
    with pytest.raises(UnsafeQueryError):
        validate_read_only(sql)


def test_rejects_empty() -> None:
    with pytest.raises(UnsafeQueryError):
        validate_read_only("   ")
