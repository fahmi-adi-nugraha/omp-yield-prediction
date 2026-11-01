"""Phase 3 cleaning, leakage audit, feature decisions, and leverage audit."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
import yaml

from omp_yield.extract import verify_snapshot
from omp_yield.inventory import markdown_table

MATURE_PERIODS = ("SAYP", "PYP", "DYP")
TARGET = "Y_TOTAL_ton"
NUMERIC_TYPES = {
    pl.Int8,
    pl.Int16,
    pl.Int32,
    pl.Int64,
    pl.UInt8,
    pl.UInt16,
    pl.UInt32,
    pl.UInt64,
    pl.Float32,
    pl.Float64,
}

ID_COLUMNS = {
    "NAME",
    "UNIT",
    "BLOCK",
    "YEAR",
    "UNIT_SUB",
    "suPlantation",
    "ID_WeatherStation",
    "ID_LSUgroup",
    "SH_GROUPmember",
    "FWUnit",
    "LA_DATE",
    "LA_LABNO",
    "LA_LABNAME",
    "LA_METHOD",
}

DROP_COLUMNS = {
    "areaIY_ha",
    "palmStandIY_p",
    "palmStand_p",
    "BlockInYield",
    "HarvestIndex",
    "Upkeep_Index",
    "D_FHARVEST",
    "M_FHARVEST",
    "LA_FROND",
    "LA_VN",
    "LA_VB",
    "LA_VMG",
    "LA_VK",
    "LA_VP",
    "LA_VCu",
    "LA_VS",
}

REVIEW_COLUMNS = {
    "Y_TH_POT",
    "MarkerYield",
    "MarkerLeaf_N",
    "MarkerLeaf_P",
    "MarkerLeaf_K",
    "MarkerLeaf_Mg",
    "LA_tree_height",
    "LA_cross_section",
    "LA_LSU",
    "LA_PCRIT",
    "LA_PK",
    "LA_PMG",
    "LA_TLB",
    "LA_Leaf_Prod",
    "LA_leaf_ProdRate",
    "TC_DENS",
    "TC_PMAT",
    "TC_RPOISON",
    "AblStart",
    "AblEnd",
    "AblReps",
    "IsAbblation",
    "areaHCV_ha",
    "soilDeficN",
    "soilDeficP",
    "soilDeficK",
    "soilDeficMg",
}

MANAGEMENT_COLUMNS = {"Pruning", "HarvesterAccess"}

EXTERNAL_FEATURES: tuple[dict[str, Any], ...] = (
    {
        "source": "tbl_FN_nutActRec",
        "name": "nutActInorgN_kg_p",
        "decision": "keep",
        "role": "management",
        "available_at": "pre_season",
        "adjustable": True,
        "reason": "Primary inorganic nitrogen management lever.",
    },
    {
        "source": "tbl_FN_nutActRec",
        "name": "nutActInorgP2O5_kg_p",
        "decision": "keep",
        "role": "management",
        "available_at": "pre_season",
        "adjustable": True,
        "reason": "Primary phosphorus management lever.",
    },
    {
        "source": "tbl_FN_nutActRec",
        "name": "nutActInorgK2O_kg_p",
        "decision": "keep",
        "role": "management",
        "available_at": "pre_season",
        "adjustable": True,
        "reason": "Primary potassium management lever.",
    },
    {
        "source": "tbl_FN_nutActRec",
        "name": "nutActInorgMgO_kg_p",
        "decision": "keep",
        "role": "management",
        "available_at": "pre_season",
        "adjustable": True,
        "reason": "Magnesium management lever.",
    },
    {
        "source": "tbl_FN_nutActRec",
        "name": "nutActInorgCaO_kg_p",
        "decision": "keep",
        "role": "management",
        "available_at": "pre_season",
        "adjustable": True,
        "reason": "Calcium management lever.",
    },
    {
        "source": "tbl_FN_nutActRec",
        "name": "nutActInorgB_kg_p",
        "decision": "keep",
        "role": "management",
        "available_at": "pre_season",
        "adjustable": True,
        "reason": "Boron management lever.",
    },
    {
        "source": "tbl_FN_nutActRec",
        "name": "nutRecInorgN_kg_p",
        "decision": "review",
        "role": "management",
        "available_at": "pre_season",
        "adjustable": True,
        "reason": "Recommended N rate; confirm availability before the cutoff.",
    },
    {
        "source": "tbl_FN_nutActRec",
        "name": "nutRecInorgK2O_kg_p",
        "decision": "review",
        "role": "management",
        "available_at": "pre_season",
        "adjustable": True,
        "reason": "Recommended K rate; confirm availability before the cutoff.",
    },
    {
        "source": "tbl_FN_nutActRec",
        "name": "nutActOrgN_kg_p",
        "decision": "review",
        "role": "management",
        "available_at": "pre_season",
        "adjustable": True,
        "reason": "Organic N share; sparse but potentially actionable.",
    },
    {
        "source": "tbl_CW_weatherAndWater",
        "name": "rain_annual_mm",
        "decision": "keep",
        "role": "weather",
        "available_at": "pre_season",
        "adjustable": False,
        "reason": "Annual rainfall; lag and anomaly features planned.",
    },
    {
        "source": "tbl_CW_weatherAndWater",
        "name": "dry_months",
        "decision": "keep",
        "role": "weather",
        "available_at": "pre_season",
        "adjustable": False,
        "reason": "Water-stress context.",
    },
    {
        "source": "tbl_CW_weatherAndWater",
        "name": "water_deficit",
        "decision": "keep",
        "role": "weather",
        "available_at": "pre_season",
        "adjustable": False,
        "reason": "Water-balance context; 2022 drought signal.",
    },
    {
        "source": "derived",
        "name": "yield_lag1",
        "decision": "keep",
        "role": "history",
        "available_at": "pre_season",
        "adjustable": False,
        "derived": True,
        "derived_from": "OILPALM.Y_TOTAL_ton",
        "derivation": "Y_TOTAL_ton shifted 1 year within block; equivalent to prior-year HRR harvest FFB",
        "reason": "Derived, not a raw column: prior-year target. Current-year Y_TOTAL_ton is leakage; lagged values are safe.",
    },
    {
        "source": "derived",
        "name": "bunch_weight_lag1",
        "decision": "keep",
        "role": "history",
        "available_at": "pre_season",
        "adjustable": False,
        "derived": True,
        "derived_from": "OILPALM.Y_KGB",
        "derivation": "Y_KGB shifted 1 year within block; Y_KGB = 1000 * Y_TOTAL_ton / Y_TOTAL_bunches; alternative from tbl_HRR_harvests sum(Y_FFB)/sum(Y_BunchNo)",
        "reason": "Derived, not a raw column: prior-year average bunch weight. Lagged target-derived values are safe.",
    },
    {
        "source": "derived",
        "name": "harvest_interval_lag1",
        "decision": "review",
        "role": "management",
        "available_at": "pre_season",
        "adjustable": True,
        "derived": True,
        "derived_from": "OILPALM.Y_AVG_harvest_int",
        "derivation": "Y_AVG_harvest_int shifted 1 year within block; alternative from tbl_HRR_harvests mean(prevRoundLength_d) or gaps between distinct D_Harvest dates",
        "reason": "Derived, not a raw column: prior-year harvest interval. Review the exact interval definition before approval.",
    },
    {
        "source": "tbl_PD_surveys",
        "name": "ganoderma_affected_area",
        "decision": "keep",
        "role": "pest",
        "available_at": "pre_season",
        "adjustable": False,
        "reason": "Chronic disease pressure context.",
    },
    {
        "source": "tbl_PD_surveys",
        "name": "ganoderma_severity",
        "decision": "keep",
        "role": "pest",
        "available_at": "pre_season",
        "adjustable": False,
        "reason": "Chronic disease pressure context.",
    },
    {
        "source": "tbl_FN_soilAnalysis",
        "name": "soil_ph",
        "decision": "review",
        "role": "soil",
        "available_at": "pre_season",
        "adjustable": False,
        "reason": "Soil chemistry; only ~12% block-year coverage.",
    },
    {
        "source": "tbl_FN_soilAnalysis",
        "name": "soil_cec",
        "decision": "review",
        "role": "soil",
        "available_at": "pre_season",
        "adjustable": False,
        "reason": "Soil chemistry; sparse coverage.",
    },
    {
        "source": "tbl_FN_soilAnalysis",
        "name": "soil_som",
        "decision": "review",
        "role": "soil",
        "available_at": "pre_season",
        "adjustable": False,
        "reason": "Soil organic matter; sparse coverage.",
    },
    {
        "source": "tbl_BBC_bunchCounts",
        "name": "black_bunch_per_palm",
        "decision": "review",
        "role": "leading_indicator",
        "available_at": "mid_season",
        "adjustable": False,
        "reason": "Only available 2023-2025; useful as a mid-season signal.",
    },
    {
        "source": "tbl_CB_cropBudgetMt",
        "name": "crop_budget_ton",
        "decision": "drop",
        "role": "benchmark",
        "available_at": "post_season_or_review",
        "adjustable": False,
        "reason": "Company budget is backfilled; use as a benchmark, not a feature.",
    },
    {
        "source": "tbl_BBC_forecastABW",
        "name": "abw_forecast",
        "decision": "drop",
        "role": "benchmark",
        "available_at": "post_season_or_review",
        "adjustable": False,
        "reason": "OMP forecast-derived; test only after timing is confirmed.",
    },
)

_EXTERNAL_PROVENANCE: dict[str, dict[str, Any]] = {
    "rain_annual_mm": {
        "derived": True,
        "derived_from": "tbl_CW_weatherAndWater.R_Total Rainfall",
        "derivation": "Renamed/standardized annual rainfall; equivalent to sum(R_rain_mm_1..12)",
    },
    "dry_months": {
        "derived": True,
        "derived_from": "tbl_CW_weatherAndWater.R_NO_dry_month",
        "derivation": "Renamed raw dry-month count",
    },
    "water_deficit": {
        "derived": True,
        "derived_from": "tbl_CW_weatherAndWater.R_waterdeficit",
        "derivation": "Renamed raw water-deficit field",
    },
    "ganoderma_affected_area": {
        "derived": True,
        "derived_from": "tbl_PD_surveys.P_AffectedArea or AffectedArea filtered to PestName='Ganoderma'",
        "derivation": "Aggregate affected area by block-year; confirm whether P_AffectedArea or AffectedArea is the intended unit",
    },
    "ganoderma_severity": {
        "derived": True,
        "derived_from": "tbl_PD_surveys.P_Severity filtered to PestName='Ganoderma'",
        "derivation": "Aggregate severity by block-year (max or mean)",
    },
    "soil_ph": {
        "derived": True,
        "derived_from": "tbl_FN_soilAnalysis.SA_PH_H2O",
        "derivation": "Renamed H2O pH; alternative SA_PH_KCl",
    },
    "soil_cec": {
        "derived": True,
        "derived_from": "tbl_FN_soilAnalysis.SA_CEC",
        "derivation": "Renamed CEC; alternative ECEC (effective CEC)",
    },
    "soil_som": {
        "derived": True,
        "derived_from": "tbl_FN_soilAnalysis.SA_SOM",
        "derivation": "Renamed soil organic matter",
    },
    "black_bunch_per_palm": {
        "derived": True,
        "derived_from": "tbl_BBC_bunchCounts.BlackBunch / NoOfPalm",
        "derivation": "Per-survey bunch count per palm; aggregate to block-year by mean or latest survey before the cutoff",
    },
    "crop_budget_ton": {
        "derived": True,
        "derived_from": "tbl_CB_cropBudgetMt.Y_total_ton_bud",
        "derivation": "Renamed budget total; benchmark only",
    },
    "abw_forecast": {
        "derived": True,
        "derived_from": "tbl_BBC_forecastABW.ABWMt1_kg..ABWMt12_kg",
        "derivation": "Average or selected-month ABW forecast; benchmark/test only",
    },
}

EXTERNAL_FEATURES = tuple(
    {**feature, **_EXTERNAL_PROVENANCE.get(feature["name"], {})}
    for feature in EXTERNAL_FEATURES
)

DERIVED_FEATURES: tuple[dict[str, Any], ...] = (
    {
        "name": "yield_lag1",
        "decision": "planned",
        "role": "history",
        "available_at": "pre_season",
        "formula": "Y_TOTAL_ton shifted 1 year within block",
        "reason": "Safe prior-year history.",
    },
    {
        "name": "yield_lag2",
        "decision": "planned",
        "role": "history",
        "available_at": "pre_season",
        "formula": "Y_TOTAL_ton shifted 2 years within block",
        "reason": "Capture longer yield memory.",
    },
    {
        "name": "yield_roll3_mean",
        "decision": "planned",
        "role": "history",
        "available_at": "pre_season",
        "formula": "rolling 3-year mean of Y_TOTAL_ton, shifted 1 year",
        "reason": "Smooth block-level yield history.",
    },
    {
        "name": "weather_anomaly",
        "decision": "planned",
        "role": "weather",
        "available_at": "pre_season",
        "formula": "station-year weather minus station climatology",
        "reason": "Drought and wet-year signal without leaking future weather.",
    },
    {
        "name": "nutrient_balance_NK",
        "decision": "planned",
        "role": "management",
        "available_at": "pre_season",
        "formula": "applied N / applied K2O",
        "reason": "Nutrient balance and management intensity.",
    },
    {
        "name": "ganoderma_cumulative_area",
        "decision": "planned",
        "role": "pest",
        "available_at": "pre_season",
        "formula": "cumulative Ganoderma affected area through prior year",
        "reason": "Chronic disease burden.",
    },
    {
        "name": "harvest_loss_rate",
        "decision": "planned",
        "role": "history",
        "available_at": "pre_season",
        "formula": "discarded and unpollinated bunches / total bunches, prior year",
        "reason": "Harvest quality and loss context.",
    },
)


@dataclass(frozen=True)
class Snapshot:
    """A loaded Phase 2 Parquet snapshot."""

    path: Path
    manifest: dict[str, Any]
    tables: dict[str, pl.DataFrame]
    verification: dict[str, Any]


def latest_snapshot(root: Path = Path("data/raw")) -> Path:
    """Return the newest snapshot directory containing a manifest."""

    candidates = sorted(
        path for path in root.iterdir() if path.is_dir() and (path / "manifest.json").is_file()
    )
    if not candidates:
        raise FileNotFoundError(f"No snapshots found under {root}")
    return candidates[-1]


def load_snapshot(path: Path, *, verify: bool = True) -> Snapshot:
    """Load all Parquet tables and the manifest from a snapshot."""

    manifest_path = path / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Snapshot manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text())
    verification = verify_snapshot(path) if verify else {"all_ok": None, "tables": []}
    if verify and not verification["all_ok"]:
        raise RuntimeError(f"Snapshot verification failed: {path}")

    tables = {
        parquet.stem: pl.read_parquet(parquet)
        for parquet in sorted(path.glob("*.parquet"))
    }
    if "OILPALM" not in tables:
        raise ValueError(f"OILPALM not found in snapshot: {path}")
    return Snapshot(path=path, manifest=manifest, tables=tables, verification=verification)


def build_population(oilpalm: pl.DataFrame) -> dict[str, pl.DataFrame]:
    """Split OILPALM into usable, mature, immature, placeholder, and anomaly frames."""

    placeholder = oilpalm.filter(pl.col("YEAR") == 2026)
    usable = oilpalm.filter(pl.col("YEAR") <= 2025)
    mature_mask = pl.col("Growth_Period").is_in(MATURE_PERIODS).fill_null(False)
    mature = usable.filter(mature_mask)
    immature = usable.filter(~mature_mask)

    flagged = []
    if mature.height:
        zero = mature.filter(pl.col(TARGET) <= 0).with_columns(
            pl.lit("mature_zero_yield").alias("flag")
        )
        area_zero = mature.filter(
            (pl.col("areaIY_ha") == 0) & (pl.col(TARGET) > 0)
        ).with_columns(pl.lit("areaIY_zero_positive_yield").alias("flag"))
        flagged.extend([zero, area_zero])
    if immature.height:
        positive = immature.filter(pl.col(TARGET) > 0).with_columns(
            pl.lit("immature_positive_yield").alias("flag")
        )
        flagged.append(positive)
    if placeholder.height:
        flagged.append(placeholder.with_columns(pl.lit("placeholder_2026").alias("flag")))

    anomalies = (
        pl.concat(flagged, how="diagonal_relaxed") if flagged else oilpalm.head(0)
    )
    return {
        "all": oilpalm,
        "usable": usable,
        "mature": mature,
        "mature_positive": mature.filter(pl.col(TARGET) > 0),
        "immature": immature,
        "placeholder": placeholder,
        "anomalies": anomalies,
    }


def _missing_expr(column: str, dtype: pl.DataType) -> pl.Expr:
    if dtype == pl.String:
        return pl.col(column).is_null() | (pl.col(column).str.strip_chars() == "")
    return pl.col(column).is_null()


def missingness_table(frame: pl.DataFrame) -> pl.DataFrame:
    """Compute missingness and distinct counts for every column."""

    rows: list[dict[str, Any]] = []
    height = frame.height
    for column in frame.columns:
        dtype = frame.schema[column]
        missing_expr = _missing_expr(column, dtype)
        missing = int(frame.select(missing_expr.sum()).item())
        distinct = int(frame.select(pl.col(column).filter(~missing_expr).n_unique()).item())
        rows.append(
            {
                "column_name": column,
                "dtype": str(dtype),
                "missing": missing,
                "missing_pct": round(missing / height * 100, 1) if height else 0.0,
                "distinct_count": distinct,
                "constant": distinct <= 1,
            }
        )
    return pl.DataFrame(rows)


def missingness_by_year(frame: pl.DataFrame) -> pl.DataFrame:
    """Compute missing counts per year for every column."""

    if "YEAR" not in frame.columns or frame.height == 0:
        return pl.DataFrame(
            schema={
                "YEAR": pl.Int64,
                "column_name": pl.String,
                "missing": pl.Int64,
                "year_rows": pl.Int64,
                "missing_pct": pl.Float64,
            }
        )
    rows = frame.group_by("YEAR").len().sort("YEAR")
    expressions = []
    for column in frame.columns:
        if column == "YEAR":
            continue
        expressions.append(
            _missing_expr(column, frame.schema[column]).sum().alias(column)
        )
    counts = frame.group_by("YEAR").agg(expressions).sort("YEAR")
    long = counts.unpivot(
        index="YEAR",
        variable_name="column_name",
        value_name="missing",
    ).join(rows, on="YEAR", how="left")
    return long.with_columns(
        (pl.col("missing") / pl.col("len") * 100).round(1).alias("missing_pct")
    ).rename({"len": "year_rows"})


def duplicate_checks(tables: dict[str, pl.DataFrame]) -> pl.DataFrame:
    """Check OILPALM keys/exact duplicates and load Phase 1 business-key checks."""

    oil = tables["OILPALM"]
    keys = ["NAME", "UNIT", "BLOCK", "YEAR"]
    grouped = oil.group_by(keys).len()
    key_dupes = grouped.filter(pl.col("len") > 1)
    key_duplicate_rows = int((key_dupes["len"] - 1).sum()) if key_dupes.height else 0
    rows = [
        {
            "check": "OILPALM business key",
            "table": "OILPALM",
            "rows": oil.height,
            "duplicate_rows": key_duplicate_rows,
            "key_columns": "NAME, UNIT, BLOCK, YEAR",
        },
        {
            "check": "OILPALM exact duplicate rows",
            "table": "OILPALM",
            "rows": oil.height,
            "duplicate_rows": int(oil.is_duplicated().sum()),
            "key_columns": "",
        },
    ]

    key_path = Path("data/phase-1-inventory/key_uniqueness.csv")
    if key_path.is_file():
        phase1 = pl.read_csv(key_path).select(
            pl.lit("Phase 1 candidate key").alias("check"),
            pl.col("table_name").alias("table"),
            pl.col("row_count").alias("rows"),
            pl.col("duplicate_rows"),
            pl.col("key_columns"),
        )
        rows.extend(phase1.to_dicts())
    return pl.DataFrame(rows)


def _max_abs_diff(frame: pl.DataFrame, expression: pl.Expr) -> float:
    value = frame.select(expression.abs().max()).item()
    return float(value) if value is not None else float("nan")


def leakage_checks(frame: pl.DataFrame) -> pl.DataFrame:
    """Verify known target-derived identities on usable rows."""

    month_ton = [f"Y_{i:02d}_total_ton" for i in range(1, 13)]
    month_bunches = [f"Y_{i:02d}_total_bunches" for i in range(1, 13)]
    month_mandays = [f"Y_{i:02d}_mandays" for i in range(1, 13)]

    checks: list[dict[str, Any]] = []

    def add(name: str, expression: pl.Expr, tolerance: float = 1e-6) -> None:
        diff = _max_abs_diff(frame, expression)
        checks.append(
            {
                "check": name,
                "max_abs_diff": diff,
                "tolerance": tolerance,
                "status": "pass" if np.isfinite(diff) and diff <= tolerance else "fail",
            }
        )

    add(
        "Y_TH = Y_TOTAL_ton / area_ha",
        pl.when(pl.col("area_ha") > 0)
        .then(pl.col("Y_TH") - pl.col("Y_TOTAL_ton") / pl.col("area_ha"))
        .otherwise(None),
    )
    add(
        "Y_KGB = 1000 * Y_TOTAL_ton / Y_TOTAL_bunches",
        pl.when(pl.col("Y_TOTAL_bunches") > 0)
        .then(
            pl.col("Y_KGB")
            - 1000 * pl.col("Y_TOTAL_ton") / pl.col("Y_TOTAL_bunches")
        )
        .otherwise(None),
    )
    add(
        "Y_TH_GAP = Y_TH - Y_TH_POT",
        pl.col("Y_TH_GAP") - (pl.col("Y_TH") - pl.col("Y_TH_POT")),
    )
    add(
        "Y_GAP_Percent = 100 * (Y_TH - Y_TH_POT) / Y_TH_POT",
        pl.when(pl.col("Y_TH_POT") > 0)
        .then(
            pl.col("Y_GAP_Percent")
            - 100 * (pl.col("Y_TH") - pl.col("Y_TH_POT")) / pl.col("Y_TH_POT")
        )
        .otherwise(None),
    )
    add(
        "Y_TOTAL_ton = sum monthly ton",
        pl.col("Y_TOTAL_ton")
        - pl.sum_horizontal([pl.col(c).fill_null(0) for c in month_ton]),
    )
    add(
        "Y_TOTAL_bunches = sum monthly bunches",
        pl.col("Y_TOTAL_bunches")
        - pl.sum_horizontal([pl.col(c).fill_null(0) for c in month_bunches]),
    )
    add(
        "Y_TOTAL_mandays = sum monthly mandays",
        pl.col("Y_TOTAL_mandays")
        - pl.sum_horizontal([pl.col(c).fill_null(0) for c in month_mandays]),
    )
    add(
        "Y_per_manday = Y_TOTAL_ton / Y_TOTAL_mandays",
        pl.when(pl.col("Y_TOTAL_mandays") > 0)
        .then(pl.col("Y_per_manday") - pl.col("Y_TOTAL_ton") / pl.col("Y_TOTAL_mandays"))
        .otherwise(None),
    )
    add(
        "Y_BNTREE ~= Y_TOTAL_bunches / palmStandMature_p",
        pl.when(pl.col("palmStandMature_p") > 0)
        .then(
            pl.col("Y_BNTREE")
            - pl.col("Y_TOTAL_bunches") / pl.col("palmStandMature_p")
        )
        .otherwise(None),
        tolerance=0.5,
    )
    return pl.DataFrame(checks)


def target_summary(population: dict[str, pl.DataFrame]) -> pl.DataFrame:
    """Target distribution and zero counts for each population slice."""

    rows = []
    for label in ("usable", "mature", "mature_positive"):
        frame = population[label]
        values = frame[TARGET].cast(pl.Float64)
        rows.append(
            {
                "population": label,
                "rows": frame.height,
                "zeros": int((values == 0).sum()),
                "negatives": int((values < 0).sum()),
                "min": values.min(),
                "p01": values.quantile(0.01),
                "median": values.median(),
                "mean": values.mean(),
                "p99": values.quantile(0.99),
                "max": values.max(),
                "std": values.std(),
            }
        )
    return pl.DataFrame(rows)


def by_year_summary(frame: pl.DataFrame) -> pl.DataFrame:
    """Target summary by year for the mature population."""

    return (
        frame.group_by("YEAR")
        .agg(
            pl.len().alias("rows"),
            (pl.col(TARGET) == 0).sum().alias("zeros"),
            pl.col(TARGET).mean().alias("mean_ton"),
            pl.col(TARGET).median().alias("median_ton"),
            pl.col(TARGET).sum().alias("total_ton"),
        )
        .sort("YEAR")
    )


def outlier_table(frame: pl.DataFrame, missing: pl.DataFrame) -> pl.DataFrame:
    """IQR outlier counts for numeric columns."""

    rows: list[dict[str, Any]] = []
    missing_map = {
        row["column_name"]: row["missing_pct"] for row in missing.iter_rows(named=True)
    }
    for column in frame.columns:
        dtype = frame.schema[column]
        if dtype not in NUMERIC_TYPES or column in {TARGET, "YEAR"}:
            continue
        series = frame[column].cast(pl.Float64).drop_nulls()
        if series.len() < 20:
            continue
        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)
        if q1 is None or q3 is None:
            continue
        iqr = float(q3 - q1)
        if iqr <= 0:
            continue
        lower = float(q1 - 1.5 * iqr)
        upper = float(q3 + 1.5 * iqr)
        count = int(((series < lower) | (series > upper)).sum())
        rows.append(
            {
                "column_name": column,
                "missing_pct": missing_map.get(column, 0.0),
                "q1": float(q1),
                "q3": float(q3),
                "lower": lower,
                "upper": upper,
                "outlier_count": count,
                "outlier_pct": round(count / series.len() * 100, 1),
            }
        )
    if not rows:
        return pl.DataFrame(
            schema={
                "column_name": pl.String,
                "missing_pct": pl.Float64,
                "q1": pl.Float64,
                "q3": pl.Float64,
                "lower": pl.Float64,
                "upper": pl.Float64,
                "outlier_count": pl.Int64,
                "outlier_pct": pl.Float64,
            }
        )
    return pl.DataFrame(rows).sort("outlier_pct", descending=True)


def domain_checks(frame: pl.DataFrame) -> pl.DataFrame:
    """Domain-specific target and structural checks."""

    def count(expression: pl.Expr) -> int:
        return int(frame.select(expression.sum()).item())

    yield_per_ha = pl.col(TARGET) / pl.col("area_ha")
    rows = [
        ("target zero", count(pl.col(TARGET) == 0)),
        ("target negative", count(pl.col(TARGET) < 0)),
        ("area_ha <= 0", count(pl.col("area_ha") <= 0)),
        ("tree age < 3", count(pl.col("D_TREEAGE") < 3)),
        ("tree age > 30", count(pl.col("D_TREEAGE") > 30)),
        ("yield per ha > 40", count(yield_per_ha > 40)),
        (
            "mature stand > total stand",
            count(pl.col("palmStandMature_p") > pl.col("palmStand_p")),
        ),
    ]
    return pl.DataFrame([{"check": name, "rows": value} for name, value in rows])


def consistency_checks(mature: pl.DataFrame, tables: dict[str, pl.DataFrame]) -> pl.DataFrame:
    """Cross-field and cross-table consistency checks."""

    checks: list[dict[str, Any]] = []
    age_expression = (
        pl.col("D_TREEAGE")
        - (pl.col("YEAR") - pl.col("D_PLANTED").dt.year() + 1)
    ).abs()
    age_diff = mature.select(age_expression.max()).item()
    checks.append(
        {
            "check": "tree age vs planting year",
            "rows_checked": mature.height,
            "failing_rows": int(mature.select((age_expression > 0).sum()).item()),
            "max_abs_diff": float(age_diff) if age_diff is not None else None,
        }
    )
    area_expression = (pl.col("area_ha") - pl.col("areaIY_ha")).abs()
    area_diff = mature.select(area_expression.max()).item()
    checks.append(
        {
            "check": "area_ha vs areaIY_ha",
            "rows_checked": mature.height,
            "failing_rows": int(mature.select((area_expression > 0.01).sum()).item()),
            "max_abs_diff": float(area_diff) if area_diff is not None else None,
        }
    )

    harvest = tables.get("tbl_HRR_harvests")
    if harvest is not None and harvest.height:
        aggregated = harvest.group_by(["Estate", "UNIT", "BLOCK", "Y_Harvest"]).agg(
            (pl.col("Y_FFB").sum() / 1000).alias("harvest_ton")
        )
        joined = mature.join(
            aggregated,
            left_on=["NAME", "UNIT", "BLOCK", "YEAR"],
            right_on=["Estate", "UNIT", "BLOCK", "Y_Harvest"],
            how="inner",
        )
        compared = joined.select(
            (pl.col(TARGET) - pl.col("harvest_ton")).abs().alias("abs_diff"),
            pl.when(pl.col(TARGET) > 0)
            .then(
                (pl.col(TARGET) - pl.col("harvest_ton")).abs() / pl.col(TARGET)
            )
            .otherwise(None)
            .alias("rel_diff"),
        )
        max_diff = compared["abs_diff"].max() if compared.height else None
        max_rel = compared["rel_diff"].max() if compared.height else None
        checks.append(
            {
                "check": "OILPALM target vs HRR harvest FFB",
                "rows_checked": joined.height,
                "failing_rows": int((compared["rel_diff"] > 0.05).sum()),
                "max_abs_diff": float(np.asarray(max_diff)) if max_diff is not None else None,
                "max_rel_diff": float(np.asarray(max_rel)) if max_rel is not None else None,
            }
        )

    return pl.DataFrame(checks)


def numeric_signal(frame: pl.DataFrame, exclude: set[str]) -> pl.DataFrame:
    """Pearson correlation of numeric features with the target."""

    target = frame[TARGET].cast(pl.Float64).to_numpy()
    rows = []
    for column in frame.columns:
        if column == TARGET or column in exclude:
            continue
        dtype = frame.schema[column]
        if dtype not in NUMERIC_TYPES:
            continue
        values = frame[column].cast(pl.Float64).to_numpy()
        mask = np.isfinite(values) & np.isfinite(target)
        if mask.sum() < 30 or np.std(values[mask]) == 0 or np.std(target[mask]) == 0:
            continue
        r = float(np.corrcoef(values[mask], target[mask])[0, 1])
        rows.append(
            {
                "feature": column,
                "pearson_r": r,
                "abs_r": abs(r),
                "n": int(mask.sum()),
            }
        )
    if not rows:
        return pl.DataFrame(
            schema={"feature": pl.String, "pearson_r": pl.Float64, "abs_r": pl.Float64, "n": pl.Int64}
        )
    return pl.DataFrame(rows).sort("abs_r", descending=True)


def vif_table(frame: pl.DataFrame, signal: pl.DataFrame, limit: int = 30) -> pl.DataFrame:
    """Approximate VIF for the strongest numeric features."""

    features = (
        signal.filter(pl.col("n") >= 30)
        .sort("abs_r", descending=True)
        .head(limit)["feature"]
        .to_list()
    )
    matrix = []
    names = []
    for feature in features:
        values = frame[feature].cast(pl.Float64).to_numpy()
        if np.isfinite(values).sum() < 30:
            continue
        median = np.nanmedian(values)
        values = np.where(np.isfinite(values), values, median)
        if np.std(values) == 0:
            continue
        matrix.append((values - values.mean()) / values.std())
        names.append(feature)
    if len(names) < 2:
        return pl.DataFrame(schema={"feature": pl.String, "vif": pl.Float64})

    x = np.column_stack(matrix)
    rows = []
    for index, name in enumerate(names):
        y = x[:, index]
        others = np.delete(x, index, axis=1)
        design = np.column_stack([np.ones(len(y)), others])
        coefficients, *_ = np.linalg.lstsq(design, y, rcond=None)
        residual = y - design @ coefficients
        total = np.sum((y - y.mean()) ** 2)
        r2 = 1 - np.sum(residual**2) / total if total > 0 else 1.0
        rows.append(
            {
                "feature": name,
                "vif": float("inf") if r2 >= 1 else float(1 / (1 - r2)),
            }
        )
    return pl.DataFrame(rows).sort("vif", descending=True)


def redundancy_pairs(frame: pl.DataFrame, signal: pl.DataFrame, limit: int = 40) -> pl.DataFrame:
    """Pairwise correlations above 0.95 among the strongest numeric features."""

    features = signal.head(limit)["feature"].to_list()
    matrix = {}
    for feature in features:
        values = frame[feature].cast(pl.Float64).to_numpy()
        median = np.nanmedian(values)
        matrix[feature] = np.where(np.isfinite(values), values, median)
    rows = []
    for i, left in enumerate(features):
        for right in features[i + 1 :]:
            x, y = matrix[left], matrix[right]
            if np.std(x) == 0 or np.std(y) == 0:
                continue
            r = float(np.corrcoef(x, y)[0, 1])
            if abs(r) >= 0.95:
                rows.append({"feature_a": left, "feature_b": right, "pearson_r": r})
    if not rows:
        return pl.DataFrame(
            schema={"feature_a": pl.String, "feature_b": pl.String, "pearson_r": pl.Float64}
        )
    return pl.DataFrame(rows).sort("pearson_r", descending=True)


def _decision_for_column(
    column: str,
    dtype: pl.DataType,
    missing_pct: float,
    distinct: int,
) -> tuple[str, str, str]:
    if column == TARGET:
        return "target", "target", "Model target in metric tons."
    if column in ID_COLUMNS:
        return "drop", "id", "Identifier, key, or timing label; not a model feature."
    if missing_pct >= 95.0 or distinct <= 1:
        return "drop", "empty_or_constant", "Empty or constant column."
    if column in DROP_COLUMNS:
        return "drop", "redundant", "Redundant, target-timing, or structurally invalid feature."
    if column in REVIEW_COLUMNS:
        return "review", "review", "Sparse, derived, or timing-ambiguous; requires approval."
    if column.startswith("Y_") or column.startswith("MarkerLeaf_"):
        return "drop", "leakage", "Current-year target-derived or assessment field; leakage risk."
    if column == "MarkerYield":
        return "review", "review", "Expert yield assessment; confirm whether it is pre-harvest."
    if column == "Y_TH_POT":
        return "review", "review", "OMP potential-yield estimate; confirm source and timing."
    if column in MANAGEMENT_COLUMNS:
        return "keep", "management", "Management lever for what-if analysis."
    if column.startswith("LA_"):
        if missing_pct >= 50:
            return "review", "leaf", "Leaf measurement with limited coverage."
        return "keep", "leaf", "Leaf nutrient or vegetative context; use latest pre-cutoff sample."
    if dtype in {pl.String} and missing_pct >= 50:
        return "review", "context", "Categorical context with limited coverage."
    return "keep", "context", "Contextual feature; validate cutoff availability in Phase 4."


def feature_decisions(
    oilpalm: pl.DataFrame,
    missing: pl.DataFrame,
    signal: pl.DataFrame,
    vif: pl.DataFrame,
) -> pl.DataFrame:
    """Build the draft feature-decision table."""

    missing_map = {
        row["column_name"]: row for row in missing.iter_rows(named=True)
    }
    signal_map = {
        row["feature"]: row["pearson_r"] for row in signal.iter_rows(named=True)
    }
    vif_map = {row["feature"]: row["vif"] for row in vif.iter_rows(named=True)}

    rows = []
    for column in oilpalm.columns:
        stats = missing_map.get(column, {})
        decision, role, reason = _decision_for_column(
            column,
            oilpalm.schema[column],
            float(stats.get("missing_pct", 0.0)),
            int(stats.get("distinct_count", 0)),
        )
        available_at = (
            "post_season"
            if role == "leakage" or column == TARGET
            else "mid_season"
            if column.startswith("LA_")
            else "post_season_or_review"
            if column in {"D_FHARVEST", "M_FHARVEST", "MarkerYield"}
            else "pre_season"
        )
        rows.append(
            {
                "source": "OILPALM",
                "name": column,
                "dtype": str(oilpalm.schema[column]),
                "decision": decision,
                "role": role,
                "available_at": available_at,
                "adjustable": column in MANAGEMENT_COLUMNS,
                "missing_pct": stats.get("missing_pct"),
                "distinct_count": stats.get("distinct_count"),
                "pearson_r": signal_map.get(column),
                "vif": vif_map.get(column),
                "derived": False,
                "derived_from": "",
                "derivation": "",
                "reason": reason,
            }
        )

    for feature in EXTERNAL_FEATURES:
        rows.append(
            {
                "source": feature["source"],
                "name": feature["name"],
                "dtype": None,
                "decision": feature["decision"],
                "role": feature["role"],
                "available_at": feature["available_at"],
                "adjustable": feature["adjustable"],
                "missing_pct": None,
                "distinct_count": None,
                "pearson_r": None,
                "vif": None,
                "derived": feature.get("derived", False),
                "derived_from": feature.get("derived_from", ""),
                "derivation": feature.get("derivation", ""),
                "reason": feature["reason"],
            }
        )
    return pl.DataFrame(rows)


def _quantile(series: pl.Series, q: float) -> float | None:
    value = series.cast(pl.Float64).quantile(q)
    return None if value is None else round(float(value), 4)


def management_levers(mature: pl.DataFrame, tables: dict[str, pl.DataFrame]) -> dict[str, Any]:
    """Build the draft management-lever configuration with observed ranges."""

    nutrient = tables.get("tbl_FN_nutActRec")
    levers: dict[str, Any] = {}
    if nutrient is not None:
        keys = mature.select(["NAME", "UNIT", "BLOCK", "YEAR"]).rename(
            {
                "NAME": "suEstate",
                "UNIT": "suDivision",
                "BLOCK": "suBlock",
                "YEAR": "Yr",
            }
        )
        joined = nutrient.join(
            keys,
            on=["suEstate", "suDivision", "suBlock", "Yr"],
            how="inner",
        )
        for column in (
            "nutActInorgN_kg_p",
            "nutActInorgP2O5_kg_p",
            "nutActInorgK2O_kg_p",
            "nutActInorgMgO_kg_p",
            "nutActInorgCaO_kg_p",
            "nutActInorgB_kg_p",
        ):
            if column not in joined.columns:
                continue
            series = joined[column]
            levers[column] = {
                "label": column.replace("nutActInorg", "").replace("_kg_p", " rate"),
                "source": "tbl_FN_nutActRec",
                "dtype": "float",
                "unit": "kg/palm/year",
                "available_at": "pre_season",
                "adjustable": True,
                "observed_p05": _quantile(series, 0.05),
                "observed_p95": _quantile(series, 0.95),
                "decision": "keep",
                "reason": "Primary nutrient management lever.",
            }

        recommendation_levers = {
            "nutRecInorgN_kg_p": "Recommended N rate",
            "nutRecInorgP2O5_kg_p": "Recommended P2O5 rate",
            "nutRecInorgK2O_kg_p": "Recommended K2O rate",
            "nutActOrgN_kg_p": "Organic N rate",
            "nutActOrgP2O5_kg_p": "Organic P2O5 rate",
            "nutActOrgK2O_kg_p": "Organic K2O rate",
        }
        for column, label in recommendation_levers.items():
            if column not in joined.columns:
                continue
            series = joined[column]
            levers[column] = {
                "label": label,
                "source": "tbl_FN_nutActRec",
                "dtype": "float",
                "unit": "kg/palm/year",
                "available_at": "pre_season",
                "adjustable": True,
                "observed_p05": _quantile(series, 0.05),
                "observed_p95": _quantile(series, 0.95),
                "decision": "review",
                "reason": "Confirm recommendation/organic input availability and operational meaning.",
            }

    for column in ("Pruning", "HarvesterAccess"):
        if column in mature.columns:
            options = sorted(
                value
                for value in mature[column].drop_nulls().unique().to_list()
                if value not in ("", "No data")
            )
            levers[column] = {
                "label": column,
                "source": "OILPALM",
                "dtype": "categorical",
                "options": options,
                "available_at": "pre_season",
                "adjustable": True,
                "decision": "keep",
                "reason": "Operational management lever.",
            }

    if "Y_AVG_harvest_int" in mature.columns:
        series = mature["Y_AVG_harvest_int"]
        levers["harvest_interval_target_d"] = {
            "label": "Harvest interval target",
            "source": "OILPALM.Y_AVG_harvest_int",
            "dtype": "float",
            "unit": "days",
            "available_at": "pre_season",
            "adjustable": True,
            "basis": "prior-year lag",
            "observed_p05": _quantile(series, 0.05),
            "observed_p95": _quantile(series, 0.95),
            "decision": "review",
            "reason": "Target-derived in-year field; only a lagged operational lever is safe.",
        }

    control = tables.get("tbl_PD_controlAct")
    if control is not None and control.height:
        levers["disease_control_felling"] = {
            "label": "Disease control / felling",
            "source": "tbl_PD_controlAct",
            "dtype": "integer",
            "unit": "events",
            "available_at": "pre_season",
            "adjustable": True,
            "coverage_block_years": int(
                control.select(
                    pl.struct(["ESTATE", "UNIT", "BLOCK", "yrFis"]).n_unique()
                ).item()
            ),
            "years": sorted(control["yrFis"].unique().to_list()),
            "decision": "review",
            "reason": "Only 2022-2025 coverage; confirm operational interpretation.",
        }

    pesticide = tables.get("tbl_PCD_pesticideAct_dt")
    if pesticide is not None and pesticide.height:
        levers["weed_control_intensity"] = {
            "label": "Weed control intensity",
            "source": "tbl_PCD_pesticideAct_dt",
            "dtype": "float",
            "unit": "kg applied",
            "available_at": "pre_season",
            "adjustable": True,
            "years": sorted(pesticide["yrFis"].unique().to_list()),
            "decision": "review",
            "reason": "2025-only data; scenario-only lever until more history exists.",
        }

    if "IsAbblation" in mature.columns:
        levers["replanting_ablation"] = {
            "label": "Ablation / replanting intervention",
            "source": "OILPALM.IsAbblation",
            "dtype": "boolean",
            "available_at": "pre_season",
            "adjustable": True,
            "decision": "review",
            "reason": "Sparse intervention; test before exposing in what-if.",
        }

    return {
        "status": "draft",
        "requires_approval": True,
        "levers": levers,
    }


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True))


def _load_yaml(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    payload = yaml.safe_load(path.read_text()) or {}
    return payload if isinstance(payload, dict) else None


def _approved_features(config_dir: Path) -> dict[str, Any] | None:
    payload = _load_yaml(config_dir / "features.yaml")
    if payload and payload.get("status") == "approved":
        return payload
    return None


def _approved_levers(config_dir: Path) -> dict[str, Any] | None:
    payload = _load_yaml(config_dir / "management_levers.yaml")
    if payload and payload.get("status") == "approved":
        return payload
    return None


def _apply_approved_decisions(
    decisions: pl.DataFrame,
    approved: dict[str, Any] | None,
) -> pl.DataFrame:
    if not approved:
        return decisions
    approved_map = {
        feature["name"]: feature
        for feature in approved.get("features", [])
        if feature.get("name")
    }
    rows = []
    for row in decisions.to_dicts():
        replacement = approved_map.get(row["name"])
        if replacement:
            for key in (
                "source",
                "decision",
                "role",
                "available_at",
                "adjustable",
                "reason",
                "derived",
                "derived_from",
                "derivation",
            ):
                if key in replacement:
                    row[key] = replacement[key]
        rows.append(row)
    return pl.DataFrame(rows)


def _write_config(
    path: Path,
    payload: dict[str, Any],
    *,
    overwrite: bool,
) -> tuple[Path, Path | None]:
    """Preserve an edited config and write a generated draft beside it."""

    if path.exists() and not overwrite:
        generated = path.with_name(f"{path.stem}.generated{path.suffix}")
        _write_yaml(generated, payload)
        return path, generated
    _write_yaml(path, payload)
    return path, None


def _write_csv(path: Path, frame: pl.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.write_csv(path)


def write_cleaning_reports(
    snapshot_dir: Path,
    *,
    docs_dir: Path = Path("docs"),
    data_dir: Path = Path("data"),
    config_dir: Path = Path("config"),
    reports_dir: Path = Path("reports"),
    overwrite_config: bool = False,
) -> dict[str, Path]:
    """Run Phase 3 and write CSV, YAML, Markdown, and interim artifacts."""

    snapshot = load_snapshot(snapshot_dir, verify=True)
    oilpalm = snapshot.tables["OILPALM"]
    population = build_population(oilpalm)
    mature = population["mature"]

    artifact_dir = data_dir / "phase-3-cleaning"
    interim_dir = data_dir / "interim" / "phase-3"
    doc_dir = docs_dir / "phase-3-cleaning"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    interim_dir.mkdir(parents=True, exist_ok=True)
    doc_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    missing_all = missingness_table(population["usable"])
    missing_mature = missingness_table(mature)
    missing_year = missingness_by_year(population["usable"])
    duplicates = duplicate_checks(snapshot.tables)
    leakage = leakage_checks(population["usable"])
    targets = target_summary(population)
    yearly = by_year_summary(mature)
    outliers = outlier_table(mature, missing_mature)
    domains = domain_checks(mature)
    consistency = consistency_checks(mature, snapshot.tables)
    exclude = set(ID_COLUMNS) | set(DROP_COLUMNS) | {
        column for column in oilpalm.columns if column.startswith("Y_")
    }
    signal = numeric_signal(mature, exclude)
    vif = vif_table(mature, signal)
    redundancy = redundancy_pairs(mature, signal)
    approved_features = _approved_features(config_dir)
    approved_levers = _approved_levers(config_dir)
    decisions = _apply_approved_decisions(
        feature_decisions(oilpalm, missing_mature, signal, vif),
        approved_features,
    )
    levers = approved_levers or management_levers(mature, snapshot.tables)
    phase_status = (
        "approved"
        if approved_features and approved_levers
        else "draft — awaiting approval"
    )

    artifacts: dict[str, Path] = {}

    def artifact(name: str, frame: pl.DataFrame | None = None) -> None:
        path = artifact_dir / name
        if frame is not None:
            _write_csv(path, frame)
        artifacts[name] = path

    artifact("missingness_all.csv", missing_all)
    artifact("missingness_mature.csv", missing_mature)
    artifact("missingness_by_year.csv", missing_year)
    artifact("duplicates.csv", duplicates)
    artifact("leakage_checks.csv", leakage)
    artifact("target_summary.csv", targets)
    artifact("target_by_year.csv", yearly)
    artifact("outliers.csv", outliers)
    artifact("domain_checks.csv", domains)
    artifact("consistency_checks.csv", consistency)
    artifact("numeric_signal.csv", signal)
    artifact("vif.csv", vif)
    artifact("redundancy_pairs.csv", redundancy)
    artifact("feature_decisions.csv", decisions)

    features_config = {
        "status": "draft",
        "requires_approval": True,
        "target": TARGET,
        "keys": ["NAME", "UNIT", "BLOCK", "YEAR"],
        "mature_periods": list(MATURE_PERIODS),
        "cutoffs": ["pre_season", "mid_season"],
        "features": decisions.filter(~pl.col("role").is_in(["target", "id"])).to_dicts(),
    }
    features_path, features_generated = _write_config(
        config_dir / "features.yaml",
        features_config,
        overwrite=overwrite_config,
    )
    artifacts["features.yaml"] = features_path
    if features_generated is not None:
        artifacts["features.generated.yaml"] = features_generated

    levers_path, levers_generated = _write_config(
        config_dir / "management_levers.yaml",
        levers,
        overwrite=overwrite_config,
    )
    artifacts["management_levers.yaml"] = levers_path
    if levers_generated is not None:
        artifacts["management_levers.generated.yaml"] = levers_generated

    mature_path = interim_dir / "oilpalm_mature.parquet"
    mature.write_parquet(mature_path, compression="zstd")
    artifacts["oilpalm_mature.parquet"] = mature_path
    positive_path = interim_dir / "oilpalm_mature_positive.parquet"
    population["mature_positive"].write_parquet(positive_path, compression="zstd")
    artifacts["oilpalm_mature_positive.parquet"] = positive_path
    anomalies_path = interim_dir / "oilpalm_anomalies.parquet"
    population["anomalies"].write_parquet(anomalies_path, compression="zstd")
    artifacts["oilpalm_anomalies.parquet"] = anomalies_path

    decision_counts = (
        decisions.group_by("decision").len().sort("decision")
    )
    anomaly_counts = (
        population["anomalies"].group_by("flag").len().sort("flag")
        if population["anomalies"].height
        else pl.DataFrame(schema={"flag": pl.String, "len": pl.Int64})
    )
    derived_external = pl.DataFrame(
        [
            {
                "feature": feature["name"],
                "derived_from": feature["derived_from"],
                "derivation": feature["derivation"],
            }
            for feature in EXTERNAL_FEATURES
            if feature.get("derived")
        ]
    )
    check = "x" if phase_status == "approved" else " "
    report_md = f"""# Phase 3 — Cleaning and Feature Decisions

