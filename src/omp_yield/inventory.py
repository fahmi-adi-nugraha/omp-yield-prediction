"""Database inventory and data-dictionary generation for Phase 1."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import polars as pl

from omp_yield.db import Database

OILPALM = "OILPALM"
INVENTORY_PHASE_DIR = "phase-1-inventory"
INVENTORY_DATA_DIR = "data"


@dataclass(frozen=True)
class JoinSpec:
    """A candidate relationship between a source table and OILPALM."""

    label: str
    table: str
    source_keys: str
    oil_keys: str
    join_on: str
    grain_note: str
    source_filter: str = ""


@dataclass(frozen=True)
class KeySpec:
    """A candidate business key for a table."""

    table: str
    columns: tuple[str, ...]
    grain_note: str


JOIN_SPECS: tuple[JoinSpec, ...] = (
    JoinSpec(
        "block-year",
        "tbl_FN_nutActRec",
        "suEstate AS name, suDivision AS unit, suBlock AS block, Yr AS year",
        "NAME AS name, UNIT AS unit, BLOCK AS block, YEAR AS year",
        "s.name = o.name AND s.unit = o.unit AND s.block = o.block AND s.year = o.year",
        "one row per block-year",
    ),
    JoinSpec(
        "block-year",
        "tbl_HRR_harvests",
        "Estate AS name, UNIT AS unit, BLOCK AS block, Y_Harvest AS year",
        "NAME AS name, UNIT AS unit, BLOCK AS block, YEAR AS year",
        "s.name = o.name AND s.unit = o.unit AND s.block = o.block AND s.year = o.year",
        "many harvest events per block-year",
    ),
    JoinSpec(
        "block-year",
        "tbl_PD_surveys",
        "ESTATE AS name, UNIT AS unit, BLOCK AS block, yrFis AS year",
        "NAME AS name, UNIT AS unit, BLOCK AS block, YEAR AS year",
        "s.name = o.name AND s.unit = o.unit AND s.block = o.block AND s.year = o.year",
        "many pest surveys per block-year",
    ),
    JoinSpec(
        "block-year",
        "tbl_PD_controlAct",
        "ESTATE AS name, UNIT AS unit, BLOCK AS block, yrFis AS year",
        "NAME AS name, UNIT AS unit, BLOCK AS block, YEAR AS year",
        "s.name = o.name AND s.unit = o.unit AND s.block = o.block AND s.year = o.year",
        "many control events per block-year",
    ),
    JoinSpec(
        "block-year",
        "tbl_areasPalmsBIY_blk_mts",
        "suEstate AS name, suDivision AS unit, suBlock AS block, Yr AS year",
        "NAME AS name, UNIT AS unit, BLOCK AS block, YEAR AS year",
        "s.name = o.name AND s.unit = o.unit AND s.block = o.block AND s.year = o.year",
        "one row per block-year",
    ),
    JoinSpec(
        "block-year",
        "tbl_SC_palmCensus",
        "suEstate AS name, suDivision AS unit, suBlock AS block, validFromYr AS year",
        "NAME AS name, UNIT AS unit, BLOCK AS block, YEAR AS year",
        "s.name = o.name AND s.unit = o.unit AND s.block = o.block AND s.year = o.year",
        "census snapshot per block-year",
    ),
    JoinSpec(
        "block-year",
        "tbl_FN_soilAnalysis",
        "NAME AS name, UNIT AS unit, BLOCK AS block, YEAR AS year",
        "NAME AS name, UNIT AS unit, BLOCK AS block, YEAR AS year",
        "s.name = o.name AND s.unit = o.unit AND s.block = o.block AND s.year = o.year",
        "sample events per block-year",
    ),
    JoinSpec(
        "block-year",
        "tbl_BBC_bunchCounts",
        "Estate AS name, Unit AS unit, Block AS block, YEAR(CntDate) AS year",
        "NAME AS name, UNIT AS unit, BLOCK AS block, YEAR AS year",
        "s.name = o.name AND s.unit = o.unit AND s.block = o.block AND s.year = o.year",
        "monthly counts per block-year",
    ),
    JoinSpec(
        "block-year",
        "tbl_BBC_forecastABW",
        "suEstate AS name, suDivision AS unit, suBlock AS block, Yr AS year",
        "NAME AS name, UNIT AS unit, BLOCK AS block, YEAR AS year",
        "s.name = o.name AND s.unit = o.unit AND s.block = o.block AND s.year = o.year",
        "one row per block-year",
    ),
    JoinSpec(
        "block-year",
        "tbl_CB_cropBudgetMt",
        "NAME AS name, UNIT AS unit, BLOCK AS block, YEAR AS year",
        "NAME AS name, UNIT AS unit, BLOCK AS block, YEAR AS year",
        "s.name = o.name AND s.unit = o.unit AND s.block = o.block AND s.year = o.year",
        "one row per block-year",
    ),
    JoinSpec(
        "block-year",
        "tbl_CLA_auditResults",
        "NAME AS name, UNIT AS unit, BLOCK AS block, YEAR AS year",
        "NAME AS name, UNIT AS unit, BLOCK AS block, YEAR AS year",
        "s.name = o.name AND s.unit = o.unit AND s.block = o.block AND s.year = o.year",
        "audit events per block-year",
    ),
    JoinSpec(
        "block-year",
        "tbl_FN_fertActInorg_mts",
        "suEstate AS name, suDivision AS unit, suBlock AS block, Yr AS year",
        "NAME AS name, UNIT AS unit, BLOCK AS block, YEAR AS year",
        "s.name = o.name AND s.unit = o.unit AND s.block = o.block AND s.year = o.year",
        "many fertilizer products per block-year",
    ),
    JoinSpec(
        "block-year",
        "tbl_FN_fertActOrg_mts",
        "suEstate AS name, suDivision AS unit, suBlock AS block, Yr AS year",
        "NAME AS name, UNIT AS unit, BLOCK AS block, YEAR AS year",
        "s.name = o.name AND s.unit = o.unit AND s.block = o.block AND s.year = o.year",
        "many organic products per block-year",
    ),
    JoinSpec(
        "block-year",
        "tbl_FN_fertRecInorg_mts",
        "suEstate AS name, suDivision AS unit, suBlock AS block, Yr AS year",
        "NAME AS name, UNIT AS unit, BLOCK AS block, YEAR AS year",
        "s.name = o.name AND s.unit = o.unit AND s.block = o.block AND s.year = o.year",
        "many fertilizer recommendations per block-year",
    ),
    JoinSpec(
        "block-year",
        "tbl_FN_fertRecOrg_mts",
        "suEstate AS name, suDivision AS unit, suBlock AS block, Yr AS year",
        "NAME AS name, UNIT AS unit, BLOCK AS block, YEAR AS year",
        "s.name = o.name AND s.unit = o.unit AND s.block = o.block AND s.year = o.year",
        "many organic recommendations per block-year",
    ),
    JoinSpec(
        "block-year",
        "tbl_PCD_pesticideAct_dt",
        "suEstate AS name, suDivision AS unit, suBlock AS block, yrFis AS year",
        "NAME AS name, UNIT AS unit, BLOCK AS block, YEAR AS year",
        "s.name = o.name AND s.unit = o.unit AND s.block = o.block AND s.year = o.year",
        "pesticide application events per block-year",
    ),
    JoinSpec(
        "block-year",
        "tbl_PCD_pesticideRec_mts",
        "suEstate AS name, suDivision AS unit, suBlock AS block, Yr AS year",
        "NAME AS name, UNIT AS unit, BLOCK AS block, YEAR AS year",
        "s.name = o.name AND s.unit = o.unit AND s.block = o.block AND s.year = o.year",
        "one recommendation row per block-year/product",
    ),
    JoinSpec(
        "block-only",
        "tbl_planting",
        "Estate AS name, Unit AS unit, Block AS block",
        "NAME AS name, UNIT AS unit, BLOCK AS block",
        "s.name = o.name AND s.unit = o.unit AND s.block = o.block",
        "one or more planting cycles per block",
    ),
    JoinSpec(
        "block-only",
        "tbl_SC_areas",
        "suEstate AS name, suDivision AS unit, suBlock AS block",
        "NAME AS name, UNIT AS unit, BLOCK AS block",
        "s.name = o.name AND s.unit = o.unit AND s.block = o.block",
        "effective-dated area records per block",
    ),
    JoinSpec(
        "block-only",
        "tbl_GIS_blocks",
        "suEstate AS name, suDivision AS unit, suBlock AS block",
        "NAME AS name, UNIT AS unit, BLOCK AS block",
        "s.name = o.name AND s.unit = o.unit AND s.block = o.block",
        "GIS fragments per block-year",
    ),
    JoinSpec(
        "division",
        "tbl_suDivisions",
        "suEstate AS name, suDivision AS unit",
        "NAME AS name, UNIT AS unit",
        "s.name = o.name AND s.unit = o.unit",
        "one row per division",
    ),
    JoinSpec(
        "weather-station-year",
        "tbl_CW_weatherAndWater",
        "R_Name AS name, R_UNIT AS station, CAST(R_YEAR AS int) AS year",
        "NAME AS name, ID_WeatherStation AS station, YEAR AS year",
        "s.name = o.name AND s.station = o.station AND s.year = o.year",
        "one row per station-year",
    ),
)

KEY_SPECS: tuple[KeySpec, ...] = (
    KeySpec("OILPALM", ("NAME", "UNIT", "BLOCK", "YEAR"), "block-year"),
    KeySpec("tbl_FN_nutActRec", ("suEstate", "suDivision", "suBlock", "Yr"), "block-year"),
    KeySpec(
        "tbl_FN_fertActInorg_mts",
        ("suEstate", "suDivision", "suBlock", "Yr", "fertName", "fertAppMeth"),
        "block-year-product-method",
    ),
    KeySpec(
        "tbl_FN_fertActOrg_mts",
        ("suEstate", "suDivision", "suBlock", "Yr", "fertName", "fertAppMeth"),
        "block-year-product-method",
    ),
    KeySpec(
        "tbl_FN_fertRecInorg_mts",
        ("suEstate", "suDivision", "suBlock", "Yr", "fertName", "fertAppMeth"),
        "block-year-product-method",
    ),
    KeySpec(
        "tbl_FN_fertRecOrg_mts",
        ("suEstate", "suDivision", "suBlock", "Yr", "fertName", "fertAppMeth"),
        "block-year-product-method",
    ),
    KeySpec(
        "tbl_HRR_harvests",
        ("Estate", "UNIT", "BLOCK", "ID_Card", "D_Harvest"),
        "block-harvest-card-date",
    ),
    KeySpec(
        "tbl_PD_surveys",
        ("ESTATE", "UNIT", "BLOCK", "ID_Rep", "D_Survey", "PestName"),
        "block-survey-pest",
    ),
    KeySpec(
        "tbl_PD_controlAct",
        ("ESTATE", "UNIT", "BLOCK", "ID_Rep", "Dt_App", "Control_Name"),
        "block-control-event",
    ),
    KeySpec("tbl_CW_weatherAndWater", ("R_Name", "R_UNIT", "R_YEAR"), "station-year"),
    KeySpec(
        "tbl_areasPalmsBIY_blk_mts",
        ("suEstate", "suDivision", "suBlock", "Yr"),
        "block-year",
    ),
    KeySpec(
        "tbl_SC_palmCensus",
        ("suEstate", "suDivision", "suBlock", "validFromYr", "validFromMt"),
        "block-year-month-snapshot",
    ),
    KeySpec("tbl_FN_soilAnalysis", ("NAME", "UNIT", "BLOCK", "SA_DATE", "SA_TYPE"), "block-sample"),
    KeySpec("tbl_BBC_bunchCounts", ("Estate", "Unit", "Block", "CntDate"), "block-month"),
    KeySpec("tbl_BBC_forecastABW", ("suEstate", "suDivision", "suBlock", "Yr"), "block-year"),
    KeySpec("tbl_CB_cropBudgetMt", ("NAME", "UNIT", "BLOCK", "YEAR"), "block-year"),
    KeySpec(
        "tbl_CLA_auditResults",
        ("NAME", "UNIT", "BLOCK", "YEAR", "AuditDate", "Row_1", "Row_2"),
        "block-audit-date-row-pair",
    ),
    KeySpec(
        "tbl_PCD_pesticideAct_dt",
        ("suEstate", "suDivision", "suBlock", "pcdAppDt", "pcdProdName", "pestEventID"),
        "block-application-event",
    ),
    KeySpec(
        "tbl_PCD_pesticideRec_mts",
        ("suEstate", "suDivision", "suBlock", "Yr", "pcdProdName"),
        "block-year-product",
    ),
    KeySpec("tbl_planting", ("Estate", "Unit", "Block", "plantingCycle"), "block-planting-cycle"),
    KeySpec(
        "tbl_SC_areas",
        ("suEstate", "suDivision", "suBlock", "validFromYr", "validFromMt"),
        "block-effective-date",
    ),
    KeySpec(
        "tbl_GIS_blocks",
        ("Yr", "suEstate", "suDivision", "suBlock", "fragmentIdx"),
        "block-year-fragment",
    ),
    KeySpec("tbl_suDivisions", ("suEstate", "suDivision"), "division"),
    KeySpec("tbl_suFields", ("suEstate", "suDivision", "suField"), "field"),
)

_DATE_TYPES = {"date", "datetime", "datetime2", "smalldatetime", "datetimeoffset"}

_ID_COLUMNS = {
    "NAME",
    "UNIT",
    "BLOCK",
    "YEAR",
    "UNIT_SUB",
    "suPlantation",
    "BlockInYield",
    "HarvestIndex",
    "Upkeep_Index",
}

_TARGET_DERIVED_PREFIXES = (
    "Y_01",
    "Y_02",
    "Y_03",
    "Y_04",
    "Y_05",
    "Y_06",
    "Y_07",
    "Y_08",
    "Y_09",
    "Y_10",
    "Y_11",
    "Y_12",
)

_EMPTY_OR_CONSTANT = {
    "soilAcidity",
    "waterTableDepth",
    "trunkDiameter",
    "LAI",
    "LAI_FrondArea",
    "LA_GreenLeaves",
    "LA_Rachis_length",
    "MillDistance",
    "maturityAge_mt",
    "NAME",
}

_LEAKAGE_NOTES = {
    "Y_TOTAL_ton": "Target.",
    "Y_TOTAL_bunches": "Target-derived: monthly bunch totals.",
    "Y_TH": "Derived: Y_TOTAL_ton / area_ha.",
    "Y_TH_GAP": "Derived: Y_TH - Y_TH_POT.",
    "Y_GAP_Percent": "Derived: (Y_TH - Y_TH_POT) / Y_TH_POT.",
    "Y_KGB": "Derived: 1000 * Y_TOTAL_ton / Y_TOTAL_bunches.",
    "Y_BNTREE": "Derived: Y_TOTAL_bunches / palmStandMature_p.",
    "Y_per_manday": "Derived: Y_TOTAL_ton / Y_TOTAL_mandays.",
    "Y_TOTAL_mandays": "Target-derived harvest effort.",
    "Y_TOTAL_rounds": "Target-derived harvest effort.",
    "Y_AVG_harvest_int": "Target-derived harvest timing.",
    "BlockInYield": "Maturity flag: 0 immature, -1 in yield.",
    "HarvestIndex": "Sort order, not a predictor.",
    "Upkeep_Index": "Sort order, not a predictor.",
    "Y_TH_POT": "Review: OMP potential-yield estimate; confirm source and timing.",
    "MarkerYield": "Review: expert yield assessment; confirm timing.",
    "MarkerLeaf_N": "Review: expert leaf assessment; likely redundant with LA_N.",
    "MarkerLeaf_P": "Review: expert leaf assessment; likely redundant with LA_P.",
    "MarkerLeaf_K": "Review: expert leaf assessment; likely redundant with LA_K.",
    "MarkerLeaf_Mg": "Review: expert leaf assessment; likely redundant with LA_Mg.",
    "areaIY_ha": "Review: inconsistent for 124H; derive maturity from Growth_Period.",
    "SA_TextClass": "~99% null in the database; use soil analysis texture if needed.",
}

_MANAGEMENT_COLUMNS = {
    "Pruning",
    "HarvesterAccess",
    "IsAbblation",
    "AblReps",
    "AblStart",
    "AblEnd",
}


def quote_ident(name: str) -> str:
    """Quote a SQL Server identifier."""

    return "[" + name.replace("]", "]]") + "]"


def _table(name: str) -> str:
    return f"{quote_ident('dbo')}.{quote_ident(name)}"


def _read(db: Database, sql: str) -> pl.DataFrame:
    # Inventory queries must not be truncated by the interactive row limit.
    return db.read_frame(sql)


def table_inventory(db: Database) -> pl.DataFrame:
    """Return table names, row counts, and column counts."""

    sql = """
    SELECT
        s.name AS schema_name,
        t.name AS table_name,
        (
            SELECT SUM(p.rows)
            FROM sys.partitions p
            WHERE p.object_id = t.object_id
              AND p.index_id IN (0, 1)
        ) AS row_count,
        (
            SELECT COUNT(*)
            FROM sys.columns c
            WHERE c.object_id = t.object_id
        ) AS column_count
    FROM sys.tables t
    JOIN sys.schemas s ON s.schema_id = t.schema_id
    ORDER BY row_count DESC, s.name, t.name
    """
    return _read(db, sql)


def column_inventory(db: Database) -> pl.DataFrame:
    """Return all column metadata."""

    sql = """
    SELECT
        TABLE_SCHEMA AS schema_name,
        TABLE_NAME AS table_name,
        ORDINAL_POSITION AS ordinal,
        COLUMN_NAME AS column_name,
        DATA_TYPE AS data_type,
        IS_NULLABLE AS is_nullable,
        CHARACTER_MAXIMUM_LENGTH AS char_max_length,
        NUMERIC_PRECISION AS numeric_precision,
        NUMERIC_SCALE AS numeric_scale,
        DATETIME_PRECISION AS datetime_precision
    FROM INFORMATION_SCHEMA.COLUMNS
    ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION
    """
    return _read(db, sql)


def key_inventory(db: Database) -> pl.DataFrame:
    """Return primary-key and unique-key constraints with their columns."""

    sql = """
    SELECT
        s.name AS schema_name,
        t.name AS table_name,
        kc.name AS key_name,
        kc.type_desc AS key_type,
        STRING_AGG(CONVERT(nvarchar(max), c.name), ', ')
            WITHIN GROUP (ORDER BY ic.key_ordinal) AS key_columns
    FROM sys.key_constraints kc
    JOIN sys.tables t ON t.object_id = kc.parent_object_id
    JOIN sys.schemas s ON s.schema_id = t.schema_id
    JOIN sys.index_columns ic
      ON ic.object_id = kc.parent_object_id
     AND ic.index_id = kc.unique_index_id
    JOIN sys.columns c
      ON c.object_id = ic.object_id
     AND c.column_id = ic.column_id
    GROUP BY s.name, t.name, kc.name, kc.type_desc
    ORDER BY s.name, t.name, kc.name
    """
    return _read(db, sql)


def foreign_key_inventory(db: Database) -> pl.DataFrame:
    """Return foreign keys with child and parent columns."""

    sql = """
    SELECT
        fk.name AS foreign_key_name,
        cs.name AS child_schema,
        ct.name AS child_table,
        ps.name AS parent_schema,
        pt.name AS parent_table,
        cc.name AS child_column,
        pc.name AS parent_column,
        fkc.constraint_column_id AS ordinal
    FROM sys.foreign_keys fk
    JOIN sys.tables ct ON ct.object_id = fk.parent_object_id
    JOIN sys.schemas cs ON cs.schema_id = ct.schema_id
    JOIN sys.tables pt ON pt.object_id = fk.referenced_object_id
    JOIN sys.schemas ps ON ps.schema_id = pt.schema_id
    JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id = fk.object_id
    JOIN sys.columns cc
      ON cc.object_id = fkc.parent_object_id
     AND cc.column_id = fkc.parent_column_id
    JOIN sys.columns pc
      ON pc.object_id = fkc.referenced_object_id
     AND pc.column_id = fkc.referenced_column_id
    ORDER BY fk.name, fkc.constraint_column_id
    """
    rows = _read(db, sql)
    if rows.height == 0:
        return rows

    return (
        rows.group_by("foreign_key_name", "child_schema", "child_table", "parent_schema", "parent_table")
        .agg(
            pl.col("child_column").sort_by("ordinal").alias("child_columns"),
            pl.col("parent_column").sort_by("ordinal").alias("parent_columns"),
        )
        .with_columns(
            pl.col("child_columns").list.join(", "),
            pl.col("parent_columns").list.join(", "),
        )
        .sort("child_table", "foreign_key_name")
    )


def key_uniqueness(db: Database) -> pl.DataFrame:
    """Check candidate business keys for duplicates."""

    selects: list[str] = []
    for spec in KEY_SPECS:
        cols = ", ".join(
            f"ISNULL(CONVERT(nvarchar(4000), {quote_ident(c)}), '<NULL>')" for c in spec.columns
        )
        key_expr = f"CONCAT_WS('|', {cols})"
        selects.append(
            f"""
            SELECT
                '{spec.table}' AS table_name,
                COUNT(*) AS row_count,
                COUNT(DISTINCT {key_expr}) AS distinct_keys,
                '{", ".join(spec.columns)}' AS key_columns,
                '{spec.grain_note}' AS grain_note
            FROM {_table(spec.table)}
            """
        )
    sql = "\nUNION ALL\n".join(selects) + "\nORDER BY table_name"
    frame = _read(db, sql)
    return frame.with_columns(
        (pl.col("row_count") - pl.col("distinct_keys")).alias("duplicate_rows"),
        pl.when(pl.col("distinct_keys") > 0)
        .then(pl.col("row_count") / pl.col("distinct_keys"))
        .otherwise(None)
        .alias("rows_per_key"),
    )


def date_range_inventory(db: Database, columns: pl.DataFrame) -> pl.DataFrame:
    """Return min/max/non-null counts for every date-like column."""

    date_cols = columns.filter(pl.col("data_type").is_in(sorted(_DATE_TYPES)))
    if date_cols.height == 0:
        return pl.DataFrame(
            schema={
                "schema_name": pl.String,
                "table_name": pl.String,
                "column_name": pl.String,
                "non_null_count": pl.Int64,
                "min_value": pl.String,
                "max_value": pl.String,
            }
        )

    selects: list[str] = []
    for row in date_cols.iter_rows(named=True):
        schema = row["schema_name"]
        table = row["table_name"]
        column = row["column_name"]
        selects.append(
            f"""
            SELECT
                '{schema}' AS schema_name,
                '{table}' AS table_name,
                '{column}' AS column_name,
                COUNT({quote_ident(column)}) AS non_null_count,
                CONVERT(nvarchar(50), MIN({quote_ident(column)})) AS min_value,
                CONVERT(nvarchar(50), MAX({quote_ident(column)})) AS max_value
            FROM {quote_ident(schema)}.{quote_ident(table)}
            """
        )

    frames: list[pl.DataFrame] = []
    batch_size = 40
    for start in range(0, len(selects), batch_size):
        sql = "\nUNION ALL\n".join(selects[start : start + batch_size])
        frames.append(_read(db, sql))
    return pl.concat(frames, how="vertical_relaxed").sort("table_name", "column_name")


def join_coverage(db: Database) -> pl.DataFrame:
    """Measure candidate table coverage against OILPALM keys."""

    selects: list[str] = []
    for spec in JOIN_SPECS:
        where = f"WHERE {spec.source_filter}" if spec.source_filter else ""
        src = f"(SELECT DISTINCT {spec.source_keys} FROM {_table(spec.table)} {where})"
        oil = f"(SELECT DISTINCT {spec.oil_keys} FROM {_table(OILPALM)})"
        selects.append(
            f"""
            SELECT
                '{spec.label}' AS join_type,
                '{spec.table}' AS source_table,
                '{spec.grain_note}' AS source_grain,
                (SELECT COUNT(*) FROM {src} s) AS source_keys,
                (SELECT COUNT(*) FROM {src} s JOIN {oil} o ON {spec.join_on}) AS matched_source_keys,
                (SELECT COUNT(*) FROM {oil} o JOIN {src} s ON {spec.join_on}) AS matched_oil_rows,
                (SELECT COUNT(*) FROM {oil} o) AS oil_rows
            """
        )
    sql = "\nUNION ALL\n".join(selects) + "\nORDER BY source_table"
    frame = _read(db, sql)
    return frame.with_columns(
        (pl.col("matched_source_keys") / pl.col("source_keys") * 100).round(1).alias(
            "matched_source_pct"
        ),
        (pl.col("matched_oil_rows") / pl.col("oil_rows") * 100).round(1).alias("matched_oil_pct"),
    )


def growth_periods(db: Database) -> pl.DataFrame:
    """Return the OMP growth-period definitions."""

    return _read(
        db,
        """
        SELECT Growth_Period, AgeStart, AgeEnd, GPDesc
        FROM [dbo].[tbl_sys_growthPeriods]
        ORDER BY AgeStart
        """,
    )


def estate_hierarchy(db: Database) -> pl.DataFrame:
    """Return estate -> division -> block counts and year coverage."""

    return _read(
        db,
        """
        SELECT
            NAME AS estate,
            suPlantation AS region,
            UNIT AS division,
            COUNT(DISTINCT BLOCK) AS blocks,
            COUNT(*) AS block_years,
            MIN(YEAR) AS min_year,
            MAX(YEAR) AS max_year
        FROM [dbo].[OILPALM]
        GROUP BY NAME, suPlantation, UNIT
        ORDER BY NAME, UNIT
        """,
    )


def oilpalm_dictionary(db: Database) -> pl.DataFrame:
    """Build the OILPALM data dictionary with descriptions and quality notes."""

    columns = column_inventory(db).filter(pl.col("table_name") == OILPALM)
    col_names = columns["column_name"].to_list()

    # Read explicit columns, not SELECT *.
    select_list = ", ".join(quote_ident(c) for c in col_names)
    raw = db.read_frame(f"SELECT {select_list} FROM {_table(OILPALM)}")

    def missing(c: str) -> pl.Expr:
        blank = (pl.col(c).cast(pl.String).str.strip_chars() == "").fill_null(False)
        return pl.col(c).is_null() | blank

    stats = raw.select(
        [missing(c).sum().alias(f"{c}__nulls") for c in col_names]
        + [
            pl.col(c).filter(~missing(c)).n_unique().alias(f"{c}__distinct")
            for c in col_names
        ]
    ).row(0, named=True)

    descriptions = _read(
        db,
        """
        SELECT fldName AS column_name, fldDescr AS description, fldCat AS category, fldUnit AS unit
        FROM [dbo].[tbl_sys_fldDefs]
        WHERE fldName IS NOT NULL
        """,
    )
    ude = _read(
        db,
        """
        SELECT fldName AS column_name, fldDescr AS description, fldCat AS category, fldUnit AS unit
        FROM [dbo].[tbl_sys_UDE_fields]
        WHERE fldName IS NOT NULL
        """,
    )
    descriptions = (
        pl.concat([descriptions, ude], how="vertical_relaxed")
        .filter(pl.col("description").is_not_null())
        .unique(subset=["column_name"], keep="first")
    )

    dictionary = columns.join(descriptions, on="column_name", how="left")
    dictionary = dictionary.with_columns(
        pl.col("column_name").replace_strict(
            {c: stats[f"{c}__nulls"] for c in col_names}, default=None
        ).alias("null_count"),
        pl.col("column_name").replace_strict(
            {c: stats[f"{c}__distinct"] for c in col_names}, default=None
        ).alias("distinct_count"),
    )
    dictionary = dictionary.with_columns(
        (pl.col("null_count") / raw.height * 100).round(1).alias("null_pct")
    )
    dictionary = dictionary.with_columns(
        pl.struct(["column_name", "data_type", "description"]).map_elements(
            _preliminary_role, return_dtype=pl.String
        ).alias("preliminary_role"),
        pl.struct(["column_name", "data_type"]).map_elements(
            _available_at, return_dtype=pl.String
        ).alias("available_at"),
        pl.col("column_name").replace_strict(_LEAKAGE_NOTES, default="").alias("notes"),
    )
    return dictionary.select(
        "ordinal",
        "column_name",
        "data_type",
        "is_nullable",
        "null_count",
        "null_pct",
        "distinct_count",
        "category",
        "unit",
        "description",
        "preliminary_role",
        "available_at",
        "notes",
    ).sort("ordinal")


def _preliminary_role(row: dict[str, object]) -> str:
    column = str(row["column_name"])
    data_type = str(row["data_type"])
    if column == "Y_TOTAL_ton":
        return "target"
    if column in _ID_COLUMNS:
        return "id"
    if column in _MANAGEMENT_COLUMNS:
        return "management"
    if column in _EMPTY_OR_CONSTANT:
        return "empty_or_constant"
    if column.startswith("LA_"):
        return "leaf_context"
    if column.startswith(_TARGET_DERIVED_PREFIXES) or column in {
        "Y_TOTAL_bunches",
        "Y_TH",
        "Y_TH_GAP",
        "Y_GAP_Percent",
        "Y_KGB",
        "Y_BNTREE",
        "Y_per_manday",
        "Y_TOTAL_mandays",
        "Y_TOTAL_rounds",
        "Y_AVG_harvest_int",
        "Y_TH_POT",
        "MarkerYield",
    }:
        return "target_derived_or_review"
    if data_type in {"date", "datetime", "datetime2", "smalldatetime"}:
        return "timing"
    return "context"


def _available_at(row: dict[str, object]) -> str:
    column = str(row["column_name"])
    if column == "Y_TOTAL_ton" or column.startswith("Y_") or column.startswith(_TARGET_DERIVED_PREFIXES):
        return "post_season"
    if column in {"D_FHARVEST", "M_FHARVEST", "MarkerYield"}:
        return "post_season_or_review"
    if column.startswith("LA_"):
        return "mid_season"
    return "pre_season"


def markdown_table(
    frame: pl.DataFrame,
    columns: Iterable[str] | None = None,
    *,
    max_rows: int | None = None,
    max_text: int = 120,
) -> str:
    """Render a Polars frame as a GitHub-flavored Markdown table."""

    selected = list(columns) if columns else frame.columns
    selected = [c for c in selected if c in frame.columns]
    data = frame.select(selected)
    if max_rows is not None:
        data = data.head(max_rows)

    def fmt(value: object) -> str:
        if value is None:
            return ""
        text = str(value).replace("\n", "<br>").replace("|", "\\|")
        return text[:max_text] + ("…" if len(text) > max_text else "")

    lines = [
        "| " + " | ".join(selected) + " |",
        "|" + "|".join("---" for _ in selected) + "|",
    ]
    for row in data.iter_rows():
        lines.append("| " + " | ".join(fmt(v) for v in row) + " |")
    return "\n".join(lines)


def write_inventory_reports(db: Database, docs_dir: Path, reports_dir: Path) -> dict[str, Path]:
    """Generate Phase 1 CSVs, Markdown reports, and the data dictionary."""

    phase_dir = docs_dir / INVENTORY_PHASE_DIR
    data_dir = phase_dir / INVENTORY_DATA_DIR
    phase_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    tables = table_inventory(db)
    columns = column_inventory(db)
    keys = key_inventory(db)
    fks = foreign_key_inventory(db)
    key_checks = key_uniqueness(db)
    dates = date_range_inventory(db, columns)
    coverage = join_coverage(db)
    periods = growth_periods(db)
    hierarchy = estate_hierarchy(db)
    dictionary = oilpalm_dictionary(db)

    artifacts: dict[str, Path] = {}

    def write_csv(name: str, frame: pl.DataFrame) -> None:
        path = data_dir / name
        frame.write_csv(path)
        artifacts[name] = path

    write_csv("schema_tables.csv", tables)
    write_csv("schema_columns.csv", columns)
    write_csv("key_constraints.csv", keys)
    write_csv("foreign_keys.csv", fks)
    write_csv("key_uniqueness.csv", key_checks)
    write_csv("date_ranges.csv", dates)
    write_csv("join_coverage.csv", coverage)
    write_csv("oilpalm_dictionary.csv", dictionary)

    total_rows = int(tables["row_count"].sum()) if tables.height else 0
    total_columns = columns.height
    oilpalm_rows = int(
        tables.filter(pl.col("table_name") == OILPALM)["row_count"].item()
    )
    top_tables = tables.head(25)

    inventory_md = f"""# Database Inventory

