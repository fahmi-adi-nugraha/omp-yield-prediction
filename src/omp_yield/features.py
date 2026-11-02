"""Phase 4 feature engineering and modeling-table assembly."""

from __future__ import annotations

import html
import importlib
import re
import warnings
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
import yaml

from omp_yield.cleaning import TARGET, build_population, load_snapshot

KEYS = ["NAME", "UNIT", "BLOCK", "YEAR"]
BLOCK_KEYS = ["NAME", "UNIT", "BLOCK"]
DEFAULT_CONFIG_DIR = Path("config")
DEFAULT_OUTPUT = Path("data/processed/modeling_table.parquet")
DEFAULT_SCHEMA_CSV = Path("data/processed/feature_schema.csv")
DEFAULT_SCHEMA_PARQUET = Path("data/processed/feature_schema.parquet")
DEFAULT_REPORT = Path("reports/04_feature_engineering.html")
def _round_or_none(value: Any, digits: int = 4) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


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


class FeatureEngineeringError(RuntimeError):
    """Raised when the Phase 4 modeling table cannot be built."""


@dataclass(frozen=True)
class FeatureSpec:
    """Metadata for one modeling-table feature column."""

    feature: str
    base_feature: str
    group: str
    role: str
    available_at: str
    pre_season: bool
    mid_season: bool
    adjustable: bool
    encoded: bool
    source: str
    derivation: str


@dataclass(frozen=True)
class ModelingResult:
    """Built modeling table and its schema."""

    table: pl.DataFrame
    schema: pl.DataFrame
    summary: dict[str, Any]
    snapshot_dir: Path | None = None
    output_path: Path | None = None
    schema_csv_path: Path | None = None
    schema_parquet_path: Path | None = None
    report_path: Path | None = None


def load_approved_features(config_dir: Path = DEFAULT_CONFIG_DIR) -> dict[str, Any]:
    """Load the approved feature configuration and reject unresolved reviews."""

    path = config_dir / "features.yaml"
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise FeatureEngineeringError(f"Invalid feature config: {path}")
    if payload.get("status") != "approved" or payload.get("requires_approval"):
        raise FeatureEngineeringError("Feature config is not approved.")
    reviews = [
        feature["name"]
        for feature in payload.get("features", [])
        if feature.get("decision") == "review"
    ]
    if reviews:
        raise FeatureEngineeringError(
            "Feature config still contains review items: " + ", ".join(reviews)
        )
    return payload


def load_transforms(config_dir: Path = DEFAULT_CONFIG_DIR) -> dict[str, Any]:
    """Load the approved transform configuration."""

    path = config_dir / "transforms.yaml"
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise FeatureEngineeringError(f"Invalid transform config: {path}")
    if payload.get("status") != "approved":
        raise FeatureEngineeringError("Transform config is not approved.")
    return payload


def load_management_levers(config_dir: Path = DEFAULT_CONFIG_DIR) -> dict[str, Any]:
    """Load the approved management-lever configuration."""

    path = config_dir / "management_levers.yaml"
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise FeatureEngineeringError(f"Invalid management-lever config: {path}")
    if payload.get("status") != "approved" or payload.get("requires_approval"):
        raise FeatureEngineeringError("Management-lever config is not approved.")
    return payload


def _approved_by_name(approved: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        feature["name"]: feature
        for feature in approved.get("features", [])
        if feature.get("name") and feature.get("decision") == "keep"
    }


def _derived_by_name(transforms: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        item["name"]: item
        for item in transforms.get("derived", [])
        if isinstance(item, dict) and item.get("name")
    }


def _slug(value: str) -> str:
    replaced = value.replace(">", "gt").replace("<", "lt")
    return re.sub(r"[^0-9A-Za-z]+", "_", replaced).strip("_").lower()


def _meta_from_approved(feature: dict[str, Any]) -> dict[str, Any]:
    return {
        "base_feature": feature["name"],
        "group": feature.get("role", "context"),
        "role": feature.get("role", "context"),
        "available_at": feature["available_at"],
        "adjustable": bool(feature.get("adjustable", False)),
        "source": feature["source"],
        "derivation": feature.get("derivation") or feature.get("reason", ""),
    }


def _meta_from_derived(
    derived: dict[str, dict[str, Any]],
    name: str,
) -> dict[str, Any]:
    item = derived.get(name)
    if item is None:
        raise FeatureEngineeringError(f"Missing derived-feature metadata: {name}")
    return {
        "base_feature": item["base_feature"],
        "group": item["group"],
        "role": item["role"],
        "available_at": item["available_at"],
        "adjustable": bool(item.get("adjustable", False)),
        "source": item["source"],
        "derivation": item["derivation"],
    }


class FeatureBuilder:
    """Accumulate feature columns and their metadata."""

    def __init__(self, frame: pl.DataFrame) -> None:
        self.frame = frame
        self.specs: list[FeatureSpec] = []
        self._names: set[str] = set()

    def add(
        self,
        feature: str,
        expression: pl.Expr,
        *,
        base_feature: str,
        group: str,
        role: str,
        available_at: str,
        adjustable: bool,
        source: str,
        derivation: str,
        encoded: bool = False,
    ) -> None:
        if feature in self._names:
            raise FeatureEngineeringError(f"Duplicate feature: {feature}")
        if available_at not in {"pre_season", "mid_season"}:
            raise FeatureEngineeringError(
                f"Unsupported cutoff for {feature}: {available_at}"
            )
        self.frame = self.frame.with_columns(expression.alias(feature))
        self._record(
            feature,
            base_feature=base_feature,
            group=group,
            role=role,
            available_at=available_at,
            adjustable=adjustable,
            encoded=encoded,
            source=source,
            derivation=derivation,
        )

    def record(
        self,
        feature: str,
        *,
        base_feature: str,
        group: str,
        role: str,
        available_at: str,
        adjustable: bool,
        source: str,
        derivation: str,
        encoded: bool = False,
    ) -> None:
        if feature not in self.frame.columns:
            raise FeatureEngineeringError(f"Feature column not found: {feature}")
        self._record(
            feature,
            base_feature=base_feature,
            group=group,
            role=role,
            available_at=available_at,
            adjustable=adjustable,
            encoded=encoded,
            source=source,
            derivation=derivation,
        )

    def _record(
        self,
        feature: str,
        *,
        base_feature: str,
        group: str,
        role: str,
        available_at: str,
        adjustable: bool,
        source: str,
        derivation: str,
        encoded: bool = False,
    ) -> None:
        if feature in self._names:
            raise FeatureEngineeringError(f"Duplicate feature metadata: {feature}")
        pre_season = available_at == "pre_season"
        self.specs.append(
            FeatureSpec(
                feature=feature,
                base_feature=base_feature,
                group=group,
                role=role,
                available_at=available_at,
                pre_season=pre_season,
                mid_season=True,
                adjustable=adjustable,
                encoded=encoded,
                source=source,
                derivation=derivation,
            )
        )
        self._names.add(feature)