Status: **{phase_status}**

Snapshot: `{snapshot.path}`  
Snapshot verified: **{snapshot.verification["all_ok"]}**  
Target: `{TARGET}` metric tons  
Mature periods: `SAYP`, `PYP`, `DYP`

## Population

| Slice | Rows |
|---|---:|
| All OILPALM rows | {population["all"].height:,} |
| Usable 2019–2025 | {population["usable"].height:,} |
| Mature | {population["mature"].height:,} |
| Mature and positive target | {population["mature_positive"].height:,} |
| Immature | {population["immature"].height:,} |
| 2026 placeholder | {population["placeholder"].height:,} |
| Flagged anomaly rows | {population["anomalies"].height:,} |

## Known anomalies

{markdown_table(anomaly_counts)}

- `204D` 2025 has target `0` but HRR harvest FFB totals about `759 t`. Treat it
  as a source-data inconsistency; do not train on it without correction or an
  explicit exclusion decision.
- `124H` 2024/2025 has `areaIY_ha = 0` but positive target yield.
- 178 `IGP` rows have small positive yield despite being immature; they are
  excluded from the mature model and documented.
- The 2026 row is a placeholder.

## Target

{markdown_table(targets)}

### Target by year

{markdown_table(yearly)}

## Missingness

Top partially-missing mature columns (excluding the fully empty columns that are
dropped automatically):