Generated by `uv run omp-yield inventory`.

## Summary

| Metric | Value |
|---|---:|
| Tables | {tables.height:,} |
| Columns | {total_columns:,} |
| Rows across tables (partition count) | {total_rows:,} |
| Key constraints | {keys.height:,} |
| Foreign keys | {fks.height:,} |
| Date-like columns | {dates.height:,} |
| `OILPALM` rows | {oilpalm_rows:,} |

## Core table grains

{markdown_table(key_checks.filter(pl.col("table_name").is_in(["OILPALM", "tbl_FN_nutActRec", "tbl_HRR_harvests", "tbl_PD_surveys", "tbl_CW_weatherAndWater", "tbl_areasPalmsBIY_blk_mts", "tbl_BBC_bunchCounts", "tbl_planting"])), ["table_name", "row_count", "distinct_keys", "duplicate_rows", "key_columns", "grain_note"])}

## Candidate join coverage against `OILPALM`

Match rates are computed on distinct source keys. A high `matched_source_pct`
means the source covers OILPALM. `matched_oil_pct` means OILPALM rows have a
matching source record.

{markdown_table(coverage, ["source_table", "join_type", "source_keys", "matched_source_keys", "matched_source_pct", "matched_oil_rows", "matched_oil_pct", "source_grain"])}