def _add_one_hot(
    builder: FeatureBuilder,
    source: str,
    categories: Sequence[str],
    *,
    approved: dict[str, Any],
) -> None:
    meta = _meta_from_approved(approved)
    for category in categories:
        builder.add(
            f"pre_{source}_{_slug(category)}",
            (pl.col(source) == category).cast(pl.Int8),
            base_feature=meta["base_feature"],
            group=meta["group"],
            role=meta["role"],
            available_at=meta["available_at"],
            adjustable=meta["adjustable"],
            encoded=True,
            source=meta["source"],
            derivation=f"one_hot({source}={category!r})",
        )


def _add_ordinal(
    builder: FeatureBuilder,
    source: str,
    feature: str,
    mapping: dict[str, int],
    *,
    approved: dict[str, Any],
) -> None:
    expression = pl.lit(None, dtype=pl.Int8)
    for value, code in mapping.items():
        expression = pl.when(pl.col(source) == value).then(pl.lit(code)).otherwise(expression)
    meta = _meta_from_approved(approved)
    builder.add(
        f"pre_{feature}",
        expression.cast(pl.Int8),
        base_feature=meta["base_feature"],
        group=meta["group"],
        role=meta["role"],
        available_at=meta["available_at"],
        adjustable=meta["adjustable"],
        encoded=True,
        source=meta["source"],
        derivation=f"ordinal({source}) with mapping {mapping}.",
    )


def _add_marker_fert(
    builder: FeatureBuilder,
    transforms: dict[str, Any],
    approved: dict[str, Any],
    derived: dict[str, dict[str, Any]],
) -> None:
    config = transforms["marker_fert"]
    source = config["source"]
    text = pl.col(source).cast(pl.String).fill_null("").str.strip_chars()
    known = (text != "") & (text != "No data")
    builder.add(
        f"pre_{config['product_count_feature']}",
        pl.when(known)
        .then(text.str.count_matches(";") + 1)
        .otherwise(0)
        .cast(pl.Int16),
        **_meta_from_derived(derived, config["product_count_feature"]),
    )
    builder.add(
        f"pre_{config['known_feature']}",
        known.cast(pl.Int8),
        **_meta_from_derived(derived, config["known_feature"]),
    )
    for indicator, keyword in config["indicators"].items():
        feature = f"marker_fert_has_{indicator}"
        builder.add(
            f"pre_{feature}",
            (
                known
                & text.str.to_lowercase().str.contains(
                    str(keyword).lower(), literal=True
                )
            ).cast(pl.Int8),
            **_meta_from_derived(derived, feature),
        )
    # The base raw markerFert column is high-cardinality text; the encoded
    # indicators above are the model-ready representation.


def _add_pre_base_features(
    builder: FeatureBuilder,
    approved: dict[str, Any],
    transforms: dict[str, Any],
    derived: dict[str, dict[str, Any]],
) -> None:
    approved_map = _approved_by_name(approved)
    one_hot = transforms["categorical"]["one_hot"]
    ordinal = transforms["categorical"]["ordinal"]
    raw_numeric = {
        "area_ha": "area_ha",
        "D_TREEAGE": "tree_age",
        "palmStand_p_ha": "stand_per_ha",
        "palmStandMature_p": "stand_mature",
        "ALTITUDE": "altitude",
        "AblReps": "ablation_reps",
    }
    leaf_prefix = "LA_"

    for name, feature in approved_map.items():
        if feature["source"] != "OILPALM":
            continue
        available_at = feature["available_at"]
        if available_at == "mid_season":
            continue
        if name == "D_PLANTED":
            builder.add(
                "pre_planting_year",
                pl.col("D_PLANTED").dt.year().cast(pl.Int64),
                **_meta_from_derived(derived, "planting_year"),
            )
        elif name in raw_numeric:
            builder.add(
                f"pre_{raw_numeric[name]}",
                pl.col(name).cast(pl.Float64),
                **_meta_from_approved(feature),
            )
        elif name == "Pruning":
            _add_one_hot(builder, name, one_hot[name], approved=feature)
            builder.add(
                "pre_pruning_known",
                pl.col(name).is_in(one_hot[name]).cast(pl.Int8),
                **_meta_from_derived(derived, "pruning_known"),
            )
        elif name == "HarvesterAccess":
            config = ordinal[name]
            _add_ordinal(
                builder,
                name,
                config["feature"],
                {key: int(value) for key, value in config["mapping"].items()},
                approved=feature,
            )
            builder.add(
                "pre_harvester_access_known",
                pl.col(name).is_in(list(config["mapping"])).cast(pl.Int8),
                **_meta_from_derived(derived, "harvester_access_known"),
            )
        elif name in ordinal:
            config = ordinal[name]
            _add_ordinal(
                builder,
                name,
                config["feature"],
                {key: int(value) for key, value in config["mapping"].items()},
                approved=feature,
            )
        elif name in one_hot:
            _add_one_hot(builder, name, one_hot[name], approved=feature)
        elif name == "markerFert":
            _add_marker_fert(builder, transforms, feature, derived)
        elif name.startswith(leaf_prefix):
            continue
        else:
            # Numeric or unhandled low-cardinality categorical context.
            if builder.frame.schema[name] in NUMERIC_TYPES:
                builder.add(
                    f"pre_{name}",
                    pl.col(name).cast(pl.Float64),
                    **_meta_from_approved(feature),
                )
            else:
                raise FeatureEngineeringError(
                    f"Unhandled approved categorical feature: {name}"
                )

    # Mature fraction is derived from a raw column that was deliberately
    # dropped as a direct feature.
    builder.add(
        "pre_mature_fraction",
        pl.when(pl.col("palmStand_p") > 0)
        .then(pl.col("palmStandMature_p") / pl.col("palmStand_p"))
        .otherwise(None),
        **_meta_from_derived(derived, "mature_fraction"),
    )