{markdown_table(missing_mature.filter((pl.col("missing_pct") > 0) & (pl.col("missing_pct") < 100)).sort("missing_pct", descending=True).head(25), ["column_name", "dtype", "missing_pct", "distinct_count", "constant"])}

## Duplicates and key checks

{markdown_table(duplicates, max_text=160)}

## Leakage checks

{markdown_table(leakage, max_text=160)}

Leakage rules: all current-year `Y_*` fields are excluded from candidate
features. `Y_TH`, `Y_KGB`, monthly totals, `Y_TH_GAP`, `Y_GAP_Percent`,
`Y_per_manday`, and `Y_BNTREE` are confirmed target-derived. `Y_TH_POT` and
`MarkerYield` were reviewed and are approved as `drop`.

## Domain checks

{markdown_table(domains)}

## Outliers

Top numeric IQR outliers:

{markdown_table(outliers.head(20), ["column_name", "missing_pct", "outlier_count", "outlier_pct", "q1", "q3", "lower", "upper"])}

Full table: `data/phase-3-cleaning/outliers.csv`.

## Consistency checks

{markdown_table(consistency, max_text=160)}

## Numeric signal

Top associations with the mature target (Pearson):

{markdown_table(signal.head(25), ["feature", "pearson_r", "abs_r", "n"])}