## Top tables by row count

{markdown_table(top_tables, ["schema_name", "table_name", "row_count", "column_count"])}

Full table inventory: `data/schema_tables.csv`.

## Growth periods

{markdown_table(periods, ["Growth_Period", "AgeStart", "AgeEnd", "GPDesc"])}

Mature model filter: `Growth_Period IN ('SAYP', 'PYP', 'DYP')`.

## Estate -> division hierarchy

{markdown_table(hierarchy, ["estate", "region", "division", "blocks", "block_years", "min_year", "max_year"])}

## Key constraints

{markdown_table(keys.head(40), max_text=180)}

Full key inventory: `data/key_constraints.csv`.

## Foreign keys

{markdown_table(fks.head(40), max_text=180)}

Full foreign-key inventory: `data/foreign_keys.csv`.

## Date ranges

Core date coverage:

{markdown_table(dates.filter(pl.col("table_name").is_in(["OILPALM", "tbl_HRR_harvests", "tbl_PD_surveys", "tbl_CW_weatherAndWater", "tbl_FN_soilAnalysis", "tbl_BBC_bunchCounts", "tbl_CLA_auditResults"])).sort("table_name", "column_name"))}

Full date-range inventory: `data/date_ranges.csv`.

## Artifacts

| File | Contents |
|---|---|
| `data/schema_tables.csv` | All tables, row counts, column counts |
| `data/schema_columns.csv` | All columns and data types |
| `data/key_constraints.csv` | Primary/unique keys |
| `data/foreign_keys.csv` | Foreign keys |
| `data/key_uniqueness.csv` | Candidate business-key duplicate checks |
| `data/date_ranges.csv` | Min/max date per date-like column |
| `data/join_coverage.csv` | Candidate join coverage |
| `data/oilpalm_dictionary.csv` | OILPALM data dictionary |
| `data_dictionary.md` | Readable OILPALM dictionary |
| `erd.md` | Core ERD and join map |
"""
    inventory_path = phase_dir / "db_inventory.md"
    inventory_path.write_text(inventory_md)
    artifacts["db_inventory.md"] = inventory_path

    dictionary_md = f"""# OILPALM Data Dictionary