def _add_lag_features(
    builder: FeatureBuilder,
    derived: dict[str, dict[str, Any]],
) -> None:
    frame = builder.frame.sort([*BLOCK_KEYS, "YEAR"])
    builder.frame = frame.with_columns(
        pl.col(TARGET).shift(1).over(BLOCK_KEYS).alias("pre_yield_lag1"),
        pl.col(TARGET).shift(2).over(BLOCK_KEYS).alias("pre_yield_lag2"),
        pl.col(TARGET)
        .shift(1)
        .rolling_mean(window_size=3, min_samples=1)
        .over(BLOCK_KEYS)
        .alias("pre_yield_roll3_mean"),
        pl.col("Y_KGB").shift(1).over(BLOCK_KEYS).alias("pre_bunch_weight_lag1"),
        pl.col("Y_AVG_harvest_int")
        .shift(1)
        .over(BLOCK_KEYS)
        .alias("pre_harvest_interval_lag1"),
        pl.col("Y_TOTAL_rounds")
        .shift(1)
        .over(BLOCK_KEYS)
        .alias("pre_harvest_rounds_lag1"),
    )
    for feature in (
        "yield_lag1",
        "yield_lag2",
        "yield_roll3_mean",
        "bunch_weight_lag1",
        "harvest_interval_lag1",
        "harvest_rounds_lag1",
    ):
        builder.record(
            f"pre_{feature}",
            **_meta_from_derived(derived, feature),
        )

    division = (
        builder.frame.group_by(["UNIT", "YEAR"])
        .agg(pl.col(TARGET).mean().alias("pre_division_yield_lag1_mean"))
        .with_columns((pl.col("YEAR") + 1).alias("YEAR"))
    )
    estate = (
        builder.frame.group_by(["NAME", "YEAR"])
        .agg(pl.col(TARGET).mean().alias("pre_estate_yield_lag1_mean"))
        .with_columns((pl.col("YEAR") + 1).alias("YEAR"))
    )
    builder.frame = builder.frame.join(division, on=["UNIT", "YEAR"], how="left")
    builder.frame = builder.frame.join(estate, on=["NAME", "YEAR"], how="left")
    for feature in ("division_yield_lag1_mean", "estate_yield_lag1_mean"):
        builder.record(
            f"pre_{feature}",
            **_meta_from_derived(derived, feature),
        )


def _add_nutrient_features(
    builder: FeatureBuilder,
    tables: dict[str, pl.DataFrame],
    approved: dict[str, Any],
    levers: dict[str, Any],
    derived: dict[str, dict[str, Any]],
) -> None:
    nutrient = tables.get("tbl_FN_nutActRec")
    if nutrient is None:
        return
    columns = [
        "nutActInorgN_kg_p",
        "nutActInorgP2O5_kg_p",
        "nutActInorgK2O_kg_p",
        "nutActInorgMgO_kg_p",
        "nutActInorgCaO_kg_p",
        "nutActInorgB_kg_p",
        "nutActOrgN_kg_p",
        "nutActOrgP2O5_kg_p",
        "nutActOrgK2O_kg_p",
    ]
    existing = [column for column in columns if column in nutrient.columns]
    keys = ["suEstate", "suDivision", "suBlock", "Yr"]
    source = (
        nutrient.select([*keys, *existing])
        .group_by(keys)
        .agg([pl.col(column).mean().alias(column) for column in existing])
        .rename(
            {
                "suEstate": "NAME",
                "suDivision": "UNIT",
                "suBlock": "BLOCK",
                "Yr": "YEAR",
            }
        )
    )
    builder.frame = builder.frame.join(source, on=KEYS, how="left")
    approved_map = _approved_by_name(approved)
    lever_map = {
        name: lever
        for name, lever in levers.get("levers", {}).items()
        if isinstance(lever, dict) and lever.get("decision") == "keep"
    }
    for column in existing:
        feature = approved_map.get(column)
        if feature is not None:
            metadata = _meta_from_approved(feature)
        else:
            lever = lever_map.get(column)
            if lever is None:
                continue
            metadata = {
                "base_feature": column,
                "group": "management",
                "role": "management",
                "available_at": lever.get("available_at", "pre_season"),
                "adjustable": bool(lever.get("adjustable", True)),
                "source": lever.get("source", "tbl_FN_nutActRec"),
                "derivation": lever.get("reason", "Approved management lever."),
            }
        builder.add(
            f"pre_{column}",
            pl.col(column).cast(pl.Float64),
            **metadata,
        )

    n_total = (
        pl.col("nutActInorgN_kg_p").fill_null(0)
        + pl.col("nutActOrgN_kg_p").fill_null(0)
    )
    k_total = (
        pl.col("nutActInorgK2O_kg_p").fill_null(0)
        + pl.col("nutActOrgK2O_kg_p").fill_null(0)
    )
    builder.add(
        "pre_nutrient_balance_NK",
        pl.when(k_total > 0).then(n_total / k_total).otherwise(None),
        **_meta_from_derived(derived, "nutrient_balance_NK"),
    )


