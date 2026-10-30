from __future__ import annotations

import polars as pl

from omp_yield.inventory import markdown_table, quote_ident


def test_quote_ident_escapes_brackets() -> None:
    assert quote_ident("a]b") == "[a]]b]"


def test_markdown_table_escapes_pipes_and_newlines() -> None:
    frame = pl.DataFrame({"a": ["x|y", "line\nbreak"], "b": [1, 2]})
    table = markdown_table(frame)
    assert "x\\|y" in table
    assert "line<br>break" in table
    assert "| a | b |" in table


def test_markdown_table_selects_and_limits() -> None:
    frame = pl.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
    table = markdown_table(frame, ["a"], max_rows=1)
    assert "| a |" in table
    assert "| 1 |" in table
    assert "| 2 |" not in table
