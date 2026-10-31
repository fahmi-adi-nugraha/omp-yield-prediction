import marimo

app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    mo.md(
        """
        # OMP Database Inventory

        Phase 1 inventory for the OMP oil palm yield prediction pipeline.

        This notebook is a live view over the read-only `omp_as_demo` database.
        The generated CSVs and Markdown reports live in `docs/`; the exported
        HTML is written to `reports/01_db_inventory.html`.
        """
    )
    return


@app.cell
def _():
    from omp_yield.config import Settings
    from omp_yield.db import Database
    from omp_yield.inventory import (
        column_inventory,
        estate_hierarchy,
        foreign_key_inventory,
        growth_periods,
        join_coverage,
        key_inventory,
        key_uniqueness,
        oilpalm_dictionary,
        table_inventory,
    )

    db = Database(Settings())
    return (
        Database,
        column_inventory,
        db,
        estate_hierarchy,
        foreign_key_inventory,
        growth_periods,
        join_coverage,
        key_inventory,
        key_uniqueness,
        oilpalm_dictionary,
        table_inventory,
    )


@app.cell
def _(db):
    db.ping()
    return


@app.cell
def _(mo, table_inventory, db):
    tables = table_inventory(db)
    mo.md(
        f"**{tables.height:,} tables** and "
        f"**{int(tables['row_count'].sum()):,} total rows** "
        "across partition counts."
    )
    mo.ui.table(tables.head(40), selection=None)
    return (tables,)


@app.cell
def _(mo, column_inventory, db):
    columns = column_inventory(db)
    mo.md(f"**{columns.height:,} visible columns** across those tables.")
    mo.ui.table(columns.head(40), selection=None)
    return (columns,)


@app.cell
def _(mo, key_uniqueness, db):
    checks = key_uniqueness(db)
    mo.md(
        "Candidate business-key uniqueness checks. `duplicate_rows = 0` means "
        "the candidate key identifies a row."
    )
    mo.ui.table(checks, selection=None)
    return (checks,)


@app.cell
def _(mo, join_coverage, db):
    coverage = join_coverage(db)
    mo.md(
        "Candidate join coverage against `OILPALM`. `matched_source_pct` is the "
        "share of source keys that land in OILPALM; `matched_oil_pct` is the "
        "share of OILPALM block-years covered by the source."
    )
    mo.ui.table(coverage, selection=None)
    return (coverage,)


@app.cell
def _(mo, growth_periods, db):
    periods = growth_periods(db)
    mo.md(
        """
        ## Growth periods

        Mature model definition: `Growth_Period IN ('SAYP', 'PYP', 'DYP')`
        (age >= 3). `IGP` is immature and excluded.
        """
    )
    mo.ui.table(periods, selection=None)
    return (periods,)


@app.cell
def _(mo, estate_hierarchy, db):
    hierarchy = estate_hierarchy(db)
    mo.md(
        "## Estate -> division hierarchy\n\n"
        "The demo has one `NAME` estate and nine `UNIT` divisions. Forecast "
        "output is estate-level; training uses the block panel."
    )
    mo.ui.table(hierarchy, selection=None)
    return (hierarchy,)


@app.cell
def _(mo, key_inventory, db):
    keys = key_inventory(db)
    mo.md("## Primary and unique key constraints")
    mo.ui.table(keys.head(60), selection=None)
    return (keys,)


@app.cell
def _(mo, foreign_key_inventory, db):
    fks = foreign_key_inventory(db)
    mo.md("## Foreign keys")
    mo.ui.table(fks.head(60), selection=None)
    return (fks,)


@app.cell
def _(mo, oilpalm_dictionary, db):
    dictionary = oilpalm_dictionary(db)
    mo.md(
        """
        ## OILPALM data dictionary

        This is a starting point for Phase 3 feature decisions. `available_at`
        and `preliminary_role` are provisional.
        """
    )
    mo.ui.table(
        dictionary.select(
            [
                "ordinal",
                "column_name",
                "data_type",
                "null_pct",
                "distinct_count",
                "description",
                "preliminary_role",
                "available_at",
                "notes",
            ]
        ),
        selection=None,
    )
    return (dictionary,)


@app.cell
def _(mo):
    mo.md(
        """
        ## Generated artifacts

        - `docs/phase-1-inventory/db_inventory.md` — inventory report
        - `docs/phase-1-inventory/data_dictionary.md` — readable OILPALM dictionary
        - `docs/phase-1-inventory/erd.md` — core ERD and join map
        - `data/phase-1-inventory/schema_tables.csv` — all tables
        - `data/phase-1-inventory/schema_columns.csv` — all columns
        - `data/phase-1-inventory/key_constraints.csv` — primary/unique keys
        - `data/phase-1-inventory/foreign_keys.csv` — foreign keys
        - `data/phase-1-inventory/key_uniqueness.csv` — candidate-key duplicate checks
        - `data/phase-1-inventory/date_ranges.csv` — date coverage
        - `data/phase-1-inventory/join_coverage.csv` — join coverage
        - `data/phase-1-inventory/oilpalm_dictionary.csv` — dictionary CSV
        """
    )
    return


if __name__ == "__main__":
    app.run()