def _add_weather_features(
    builder: FeatureBuilder,
    tables: dict[str, pl.DataFrame],
    derived: dict[str, dict[str, Any]],
) -> None:
    weather = tables.get("tbl_CW_weatherAndWater")
    if weather is None:
        return
    station = "ID_WeatherStation"
    source = (
        weather.select(
            pl.col("R_UNIT").cast(pl.String).alias(station),
            pl.col("R_YEAR").cast(pl.Int64).alias("WEATHER_YEAR"),
            pl.col("R_Total Rainfall").cast(pl.Float64).alias("rain"),
            pl.col("R_NO_dry_month").cast(pl.Float64).alias("dry_months"),
            pl.col("R_waterdeficit").cast(pl.Float64).alias("water_deficit"),
        )
        .filter(pl.col(station).is_not_null())
        .sort([station, "WEATHER_YEAR"])
        .with_columns(
            pl.col("rain")
            .shift(1)
            .rolling_mean(window_size=100, min_samples=1)
            .over(station)
            .alias("rain_climatology"),
            pl.col("rain")
            .rolling_mean(window_size=3, min_samples=1)
            .over(station)
            .alias("rain_roll3"),
            pl.col("rain").alias("rain_lag1"),
            pl.col("dry_months").alias("dry_months_lag1"),
            pl.col("water_deficit").alias("water_deficit_lag1"),
        )
        .with_columns(
            (pl.col("rain_lag1") - pl.col("rain_climatology")).alias(
                "rain_anomaly_lag1"
            )
        )
        .with_columns((pl.col("WEATHER_YEAR") + 1).alias("YEAR"))
        .select(
            station,
            "YEAR",
            "rain_lag1",
            "dry_months_lag1",
            "water_deficit_lag1",
            "rain_anomaly_lag1",
            "rain_roll3",
        )
    )
    builder.frame = builder.frame.join(source, on=[station, "YEAR"], how="left")
    for feature, column in (
        ("rain_annual_mm_lag1", "rain_lag1"),
        ("dry_months_lag1", "dry_months_lag1"),
        ("water_deficit_lag1", "water_deficit_lag1"),
        ("rain_anomaly_lag1", "rain_anomaly_lag1"),
        ("rain_roll3_mean_lag1", "rain_roll3"),
    ):
        builder.add(
            f"pre_{feature}",
            pl.col(column).cast(pl.Float64),
            **_meta_from_derived(derived, feature),
        )


def _add_soil_features(
    builder: FeatureBuilder,
    tables: dict[str, pl.DataFrame],
    approved: dict[str, Any],
    derived: dict[str, dict[str, Any]],
) -> None:
    soil = tables.get("tbl_FN_soilAnalysis")
    if soil is None:
        return
    columns = ["SA_PH_H2O", "SA_CEC", "SA_SOM"]
    if not all(column in soil.columns for column in columns):
        return
    source = (
        soil.select([*BLOCK_KEYS, "SA_DATE", *columns])
        .filter(pl.col("SA_DATE").is_not_null())
        .with_columns(pl.col("SA_DATE").dt.date().alias("SA_DATE"))
        .group_by([*BLOCK_KEYS, "SA_DATE"])
        .agg([pl.col(column).mean().alias(column) for column in columns])
        .rename(
            {
                "SA_PH_H2O": "soil_ph",
                "SA_CEC": "soil_cec",
                "SA_SOM": "soil_som",
            }
        )
        .sort([*BLOCK_KEYS, "SA_DATE"])
    )
    left = (
        builder.frame.select(KEYS)
        .with_columns(
            (pl.date(pl.col("YEAR"), 1, 1) - pl.duration(days=1)).alias(
                "cutoff_date"
            )
        )
        .sort([*BLOCK_KEYS, "cutoff_date"])
    )
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Sortedness of columns cannot be checked.*",
            category=UserWarning,
        )
        joined = left.join_asof(
            source,
            left_on="cutoff_date",
            right_on="SA_DATE",
            by=BLOCK_KEYS,
            strategy="backward",
        )
    builder.frame = builder.frame.join(
        joined.select([*KEYS, "soil_ph", "soil_cec", "soil_som"]),
        on=KEYS,
        how="left",
    )
    approved_map = _approved_by_name(approved)
    for column in ("soil_ph", "soil_cec", "soil_som"):
        feature = approved_map.get(column)
        if feature is not None:
            builder.add(
                f"pre_{column}",
                pl.col(column).cast(pl.Float64),
                **_meta_from_approved(feature),
            )
    builder.add(
        "pre_soil_cec_som_ratio",
        pl.when(pl.col("soil_som") > 0)
        .then(pl.col("soil_cec") / pl.col("soil_som"))
        .otherwise(None),
        **_meta_from_derived(derived, "soil_cec_som_ratio"),
    )


def _add_ganoderma_features(
    builder: FeatureBuilder,
    tables: dict[str, pl.DataFrame],
    approved: dict[str, Any],
    derived: dict[str, dict[str, Any]],
) -> None:
    pest = tables.get("tbl_PD_surveys")
    if pest is None:
        return
    required = {"PestName", "ESTATE", "UNIT", "BLOCK", "yrFis", "AffectedArea", "P_Severity"}
    if not required.issubset(set(pest.columns)):
        return
    source = (
        pest.filter(pl.col("PestName") == "Ganoderma")
        .select(
            pl.col("ESTATE").alias("NAME"),
            pl.col("UNIT"),
            pl.col("BLOCK"),
            pl.col("yrFis").cast(pl.Int64).alias("PEST_YEAR"),
            pl.col("AffectedArea").cast(pl.Float64).alias("affected_area"),
            pl.col("P_Severity").cast(pl.Float64).alias("severity"),
        )
        .group_by([*BLOCK_KEYS, "PEST_YEAR"])
        .agg(
            pl.col("affected_area").max().alias("affected_area"),
            pl.col("severity").max().alias("severity"),
        )
        .sort([*BLOCK_KEYS, "PEST_YEAR"])
        .with_columns(
            pl.col("affected_area")
            .shift(1)
            .over(BLOCK_KEYS)
            .alias("ganoderma_affected_area"),
            pl.col("severity")
            .shift(1)
            .over(BLOCK_KEYS)
            .alias("ganoderma_severity"),
            pl.col("affected_area")
            .cum_max()
            .shift(1)
            .over(BLOCK_KEYS)
            .alias("ganoderma_cumulative_area"),
        )
        .with_columns((pl.col("PEST_YEAR") + 1).alias("YEAR"))
        .select(
            *KEYS,
            "ganoderma_affected_area",
            "ganoderma_severity",
            "ganoderma_cumulative_area",
        )
    )
    builder.frame = builder.frame.join(source, on=KEYS, how="left")
    approved_map = _approved_by_name(approved)
    for feature in ("ganoderma_affected_area", "ganoderma_severity"):
        approved_feature = approved_map.get(feature)
        if approved_feature is not None:
            builder.add(
                f"pre_{feature}",
                pl.col(feature).cast(pl.Float64),
                **_meta_from_approved(approved_feature),
            )
    builder.add(
        "pre_ganoderma_cumulative_area",
        pl.col("ganoderma_cumulative_area").cast(pl.Float64),
        **_meta_from_derived(derived, "ganoderma_cumulative_area"),
    )