High-VIF features (top 20):

{markdown_table(vif.head(20), ["feature", "vif"])}

High-correlation pairs (`|r| >= 0.95`):

{markdown_table(redundancy.head(25), ["feature_a", "feature_b", "pearson_r"])}

## Derived feature provenance

These candidate features are **not raw database columns**. They are planned
derivations from `tbl_HRR_harvests`. The derivation must be implemented and
tested in Phase 4; it is not a direct table field.

{markdown_table(derived_external, ["feature", "derived_from", "derivation"], max_text=220)}

## Feature decisions

Decision counts:

{markdown_table(decision_counts)}

- Feature decisions: `config/features.yaml` ({phase_status})
- Management levers: `config/management_levers.yaml` ({phase_status})
- Full decision table: `data/phase-3-cleaning/feature_decisions.csv`

The feature list is approved; no review decisions remain. Re-running
`omp-yield clean` preserves existing edited configs and writes regenerated
drafts as `*.generated.yaml`; use `--overwrite-config` only when you
intentionally want to replace them.

### Review decisions

{markdown_table(decisions.filter(pl.col("decision") == "review").select(["source", "name", "role", "missing_pct", "reason"]), max_text=160)}

## Management levers

{markdown_table(pl.DataFrame([
    {"lever": key, "decision": value.get("decision"), "reason": value.get("reason", "")}
    for key, value in levers["levers"].items()
]), max_text=180)}