Generated by `uv run omp-yield inventory`.

`OILPALM` has {dictionary.height:,} columns and 2,909 rows. This dictionary is a
starting point for Phase 3 feature decisions; it is not the final feature list.
`null_count` treats NULL and blank strings as missing.

## Known leakage and quality notes

- `Y_TH` is exactly `Y_TOTAL_ton / area_ha`.
- `Y_KGB` is exactly `1000 * Y_TOTAL_ton / Y_TOTAL_bunches`.
- Monthly `Y_*` columns sum exactly to annual totals.
- `Y_TH_GAP`, `Y_GAP_Percent`, `Y_BNTREE`, and `Y_per_manday` are derived from actual yield.
- `BlockInYield` is a maturity flag; `HarvestIndex` and `Upkeep_Index` are sort orders.
- `Y_TH_POT` and `MarkerYield` require timing/source review before use.
- `areaIY_ha` is inconsistent for `124H`; do not use it as the primary maturity filter.
- `SA_TextClass` is ~99% null in the database.

## Columns

{markdown_table(dictionary, ["ordinal", "column_name", "data_type", "is_nullable", "null_count", "null_pct", "distinct_count", "category", "unit", "description", "preliminary_role", "available_at", "notes"], max_text=180)}

Full CSV: `data/oilpalm_dictionary.csv`.
"""
    dictionary_path = phase_dir / "data_dictionary.md"
    dictionary_path.write_text(dictionary_md)
    artifacts["data_dictionary.md"] = dictionary_path

    erd_md = """# Core ERD and Join Map