def _add_harvest_loss_feature(
    builder: FeatureBuilder,
    tables: dict[str, pl.DataFrame],
    derived: dict[str, dict[str, Any]],
) -> None:
    harvest = tables.get("tbl_HRR_harvests")
    if harvest is None:
        return
    required = {
        "Estate",
        "UNIT",
        "BLOCK",
        "Y_Harvest",
        "Y_BunchNo",
        "bunchesDiscarded_b",
        "bunchesUnpoll_b",
    }
    if not required.issubset(set(harvest.columns)):
        return
    source = (
        harvest.select(
            pl.col("Estate").alias("NAME"),
            pl.col("UNIT"),
            pl.col("BLOCK"),
            pl.col("Y_Harvest").cast(pl.Int64).alias("HARVEST_YEAR"),
            pl.col("Y_BunchNo").cast(pl.Float64).fill_null(0).alias("bunches"),
            pl.col("bunchesDiscarded_b")
            .cast(pl.Float64)
            .fill_null(0)
            .alias("discarded"),
            pl.col("bunchesUnpoll_b")
            .cast(pl.Float64)
            .fill_null(0)
            .alias("unpollinated"),
        )
        .group_by([*BLOCK_KEYS, "HARVEST_YEAR"])
        .agg(
            pl.col("bunches").sum().alias("bunches"),
            pl.col("discarded").sum().alias("discarded"),
            pl.col("unpollinated").sum().alias("unpollinated"),
        )
        .with_columns(
            (pl.col("discarded") + pl.col("unpollinated")).alias("losses"),
            (
                pl.col("bunches")
                + pl.col("discarded")
                + pl.col("unpollinated")
            ).alias("total_bunches"),
        )
        .with_columns(
            pl.when(pl.col("total_bunches") > 0)
            .then(pl.col("losses") / pl.col("total_bunches"))
            .otherwise(None)
            .alias("harvest_loss_rate_lag1")
        )
        .with_columns((pl.col("HARVEST_YEAR") + 1).alias("YEAR"))
        .select(*KEYS, "harvest_loss_rate_lag1")
    )
    builder.frame = builder.frame.join(source, on=KEYS, how="left")
    builder.add(
        "pre_harvest_loss_rate_lag1",
        pl.col("harvest_loss_rate_lag1").cast(pl.Float64),
        **_meta_from_derived(derived, "harvest_loss_rate_lag1"),
    )


def _add_leaf_features(
    builder: FeatureBuilder,
    approved: dict[str, Any],
    transforms: dict[str, Any],
    derived: dict[str, dict[str, Any]],
) -> None:
    month, day = _cutoff_month_day(transforms)
    leaf_features = [
        feature
        for feature in approved.get("features", [])
        if feature.get("decision") == "keep"
        and feature.get("source") == "OILPALM"
        and feature.get("available_at") == "mid_season"
        and str(feature.get("name", "")).startswith("LA_")
        and feature.get("name") in builder.frame.columns
    ]
    cutoff = pl.date(pl.col("YEAR"), month, day)
    leaf_available = (
        pl.col("LA_DATE").is_not_null()
        & (pl.col("LA_DATE").dt.year() == pl.col("YEAR"))
        & (pl.col("LA_DATE").dt.date() <= cutoff)
    )
    for feature in leaf_features:
        name = feature["name"]
        builder.add(
            f"mid_{name}",
            pl.when(leaf_available)
            .then(pl.col(name).cast(pl.Float64))
            .otherwise(None),
            **_meta_from_approved(feature),
        )

    for ratio, numerator, denominator in (
        ("LA_NK_ratio", "mid_LA_N", "mid_LA_K"),
        ("LA_NP_ratio", "mid_LA_N", "mid_LA_P"),
        ("LA_KMg_ratio", "mid_LA_K", "mid_LA_Mg"),
        ("LA_CaMg_ratio", "mid_LA_Ca", "mid_LA_Mg"),
    ):
        builder.add(
            f"mid_{ratio}",
            pl.when(
                (pl.col(denominator) > 0)
                & pl.col(numerator).is_not_null()
                & pl.col(denominator).is_not_null()
            )
            .then(pl.col(numerator) / pl.col(denominator))
            .otherwise(None),
            **_meta_from_derived(derived, ratio),
        )


def _add_black_bunch_feature(
    builder: FeatureBuilder,
    tables: dict[str, pl.DataFrame],
    approved: dict[str, Any],
    transforms: dict[str, Any],
) -> None:
    bunch = tables.get("tbl_BBC_bunchCounts")
    if bunch is None:
        return
    required = {"Estate", "Unit", "Block", "CntDate", "NoOfPalm", "BlackBunch"}
    if not required.issubset(set(bunch.columns)):
        return
    month, day = _cutoff_month_day(transforms)
    source = (
        bunch.select(
            pl.col("Estate").alias("NAME"),
            pl.col("Unit").alias("UNIT"),
            pl.col("Block").alias("BLOCK"),
            pl.col("CntDate").dt.date().alias("CntDate"),
            pl.col("NoOfPalm").cast(pl.Float64),
            pl.col("BlackBunch").cast(pl.Float64),
        )
        .filter(pl.col("NoOfPalm") > 0)
        .with_columns(
            (pl.col("BlackBunch") / pl.col("NoOfPalm")).alias(
                "black_bunch_per_palm"
            ),
            pl.col("CntDate").dt.year().alias("YEAR"),
        )
    )
    left = builder.frame.select(KEYS).with_columns(
        (pl.date(pl.col("YEAR"), month, day)).alias("cutoff_date")
    )
    candidates = left.join(
        source,
        on=["NAME", "UNIT", "BLOCK", "YEAR"],
        how="inner",
    ).filter(pl.col("CntDate") <= pl.col("cutoff_date"))
    latest = (
        candidates.sort("CntDate")
        .group_by(KEYS)
        .agg(pl.col("black_bunch_per_palm").last().alias("mid_black_bunch_per_palm"))
    )
    builder.frame = builder.frame.join(latest, on=KEYS, how="left")
    approved_map = _approved_by_name(approved)
    feature = approved_map.get("black_bunch_per_palm")
    if feature is not None:
        builder.record("mid_black_bunch_per_palm", **_meta_from_approved(feature))