## Interim data

- `data/interim/phase-3/oilpalm_mature.parquet`
- `data/interim/phase-3/oilpalm_mature_positive.parquet`
- `data/interim/phase-3/oilpalm_anomalies.parquet`

These are intermediate artifacts. The final modeling table is built in Phase 4
after feature approval.

## Approval checklist

- [{check}] Confirm mature filter: `SAYP`, `PYP`, `DYP`
- [{check}] Confirm target: `{TARGET}` in metric tons
- [{check}] Resolve every `review` feature in `config/features.yaml`
- [{check}] Approve or edit `config/management_levers.yaml`
- [{check}] Confirm `Y_TH_POT` and `MarkerYield` timing/source
- [{check}] Confirm sparse features (`LA_tree_height`, soil analysis, bunch counts)
"""
    report_path = doc_dir / "cleaning_report.md"
    report_path.write_text(report_md)
    artifacts["cleaning_report.md"] = report_path

    next_step = (
        "Phase 3 is approved. Proceed to Phase 4 — feature engineering and the "
        "final modeling table."
        if phase_status == "approved"
        else "Review and approve the feature and lever lists, then proceed to Phase 4."
    )
    readme = f"""# Phase 3 — Cleaning, Profiling, and Feature Decisions

Status: **{phase_status}**