The operational key chain is:

```text
NAME / suEstate / Estate / ESTATE / R_Name
  -> UNIT / suDivision / Unit / UNIT
    -> BLOCK / suBlock / Block
      -> YEAR / Yr / yrFis / Y_Harvest
```

`tbl_CW_weatherAndWater` is the exception: `OILPALM.ID_WeatherStation` joins to
`R_UNIT`, not to `OILPALM.UNIT`.

```mermaid
erDiagram
    OILPALM {
        nvarchar NAME
        nvarchar UNIT
        nvarchar BLOCK
        int YEAR
        nvarchar Growth_Period
        float area_ha
        int palmStandMature_p
        float Y_TOTAL_ton
    }
    tbl_FN_nutActRec {
        nvarchar suEstate
        nvarchar suDivision
        nvarchar suBlock
        int Yr
        float nutActInorgN_kg_p
        float nutActInorgK2O_kg_p
        float nutRecInorgN_kg_p
    }
    tbl_HRR_harvests {
        nvarchar Estate
        nvarchar UNIT
        nvarchar BLOCK
        datetime2 D_Harvest
        int Y_Harvest
        float Y_FFB
        int Y_BunchNo
    }
    tbl_PD_surveys {
        nvarchar ESTATE
        nvarchar UNIT
        nvarchar BLOCK
        datetime2 D_Survey
        int yrFis
        nvarchar PestName
        int P_Severity
    }
    tbl_CW_weatherAndWater {
        nvarchar R_Name
        nvarchar R_UNIT
        float R_YEAR
        float R_rain_mm_1
        int R_NO_dry_month
        float R_waterdeficit
    }
    tbl_areasPalmsBIY_blk_mts {
        nvarchar suEstate
        nvarchar suDivision
        nvarchar suBlock
        int Yr
        int palmAgeMt1_mt
        int palmStandMatureYr_p
    }
    tbl_BBC_bunchCounts {
        nvarchar Estate
        nvarchar Unit
        nvarchar Block
        datetime2 CntDate
        int NoOfPalm
        int BlackBunch
    }
    tbl_planting {
        nvarchar Estate
        nvarchar Unit
        nvarchar Block
        datetime2 Dt_Planted
        nvarchar PMat
        float PlantingDensity
    }
    tbl_PD_controlAct {
        nvarchar ESTATE
        nvarchar UNIT
        nvarchar BLOCK
        datetime2 Dt_App
        int yrFis
        nvarchar Control_Name
        float Amount_App
    }
    tbl_PCD_pesticideAct_dt {
        nvarchar suEstate
        nvarchar suDivision
        nvarchar suBlock
        datetime2 pcdAppDt
        int yrFis
        nvarchar pcdProdName
        float pcdApp_kg
    }
    tbl_FN_soilAnalysis {
        nvarchar NAME
        nvarchar UNIT
        nvarchar BLOCK
        int YEAR
        datetime2 SA_DATE
        float SA_PH_H2O
        float SA_CEC
        float SA_SOM
    }
    tbl_CB_cropBudgetMt {
        nvarchar NAME
        nvarchar UNIT
        nvarchar BLOCK
        int YEAR
        float Y_total_ton_bud
    }
    tbl_CLA_auditResults {
        nvarchar NAME
        nvarchar UNIT
        nvarchar BLOCK
        int YEAR
        datetime2 AuditDate
        int B_harvested
        int B_unharvested
    }

    OILPALM ||--o| tbl_FN_nutActRec : "block-year nutrients"
    OILPALM ||--o{ tbl_HRR_harvests : "block-year harvest events"
    OILPALM ||--o{ tbl_PD_surveys : "block-year pest surveys"
    OILPALM ||--o{ tbl_PD_controlAct : "block-year disease control"
    OILPALM ||--o{ tbl_PCD_pesticideAct_dt : "block-year weed control"
    OILPALM ||--o| tbl_CW_weatherAndWater : "weather station-year"
    OILPALM ||--o| tbl_areasPalmsBIY_blk_mts : "block-year stand"
    OILPALM ||--o{ tbl_BBC_bunchCounts : "block-month bunch counts"
    OILPALM ||--o| tbl_planting : "block planting"
    OILPALM ||--o{ tbl_FN_soilAnalysis : "block-year soil samples"
    OILPALM ||--o| tbl_CB_cropBudgetMt : "block-year budget"
    OILPALM ||--o{ tbl_CLA_auditResults : "block-year audit"
```