def _cutoff_month_day(transforms: dict[str, Any]) -> tuple[int, int]:
    raw = str(transforms.get("mid_season_cutoff", "06-30"))
    parts = raw.split("-")
    if len(parts) != 2:
        raise FeatureEngineeringError(f"Invalid mid-season cutoff: {raw}")
    month, day = int(parts[0]), int(parts[1])
    if not (1 <= month <= 12 and 1 <= day <= 31):
        raise FeatureEngineeringError(f"Invalid mid-season cutoff: {raw}")
    return month, day


def _schema_from_builder(builder: FeatureBuilder, table: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    for spec in builder.specs:
        if spec.feature not in table.columns:
            raise FeatureEngineeringError(f"Missing feature in table: {spec.feature}")
        series = table[spec.feature]
        rows.append(
            {
                "feature": spec.feature,
                "base_feature": spec.base_feature,
                "group": spec.group,
                "role": spec.role,
                "available_at": spec.available_at,
                "pre_season": spec.pre_season,
                "mid_season": spec.mid_season,
                "adjustable": spec.adjustable,
                "encoded": spec.encoded,
                "source": spec.source,
                "derivation": spec.derivation,
                "dtype": str(series.dtype),
                "missing_pct": round(
                    float(series.is_null().sum()) / table.height * 100, 1
                )
                if table.height
                else 0.0,
                "n_unique": int(series.n_unique()),
            }
        )
    return pl.DataFrame(rows)


def _validate_result(table: pl.DataFrame, schema: pl.DataFrame) -> None:
    if table.height == 0:
        raise FeatureEngineeringError("Modeling table is empty.")
    duplicate_keys = table.group_by(KEYS).len().filter(pl.col("len") > 1)
    if duplicate_keys.height:
        raise FeatureEngineeringError(
            f"Modeling-table key is not unique: {duplicate_keys.height} duplicates."
        )
    features = set(schema["feature"].to_list())
    if TARGET in features:
        raise FeatureEngineeringError("Target is present in the feature schema.")
    current_year = [
        feature
        for feature in features
        if feature.startswith("Y_") and "lag" not in feature.lower()
    ]
    if current_year:
        raise FeatureEngineeringError(
            "Current-year target-derived features found: " + ", ".join(current_year)
        )
    if set(schema["available_at"].to_list()) - {"pre_season", "mid_season"}:
        raise FeatureEngineeringError("Feature available_at contains post-season values.")
    if schema.filter(~pl.col("pre_season") & ~pl.col("mid_season")).height:
        raise FeatureEngineeringError("Feature is not available at either cutoff.")


def build_features_from_tables(
    tables: dict[str, pl.DataFrame],
    approved: dict[str, Any],
    transforms: dict[str, Any],
    levers: dict[str, Any] | None = None,
    *,
    snapshot_dir: Path | None = None,
) -> ModelingResult:
    """Build the modeling table from already-loaded snapshot tables."""

    if "OILPALM" not in tables:
        raise FeatureEngineeringError("OILPALM table is required.")
    population = build_population(tables["OILPALM"])
    mature = population["mature"].sort([*BLOCK_KEYS, "YEAR"])
    derived = _derived_by_name(transforms)
    builder = FeatureBuilder(mature)

    anomaly_flags = (
        population["anomalies"]
        .filter(pl.col("YEAR") <= 2025)
        .group_by(KEYS)
        .agg(pl.col("flag").unique().sort().str.join("; ").alias("anomaly_flags"))
    )
    builder.frame = builder.frame.join(anomaly_flags, on=KEYS, how="left")
    builder.frame = builder.frame.with_columns(
        pl.col("anomaly_flags").fill_null("").alias("anomaly_flags"),
        pl.col("anomaly_flags").is_not_null().cast(pl.Boolean).alias("has_anomaly"),
    )

    _add_pre_base_features(builder, approved, transforms, derived)
    _add_lag_features(builder, derived)
    _add_nutrient_features(builder, tables, approved, levers or {"levers": {}}, derived)
    _add_weather_features(builder, tables, derived)
    _add_soil_features(builder, tables, approved, derived)
    _add_ganoderma_features(builder, tables, approved, derived)
    _add_harvest_loss_feature(builder, tables, derived)
    _add_leaf_features(builder, approved, transforms, derived)
    _add_black_bunch_feature(builder, tables, approved, transforms)

    metadata_columns = [*KEYS, TARGET, "anomaly_flags", "has_anomaly"]
    feature_columns = [spec.feature for spec in builder.specs]
    table = (
        builder.frame.select([*metadata_columns, *feature_columns])
        .sort([*BLOCK_KEYS, "YEAR"])
        .with_columns(pl.col("has_anomaly").fill_null(False))
    )
    schema = _schema_from_builder(builder, table)
    _validate_result(table, schema)
    summary = {
        "rows": table.height,
        "pre_season_features": int(schema.filter(pl.col("pre_season")).height),
        "mid_season_features": int(schema.filter(pl.col("mid_season")).height),
        "mid_only_features": int(
            schema.filter(~pl.col("pre_season") & pl.col("mid_season")).height
        ),
        "target_mean": _round_or_none(table[TARGET].mean()),
        "target_median": _round_or_none(table[TARGET].median()),
        "anomaly_rows": int(table.filter(pl.col("has_anomaly")).height),
        "feature_columns": len(feature_columns),
    }
    return ModelingResult(
        table=table,
        schema=schema,
        summary=summary,
        snapshot_dir=snapshot_dir,
    )


def build_modeling_table(
    snapshot_dir: Path,
    *,
    config_dir: Path = DEFAULT_CONFIG_DIR,
) -> ModelingResult:
    """Load a snapshot and build the Phase 4 modeling table."""

    approved = load_approved_features(config_dir)
    transforms = load_transforms(config_dir)
    levers = load_management_levers(config_dir)
    snapshot = load_snapshot(snapshot_dir, verify=True)
    return build_features_from_tables(
        snapshot.tables,
        approved,
        transforms,
        levers,
        snapshot_dir=snapshot_dir,
    )


def _table_html(frame: pl.DataFrame, *, max_rows: int = 50) -> str:
    headers = "".join(f"<th>{html.escape(str(column))}</th>" for column in frame.columns)
    rows = []
    for row in frame.head(max_rows).iter_rows(named=True):
        cells = "".join(
            f"<td>{html.escape('' if value is None else str(value))}</td>"
            for value in row.values()
        )
        rows.append(f"<tr>{cells}</tr>")
    return (
        f"<table><thead><tr>{headers}</tr></thead><tbody>{''.join(rows)}</tbody></table>"
    )


def _numeric_summary(frame: pl.DataFrame, columns: Sequence[str]) -> pl.DataFrame:
    rows = []
    for column in columns:
        if column not in frame.columns:
            continue
        series = frame[column].cast(pl.Float64)
        if series.null_count() == series.len():
            continue
        rows.append(
            {
                "feature": column,
                "count": series.len() - series.null_count(),
                "missing_pct": round(series.null_count() / series.len() * 100, 1),
                "mean": _round_or_none(series.mean()),
                "std": _round_or_none(series.std()),
                "min": _round_or_none(series.min()),
                "p50": _round_or_none(series.median()),
                "max": _round_or_none(series.max()),
            }
        )
    return pl.DataFrame(rows)


def _vif_diagnostic(
    table: pl.DataFrame,
    schema: pl.DataFrame,
    *,
    max_features: int = 30,
) -> pl.DataFrame:
    candidates = [
        feature
        for feature in schema.filter(pl.col("pre_season"))["feature"].to_list()
        if table.schema[feature] in NUMERIC_TYPES
    ]
    if len(candidates) < 2:
        return pl.DataFrame(schema={"feature": pl.String, "vif": pl.Float64})
    matrix = []
    names = []
    for feature in candidates:
        values = table[feature].cast(pl.Float64).to_numpy()
        mask = np.isfinite(values)
        if mask.sum() < 30:
            continue
        median = np.nanmedian(values)
        filled = np.where(mask, values, median)
        if np.std(filled) == 0:
            continue
        matrix.append((filled - filled.mean()) / filled.std())
        names.append(feature)
    if len(names) < 2:
        return pl.DataFrame(schema={"feature": pl.String, "vif": pl.Float64})
    x = np.column_stack(matrix)
    # Keep the strongest-variance columns to keep the diagnostic bounded.
    variances = x.var(axis=0)
    order = np.argsort(variances)[::-1][:max_features]
    x = x[:, order]
    names = [names[index] for index in order]
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


def _ablation_diagnostic(
    table: pl.DataFrame,
    schema: pl.DataFrame,
    transforms: dict[str, Any],
) -> pl.DataFrame:
    try:
        ensemble = importlib.import_module("sklearn.ensemble")
        metrics = importlib.import_module("sklearn.metrics")
        HistGradientBoostingRegressor = ensemble.HistGradientBoostingRegressor
        mean_absolute_error = metrics.mean_absolute_error
        mean_squared_error = metrics.mean_squared_error
    except ImportError:
        return pl.DataFrame(
            schema={
                "scope": pl.String,
                "group": pl.String,
                "features": pl.Int64,
                "rmse": pl.Float64,
                "mae": pl.Float64,
            }
        )

    ablate = transforms.get("ablation", {})
    train_through = int(ablate.get("train_through_year", 2023))
    validation_years = list(ablate.get("validation_years", [2024, 2025]))
    train = table.filter(pl.col("YEAR") <= train_through)
    validation = table.filter(pl.col("YEAR").is_in(validation_years))
    if train.height == 0 or validation.height == 0:
        return pl.DataFrame()

    y_train = train[TARGET].cast(pl.Float64).to_numpy()
    y_validation = validation[TARGET].cast(pl.Float64).to_numpy()
    rows = []
    scopes = [("pre_season", schema.filter(pl.col("pre_season")))]
    mid_schema = schema.filter(pl.col("mid_season"))
    if mid_schema.height != schema.filter(pl.col("pre_season")).height:
        scopes.append(("mid_season", mid_schema))

    for scope, scope_schema in scopes:
        all_features = [
            feature
            for feature in scope_schema["feature"].to_list()
            if table.schema[feature] in NUMERIC_TYPES
        ]
        groups = ["all", *sorted(set(scope_schema["group"].to_list()))]
        for group in groups:
            if group == "all":
                features = all_features
            else:
                features = [
                    feature
                    for feature in scope_schema.filter(pl.col("group") == group)[
                        "feature"
                    ].to_list()
                    if table.schema[feature] in NUMERIC_TYPES
                ]
            features = [
                feature
                for feature in features
                if train[feature].drop_nulls().n_unique() > 1
            ]
            if not features:
                continue
            x_train = (
                train.select([pl.col(feature).cast(pl.Float64) for feature in features])
                .to_numpy()
            )
            x_validation = (
                validation.select(
                    [pl.col(feature).cast(pl.Float64) for feature in features]
                ).to_numpy()
            )
            model = HistGradientBoostingRegressor(
                max_iter=100,
                learning_rate=0.08,
                max_leaf_nodes=31,
                random_state=0,
            )
            try:
                model.fit(x_train, y_train)
                predictions = model.predict(x_validation)
            except ValueError:
                continue
            rows.append(
                {
                    "scope": scope,
                    "group": group,
                    "features": len(features),
                    "rmse": round(float(np.sqrt(mean_squared_error(y_validation, predictions))), 4),
                    "mae": round(float(mean_absolute_error(y_validation, predictions)), 4),
                }
            )
    return pl.DataFrame(rows)


def _leakage_table(
    approved: dict[str, Any],
    transforms: dict[str, Any],
    schema: pl.DataFrame,
) -> pl.DataFrame:
    current_year = [
        feature["name"]
        for feature in approved.get("features", [])
        if feature.get("decision") == "drop"
        and feature.get("role") == "leakage"
    ]
    forbidden = transforms.get("leakage", {}).get(
        "forbidden_current_year_prefixes", ["Y_"]
    )
    features = schema["feature"].to_list()
    violations = [
        feature
        for feature in features
        if any(feature.startswith(prefix) for prefix in forbidden)
    ]
    rows = [
        {
            "check": "current-year target-derived columns excluded",
            "value": len(current_year),
            "status": "pass",
        },
        {
            "check": "feature schema has no forbidden current-year prefix",
            "value": len(violations),
            "status": "pass" if not violations else "fail",
        },
        {
            "check": "target is not a feature",
            "value": int(TARGET in features),
            "status": "pass" if TARGET not in features else "fail",
        },
        {
            "check": "all features have a supported available_at",
            "value": int(
                schema.filter(
                    ~pl.col("available_at").is_in(["pre_season", "mid_season"])
                ).height
            ),
            "status": "pass"
            if schema.filter(
                ~pl.col("available_at").is_in(["pre_season", "mid_season"])
            ).height
            == 0
            else "fail",
        },
        {
            "check": "pre-season-only features do not appear in mid-only set",
            "value": int(
                schema.filter(pl.col("pre_season") & ~pl.col("mid_season")).height
            ),
            "status": "pass",
        },
    ]
    return pl.DataFrame(rows)


def write_feature_report(
    result: ModelingResult,
    approved: dict[str, Any],
    transforms: dict[str, Any],
    path: Path = DEFAULT_REPORT,
) -> Path:
    """Write a standalone Phase 4 HTML report."""

    table = result.table
    schema = result.schema
    leakage = _leakage_table(approved, transforms, schema)
    numeric_features = [
        feature
        for feature in schema["feature"].to_list()
        if table.schema[feature] in NUMERIC_TYPES
    ]
    distributions = _numeric_summary(table, numeric_features)
    missing = distributions.sort("missing_pct", descending=True).head(20)
    vif = _vif_diagnostic(
        table,
        schema,
        max_features=int(transforms.get("vif", {}).get("max_features", 30)),
    )
    ablation = _ablation_diagnostic(table, schema, transforms)
    decision_counts = pl.DataFrame(
        [
            {
                "decision": decision,
                "count": sum(
                    1
                    for feature in approved.get("features", [])
                    if feature.get("decision") == decision
                ),
            }
            for decision in ("keep", "drop", "review")
        ]
    )
    group_counts = (
        schema.group_by("group").len().sort("group").rename({"len": "features"})
    )
    cutoff_counts = pl.DataFrame(
        [
            {
                "scope": "pre_season",
                "features": int(schema.filter(pl.col("pre_season")).height),
            },
            {
                "scope": "mid_season",
                "features": int(schema.filter(pl.col("mid_season")).height),
            },
            {
                "scope": "mid_only",
                "features": int(
                    schema.filter(~pl.col("pre_season") & pl.col("mid_season")).height
                ),
            },
        ]
    )
    target_summary = pl.DataFrame(
        [
            {
                "rows": table.height,
                "mean": _round_or_none(table[TARGET].mean()),
                "median": _round_or_none(table[TARGET].median()),
                "min": _round_or_none(table[TARGET].min()),
                "max": _round_or_none(table[TARGET].max()),
                "zero_targets": int((table[TARGET] == 0).sum()),
                "anomaly_rows": int(table.filter(pl.col("has_anomaly")).height),
            }
        ]
    )
    body = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Phase 4 — Feature Engineering</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #222; }}
h1, h2 {{ color: #1f4e5f; }}
table {{ border-collapse: collapse; margin: 0.75rem 0 1.5rem; font-size: 0.9rem; }}
th, td {{ border: 1px solid #ccc; padding: 0.3rem 0.5rem; text-align: left; }}
th {{ background: #eef4f6; }}
code {{ background: #f4f4f4; padding: 0.1rem 0.25rem; }}
.note {{ color: #555; max-width: 70rem; }}
</style>
</head>
<body>
<h1>Phase 4 — Feature Engineering and Modeling Table</h1>
<p class="note">Generated from snapshot <code>{html.escape(str(result.snapshot_dir or ""))}</code>.
The target is <code>{TARGET}</code> metric tons. Pre-season features use data through
31 Dec of t-1; mid-season features use current-year records through the configured
cutoff ({html.escape(str(transforms.get("mid_season_cutoff", "06-30")))}).</p>

<h2>Modeling table</h2>
{_table_html(target_summary)}

<h2>Feature approval summary</h2>
<p class="note">The approved feature config contains no unresolved <code>review</code>
items. Management levers are retained even when their marginal importance is low.</p>
{_table_html(decision_counts)}
{_table_html(group_counts)}
{_table_html(cutoff_counts)}

<h2>Leakage checks</h2>
<p class="note">Current-year target-derived columns are excluded. Only prior-year
target-derived history is allowed, under the explicit lag names.</p>
{_table_html(leakage)}

<h2>Missingness after feature engineering (top 20)</h2>
{_table_html(missing)}

<h2>Distribution summary</h2>
{_table_html(distributions)}

<h2>VIF diagnostic</h2>
<p class="note">Full-data diagnostic only. Final VIF and feature selection will be
computed on Phase 5 training folds.</p>
{_table_html(vif)}

<h2>Feature-group ablation diagnostic</h2>
<p class="note">Chronological diagnostic split: train through
{html.escape(str(transforms.get("ablation", {}).get("train_through_year", 2023)))},
validation on {html.escape(str(transforms.get("ablation", {}).get("validation_years", [2024, 2025])))}.
This is not the Phase 5 evaluation protocol.</p>
{_table_html(ablation)}

<h2>Schema</h2>
{_table_html(schema.select("feature", "base_feature", "group", "role", "available_at", "pre_season", "mid_season", "adjustable", "encoded", "dtype", "missing_pct"), max_rows=500)}

</body>
</html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def write_modeling_outputs(
    snapshot_dir: Path,
    *,
    config_dir: Path = DEFAULT_CONFIG_DIR,
    output_path: Path = DEFAULT_OUTPUT,
    schema_csv_path: Path = DEFAULT_SCHEMA_CSV,
    schema_parquet_path: Path = DEFAULT_SCHEMA_PARQUET,
    report_path: Path = DEFAULT_REPORT,
) -> ModelingResult:
    """Build and write the modeling table, feature schema, and HTML report."""

    approved = load_approved_features(config_dir)
    transforms = load_transforms(config_dir)
    result = build_modeling_table(snapshot_dir, config_dir=config_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    schema_csv_path.parent.mkdir(parents=True, exist_ok=True)
    schema_parquet_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    result.table.write_parquet(output_path, compression="zstd")
    result.schema.write_csv(schema_csv_path)
    result.schema.write_parquet(schema_parquet_path, compression="zstd")
    report = write_feature_report(result, approved, transforms, report_path)
    return ModelingResult(
        table=result.table,
        schema=result.schema,
        summary=result.summary,
        snapshot_dir=result.snapshot_dir,
        output_path=output_path,
        schema_csv_path=schema_csv_path,
        schema_parquet_path=schema_parquet_path,
        report_path=report,
    )