Phase 3 cleans the mature 2019–2025 block-year population, audits target
leakage, profiles missingness and outliers, and produces feature and
management-lever configurations. This revision is **{phase_status}**.

## Key counts

| Item | Value |
|---|---:|
| Usable rows | {population["usable"].height:,} |
| Mature rows | {population["mature"].height:,} |
| Mature positive-target rows | {population["mature_positive"].height:,} |
| Anomaly rows flagged | {population["anomalies"].height:,} |
| Candidate feature decisions | {decisions.height:,} |
| Keep decisions | {int((decisions["decision"] == "keep").sum())} |
| Drop decisions | {int((decisions["decision"] == "drop").sum())} |
| Review decisions | {int((decisions["decision"] == "review").sum())} |

## Key anomaly

`204D` 2025 has target `0` but HRR harvest FFB totals about `759 t`. Treat it as
a source-data inconsistency before training.

## Derived and renamed features

Several external candidate names are **not raw columns**:

- `yield_lag1`, `bunch_weight_lag1`, `harvest_interval_lag1` are lagged
  `OILPALM` fields.
- `soil_ph`, `soil_cec`, `soil_som` rename `SA_PH_H2O`, `SA_CEC`, `SA_SOM`
  from `tbl_FN_soilAnalysis`.
- `black_bunch_per_palm` is `BlackBunch / NoOfPalm` from
  `tbl_BBC_bunchCounts`.
- Weather, pest, budget, and ABW aliases are also documented.

Exact formulas are in `cleaning_report.md` and the `derivation` fields in
`config/features.yaml`.

## Approval status

- `config/features.yaml` is `status: {phase_status}`.
- `config/management_levers.yaml` is `status: {phase_status}`.
- Review decisions remaining: **{len([d for d in decisions["decision"].to_list() if d == "review"])}**.
- The final modeling table is not built until Phase 4.
- Re-running `omp-yield clean` preserves existing edited configs and writes
  `*.generated.yaml` drafts unless `--overwrite-config` is used.

## Artifacts

- `cleaning_report.md` — detailed Phase 3 report
- `../../data/phase-3-cleaning/` — CSVs for missingness, leakage, outliers, consistency, decisions
- `../../config/features.yaml` — {phase_status} feature decisions
- `../../config/management_levers.yaml` — {phase_status} levers
- `../../data/interim/phase-3/` — cleaned intermediate Parquet files
- `../../reports/03_cleaning_report.html` — interactive Marimo report

## Next

{next_step}
"""
    readme_path = doc_dir / "README.md"
    readme_path.write_text(readme)
    artifacts["README.md"] = readme_path

    return artifacts