## Notes

- `tbl_CW_weatherAndWater` is station-year grain, not block-year.
- `tbl_HRR_harvests`, `tbl_PD_surveys`, `tbl_BBC_bunchCounts`, and
  `tbl_FN_soilAnalysis` are event/monthly tables; aggregate before joining.
- `tbl_CB_cropBudgetMt` is a benchmark, not a feature; it appears backfilled.
- `tbl_BBC_forecastABW` has 2023-2025 data and one null 2026 row; it cannot
  support a 2026 baseline forecast as-is.
"""
    erd_path = phase_dir / "erd.md"
    erd_path.write_text(erd_md)
    artifacts["erd.md"] = erd_path

    summary_path = reports_dir / "01_db_inventory.html"
    summary_path.write_text(
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>OMP DB Inventory</title></head><body>"
        "<h1>OMP Database Inventory</h1>"
        f"<p>Tables: {tables.height:,}; columns: {total_columns:,}; "
        f"key constraints: {keys.height:,}; foreign keys: {fks.height:,}.</p>"
        "<p>See <code>docs/phase-1-inventory/db_inventory.md</code>, "
        "<code>docs/phase-1-inventory/data_dictionary.md</code>, and "
        "<code>docs/phase-1-inventory/erd.md</code>.</p>"
        "</body></html>"
    )
    artifacts["01_db_inventory.html"] = summary_path

    return artifacts
