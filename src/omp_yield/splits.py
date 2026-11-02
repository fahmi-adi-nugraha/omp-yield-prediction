"""Phase 5 split definitions, data contracts, and evaluation protocol."""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl
import yaml

from omp_yield.cleaning import TARGET, load_snapshot
from omp_yield.features import KEYS, load_transforms

BLOCK_KEYS = ["NAME", "UNIT", "BLOCK"]
DEFAULT_TABLE = Path("data/processed/modeling_table.parquet")
DEFAULT_SCHEMA = Path("data/processed/feature_schema.csv")
DEFAULT_CONFIG = Path("config/evaluation.yaml")
DEFAULT_SPLITS = Path("data/processed/splits.json")
DEFAULT_CONTRACT_REPORT = Path("data/processed/contract_report.csv")
DEFAULT_CONTRACT_DOC = Path("docs/data_contract.md")
METADATA_COLUMNS = {"anomaly_flags", "has_anomaly"}


class SplitError(RuntimeError):
    """Raised when a split definition is invalid or leaks future data."""


class DataContractError(RuntimeError):
    """Raised when the modeling table violates the data contract."""


@dataclass(frozen=True)
class SplitFold:
    """Row-index membership for one train/validation/test fold."""

    name: str
    train_indices: tuple[int, ...]
    validation_indices: tuple[int, ...]
    test_indices: tuple[int, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, frame: pl.DataFrame) -> dict[str, Any]:
        return {
            "name": self.name,
            "train": _membership(frame, self.train_indices),
            "validation": _membership(frame, self.validation_indices),
            "test": _membership(frame, self.test_indices),
            **self.metadata,
        }


@dataclass(frozen=True)
class ContractReport:
    """Data-contract check results."""

    ok: bool
    checks: pl.DataFrame
    summary: dict[str, Any]


def load_evaluation_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    """Load the approved evaluation protocol."""

    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SplitError(f"Invalid evaluation config: {path}")
    if payload.get("status") != "approved":
        raise SplitError("Evaluation config is not approved.")
    return payload


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _hash_indices(indices: Sequence[int]) -> str:
    return _sha256_text(json.dumps(list(indices), separators=(",", ":")))


def _membership(frame: pl.DataFrame, indices: Sequence[int]) -> dict[str, Any]:
    values = tuple(indices)
    if not values:
        return {
            "count": 0,
            "years": [],
            "blocks": 0,
            "row_indices": [],
            "sha256": _hash_indices(()),
        }
    subset = frame[list(values)]
    return {
        "count": len(values),
        "years": sorted(int(year) for year in subset["YEAR"].unique().to_list()),
        "blocks": subset.select(BLOCK_KEYS).unique().height,
        "row_indices": list(values),
        "sha256": _hash_indices(values),
    }


def _indices_for_years(frame: pl.DataFrame, years: Sequence[int]) -> tuple[int, ...]:
    if not years:
        return ()
    selected = set(int(year) for year in years)
    return tuple(
        int(index)
        for index in frame.with_row_index("__row_index")
        .filter(pl.col("YEAR").is_in(list(selected)))["__row_index"]
        .to_list()
    )


def _block_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return tuple(str(row[column]) for column in BLOCK_KEYS)  # type: ignore[return-value]


def _split_from_indices(
    name: str,
    train: Sequence[int],
    validation: Sequence[int],
    test: Sequence[int] = (),
    metadata: dict[str, Any] | None = None,
) -> SplitFold:
    return SplitFold(
        name=name,
        train_indices=tuple(train),
        validation_indices=tuple(validation),
        test_indices=tuple(test),
        metadata=metadata or {},
    )


class ChronologicalSplitter:
    """Chronological train/validation/test split."""

    def split(
        self,
        frame: pl.DataFrame,
        *,
        train_years: Sequence[int],
        validation_years: Sequence[int],
        test_years: Sequence[int],
    ) -> SplitFold:
        _validate_year_sets(train_years, validation_years, test_years)
        return _split_from_indices(
            "chronological",
            _indices_for_years(frame, train_years),
            _indices_for_years(frame, validation_years),
            _indices_for_years(frame, test_years),
            metadata={
                "train_years": sorted(int(year) for year in train_years),
                "validation_years": sorted(int(year) for year in validation_years),
                "test_years": sorted(int(year) for year in test_years),
            },
        )


class GroupShuffleSplitter:
    """Deterministic 80/10/10-style split by block."""

    def __init__(self, *, seed: int = 42) -> None:
        self.seed = seed

    def split(
        self,
        frame: pl.DataFrame,
        *,
        validation_size: float = 0.10,
        test_size: float = 0.10,
    ) -> SplitFold:
        if not (0 < validation_size < 1 and 0 < test_size < 1):
            raise SplitError("Grouped split sizes must be between 0 and 1.")
        if validation_size + test_size >= 1:
            raise SplitError("Grouped split sizes must leave a training portion.")

        blocks = frame.select(BLOCK_KEYS).unique().sort(BLOCK_KEYS).to_dicts()
        random.Random(self.seed).shuffle(blocks)
        n_blocks = len(blocks)
        if n_blocks < 3:
            raise SplitError("At least three blocks are required for a grouped split.")

        n_test = max(1, int(round(n_blocks * test_size)))
        n_validation = max(1, int(round(n_blocks * validation_size)))
        while n_test + n_validation >= n_blocks:
            if n_test >= n_validation and n_test > 1:
                n_test -= 1
            elif n_validation > 1:
                n_validation -= 1
            else:
                break

        test_blocks = {_block_key(row) for row in blocks[:n_test]}
        validation_blocks = {
            _block_key(row) for row in blocks[n_test : n_test + n_validation]
        }
        train_blocks = {
            _block_key(row) for row in blocks[n_test + n_validation :]
        }

        train: list[int] = []
        validation: list[int] = []
        test: list[int] = []
        for row in frame.with_row_index("__row_index").iter_rows(named=True):
            key = _block_key(row)
            index = int(row["__row_index"])
            if key in test_blocks:
                test.append(index)
            elif key in validation_blocks:
                validation.append(index)
            elif key in train_blocks:
                train.append(index)
            else:
                raise SplitError(f"Block was not assigned to a split: {key}")

        return _split_from_indices(
            "grouped_block",
            train,
            validation,
            test,
            metadata={
                "seed": self.seed,
                "block_counts": {
                    "train": len(train_blocks),
                    "validation": len(validation_blocks),
                    "test": len(test_blocks),
                },
            },
        )


class GroupKFoldSplitter:
    """Deterministic grouped K-fold split by block."""

    def __init__(self, *, n_splits: int = 5, seed: int = 42) -> None:
        if n_splits < 2:
            raise SplitError("GroupKFold requires at least two folds.")
        self.n_splits = n_splits
        self.seed = seed

    def split(self, frame: pl.DataFrame) -> list[SplitFold]:
        blocks = frame.select(BLOCK_KEYS).unique().sort(BLOCK_KEYS).to_dicts()
        if len(blocks) < self.n_splits:
            raise SplitError("Not enough blocks for the requested number of folds.")
        random.Random(self.seed).shuffle(blocks)
        fold_blocks = [blocks[index :: self.n_splits] for index in range(self.n_splits)]
        fold_keys = [{_block_key(row) for row in rows} for rows in fold_blocks]

        indices: list[list[int]] = [[] for _ in range(self.n_splits)]
        for row in frame.with_row_index("__row_index").iter_rows(named=True):
            key = _block_key(row)
            index = int(row["__row_index"])
            for fold_index, keys in enumerate(fold_keys):
                if key in keys:
                    indices[fold_index].append(index)
                    break
            else:
                raise SplitError(f"Block was not assigned to a fold: {key}")

        folds = []
        for fold_index, validation in enumerate(indices):
            train = [
                index
                for other_index, values in enumerate(indices)
                if other_index != fold_index
                for index in values
            ]
            folds.append(
                _split_from_indices(
                    f"group_fold_{fold_index}",
                    sorted(train),
                    validation,
                    metadata={
                        "fold": fold_index,
                        "block_counts": {
                            "train": len(blocks) - len(fold_keys[fold_index]),
                            "validation": len(fold_keys[fold_index]),
                        },
                    },
                )
            )
        return folds


class TimeSeriesSplitter:
    """Expanding-window chronological CV folds."""

    def __init__(self, *, n_splits: int = 3) -> None:
        if n_splits < 1:
            raise SplitError("TimeSeriesSplit requires at least one split.")
        self.n_splits = n_splits

    def split(self, frame: pl.DataFrame) -> list[SplitFold]:
        years = sorted(int(year) for year in frame["YEAR"].unique().to_list())
        if len(years) <= self.n_splits:
            raise SplitError("Not enough years for the requested time-series splits.")
        validation_years = years[-self.n_splits :]
        folds = []
        for fold_index, validation_year in enumerate(validation_years):
            train_years = [year for year in years if year < validation_year]
            folds.append(
                _split_from_indices(
                    f"time_series_{fold_index}",
                    _indices_for_years(frame, train_years),
                    _indices_for_years(frame, [validation_year]),
                    metadata={
                        "fold": fold_index,
                        "train_years": train_years,
                        "validation_year": validation_year,
                    },
                )
            )
        return folds


class RollingOriginSplitter:
    """Rolling-origin forecast backtests."""

    def split(
        self,
        frame: pl.DataFrame,
        origins: Sequence[dict[str, Any]],
    ) -> list[SplitFold]:
        folds = []
        for origin in origins:
            train_through = int(origin["train_through"])
            validation_year = int(origin["validation_year"])
            if validation_year <= train_through:
                raise SplitError("Rolling-origin validation must be after train_through.")
            train_indices = _indices_for_years(
                frame, [year for year in frame["YEAR"].unique().to_list() if year <= train_through]
            )
            validation_indices = _indices_for_years(frame, [validation_year])
            folds.append(
                _split_from_indices(
                    f"origin_{train_through}_validate_{validation_year}",
                    train_indices,
                    validation_indices,
                    metadata={
                        "train_through": train_through,
                        "validation_year": validation_year,
                    },
                )
            )
        return folds


def _validate_year_sets(
    train_years: Sequence[int],
    validation_years: Sequence[int],
    test_years: Sequence[int],
) -> None:
    train = set(int(year) for year in train_years)
    validation = set(int(year) for year in validation_years)
    test = set(int(year) for year in test_years)
    if train & validation or train & test or validation & test:
        raise SplitError("Train, validation, and test year sets overlap.")
    if train and validation and max(train) >= min(validation):
        raise SplitError("Training years must precede validation years.")
    if validation and test and max(validation) >= min(test):
        raise SplitError("Validation years must precede test years.")


def _remap_fold(fold: SplitFold, global_train: Sequence[int]) -> SplitFold:
    def remap(indices: Sequence[int]) -> tuple[int, ...]:
        return tuple(global_train[index] for index in indices)

    return SplitFold(
        name=fold.name,
        train_indices=remap(fold.train_indices),
        validation_indices=remap(fold.validation_indices),
        test_indices=(),
        metadata=fold.metadata,
    )


def build_splits(
    frame: pl.DataFrame,
    evaluation: dict[str, Any],
    *,
    table_path: Path | None = None,
    schema_path: Path | None = None,
    config_path: Path | None = None,
) -> dict[str, Any]:
    """Build all primary, grouped, CV, and rolling-origin splits."""

    yield_config = evaluation["yield_prediction"]
    primary_config = yield_config["primary"]
    primary = ChronologicalSplitter().split(
        frame,
        train_years=primary_config["train_years"],
        validation_years=primary_config["validation_years"],
        test_years=primary_config["test_years"],
    )
    covered = (
        set(primary.train_indices)
        | set(primary.validation_indices)
        | set(primary.test_indices)
    )
    if len(covered) != frame.height:
        raise SplitError("Primary split does not cover every modeling row.")

    refit = ChronologicalSplitter().split(
        frame,
        train_years=primary_config.get("final_train_years", primary_config["train_years"]),
        validation_years=[],
        test_years=primary_config.get("final_test_years", primary_config["test_years"]),
    )

    grouped_config = yield_config["grouped"]
    grouped = GroupShuffleSplitter(seed=int(grouped_config.get("seed", evaluation["seed"]))).split(
        frame,
        validation_size=float(grouped_config["validation_size"]),
        test_size=float(grouped_config["test_size"]),
    )
    grouped_covered = (
        set(grouped.train_indices)
        | set(grouped.validation_indices)
        | set(grouped.test_indices)
    )
    if len(grouped_covered) != frame.height:
        raise SplitError("Grouped split does not cover every modeling row.")

    train_frame = frame[list(primary.train_indices)]
    group_folds = [
        _remap_fold(fold, primary.train_indices)
        for fold in GroupKFoldSplitter(
            n_splits=int(yield_config["cv"]["group_kfold_splits"]),
            seed=int(evaluation["seed"]),
        ).split(train_frame)
    ]
    time_folds = [
        _remap_fold(fold, primary.train_indices)
        for fold in TimeSeriesSplitter(
            n_splits=int(yield_config["cv"]["time_series_splits"])
        ).split(train_frame)
    ]
    rolling_origins = RollingOriginSplitter().split(
        frame, evaluation["forecast"]["rolling_origins"]
    )

    table_hash = (
        _sha256_file(table_path)
        if table_path is not None and table_path.is_file()
        else _sha256_text(frame.write_json())
    )
    schema_hash = (
        _sha256_file(schema_path)
        if schema_path is not None and schema_path.is_file()
        else None
    )
    config_hash = (
        _sha256_file(config_path)
        if config_path is not None and config_path.is_file()
        else None
    )

    return {
        "version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "seed": int(evaluation["seed"]),
        "table": {
            "path": str(table_path) if table_path is not None else None,
            "rows": frame.height,
            "sha256": table_hash,
        },
        "feature_schema": {
            "path": str(schema_path) if schema_path is not None else None,
            "sha256": schema_hash,
        },
        "config": {
            "path": str(config_path) if config_path is not None else None,
            "sha256": config_hash,
        },
        "primary": primary.to_dict(frame),
        "refit": refit.to_dict(frame),
        "grouped": grouped.to_dict(frame),
        "cv": {
            "group_kfold": [fold.to_dict(frame) for fold in group_folds],
            "time_series": [fold.to_dict(frame) for fold in time_folds],
        },
        "rolling_origins": [fold.to_dict(frame) for fold in rolling_origins],
        "forecast": {
            "final_train_through": evaluation["forecast"]["final_train_through"],
            "final_train": _membership(
                frame,
                _indices_for_years(
                    frame,
                    [
                        int(year)
                        for year in frame["YEAR"].unique().to_list()
                        if int(year) <= int(evaluation["forecast"]["final_train_through"])
                    ],
                ),
            ),
            "forecast_years": evaluation["forecast"]["forecast_years"],
            "experimental_forecast_years": evaluation["forecast"].get(
                "experimental_forecast_years", []
            ),
        },
        "metrics": evaluation["metrics"],
        "baselines": evaluation["baselines"],
    }


def _check(
    checks: list[dict[str, Any]],
    name: str,
    ok: bool,
    details: str,
    *,
    warning: bool = False,
) -> None:
    status = "warn" if warning else "pass" if ok else "fail"
    checks.append({"check": name, "status": status, "details": details})


def _is_temporal(dtype: pl.DataType) -> bool:
    return str(dtype).startswith(("Datetime", "Date"))


def validate_contract(
    table: pl.DataFrame,
    schema: pl.DataFrame,
    evaluation: dict[str, Any],
    transforms: dict[str, Any],
    *,
    source_tables: dict[str, pl.DataFrame] | None = None,
) -> ContractReport:
    """Validate the modeling table against the Phase 5 data contract."""

    checks: list[dict[str, Any]] = []
    contract = evaluation.get("contract", {})
    feature_columns = [
        column
        for column in table.columns
        if column not in {*KEYS, TARGET, *METADATA_COLUMNS}
    ]
    schema_features = set(schema["feature"].to_list())

    duplicate_keys = table.group_by(KEYS).len().filter(pl.col("len") > 1).height
    _check(checks, "unique business key", duplicate_keys == 0, f"{duplicate_keys} duplicate keys")

    target_present = TARGET in table.columns
    target_nulls = table[TARGET].null_count() if target_present else table.height
    target_min = (
        _as_float(table[TARGET].min())
        if target_present and target_nulls < table.height
        else None
    )
    target_max = (
        _as_float(table[TARGET].max())
        if target_present and target_nulls < table.height
        else None
    )
    target_min_allowed = float(contract.get("target_min", 0.0))
    target_max_allowed = contract.get("target_max")
    target_ok = (
        target_present
        and target_nulls == 0
        and target_min is not None
        and target_min >= target_min_allowed
        and (
            target_max_allowed is None
            or (target_max is not None and target_max <= float(target_max_allowed))
        )
    )
    _check(
        checks,
        "target present, non-null, and within range",
        target_ok,
        f"nulls={target_nulls}, min={target_min}, max={target_max}",
    )

    min_year = int(contract.get("min_year", 2019))
    max_year = int(contract.get("max_year", 2025))
    year_min = _as_int(table["YEAR"].min()) if "YEAR" in table.columns else None
    year_max = _as_int(table["YEAR"].max()) if "YEAR" in table.columns else None
    _check(
        checks,
        "year range",
        year_min is not None and year_max is not None and year_min >= min_year and year_max <= max_year,
        f"min={year_min}, max={year_max}, allowed={min_year}..{max_year}",
    )

    _check(
        checks,
        "feature schema covers every feature column",
        schema_features == set(feature_columns),
        f"schema={len(schema_features)}, table_features={len(feature_columns)}",
    )
    _check(
        checks,
        "feature availability metadata is complete",
        set(schema["available_at"].to_list()) <= {"pre_season", "mid_season"}
        and schema.filter(~pl.col("pre_season") & ~pl.col("mid_season")).height == 0,
        "available_at must be pre_season or mid_season",
    )
    _check(
        checks,
        "no current-year Y_* feature",
        not any(feature.startswith("Y_") for feature in feature_columns),
        "target-derived current-year columns must not be features",
    )
    all_null = [feature for feature in feature_columns if table[feature].null_count() == table.height]
    _check(checks, "no all-null feature columns", not all_null, ", ".join(all_null) or "none")
    _check(
        checks,
        "target is not a feature",
        TARGET not in feature_columns,
        "target column excluded from feature list",
    )

    for feature, bounds in contract.get("bounds", {}).items():
        if feature not in table.columns:
            _check(checks, f"bounds {feature}", False, "feature missing from modeling table")
            continue
        series = table[feature].cast(pl.Float64)
        minimum = series.min()
        maximum = series.max()
        lower = bounds.get("min")
        upper = bounds.get("max")
        ok = (
            (lower is None or (minimum is not None and float(minimum) >= float(lower)))
            and (upper is None or (maximum is not None and float(maximum) <= float(upper)))
        )
        _check(
            checks,
            f"bounds {feature}",
            ok,
            f"min={minimum}, max={maximum}, allowed={lower}..{upper}",
        )

    for feature, domain in contract.get("ordinal_domains", {}).items():
        if feature not in table.columns:
            _check(checks, f"domain {feature}", False, "feature missing from modeling table")
            continue
        values = table[feature].drop_nulls().unique().to_list()
        unexpected = [value for value in values if value not in domain]
        _check(
            checks,
            f"domain {feature}",
            not unexpected,
            f"values={values}, unexpected={unexpected}",
        )

    one_hot_sources = transforms.get("categorical", {}).get("one_hot", {})
    for source in one_hot_sources:
        columns = [
            feature
            for feature in schema.filter(pl.col("base_feature") == source)["feature"].to_list()
            if feature in table.columns
        ]
        bad = []
        for column in columns:
            values = table[column].drop_nulls().unique().to_list()
            if any(value not in (0, 1) for value in values):
                bad.append(column)
        _check(
            checks,
            f"one-hot binary values {source}",
            not bad,
            ", ".join(bad) or "all binary",
        )

    binary_columns = [
        "pre_marker_fert_known",
        "pre_marker_fert_has_urea",
        "pre_marker_fert_has_kcl",
        "pre_marker_fert_has_rp",
        "pre_marker_fert_has_kieserite",
        "pre_marker_fert_has_borate",
        "pre_marker_fert_has_efb",
        "pre_marker_fert_has_compound",
        "pre_pruning_known",
        "pre_harvester_access_known",
    ]
    bad_binary = [
        column
        for column in binary_columns
        if column in table.columns
        and any(value not in (0, 1) for value in table[column].drop_nulls().unique().to_list())
    ]
    _check(checks, "binary indicator values", not bad_binary, ", ".join(bad_binary) or "all binary")

    if source_tables and "OILPALM" in source_tables:
        oilpalm = source_tables["OILPALM"]
        date_columns = [column for column in ("D_PLANTED", "LA_DATE") if column in oilpalm.columns]
        bad_dates = [column for column in date_columns if not _is_temporal(oilpalm.schema[column])]
        _check(
            checks,
            "source dates parseable",
            not bad_dates,
            ", ".join(bad_dates) or "D_PLANTED and LA_DATE are temporal",
        )
        if "Growth_Period" in oilpalm.columns:
            allowed = set(contract.get("allowed_growth_periods", []))
            modeled_periods = (
                table.select(KEYS)
                .join(
                    oilpalm.select([*KEYS, "Growth_Period"]),
                    on=KEYS,
                    how="left",
                )["Growth_Period"]
                .drop_nulls()
                .unique()
                .to_list()
            )
            observed = set(modeled_periods)
            _check(
                checks,
                "growth-period domain in modeling rows",
                observed <= allowed,
                f"observed={sorted(observed)}, allowed={sorted(allowed)}",
            )
        for column, config_key in (
            ("Pruning", "allowed_pruning"),
            ("HarvesterAccess", "allowed_harvester_access"),
        ):
            if column not in oilpalm.columns:
                continue
            allowed = set(contract.get(config_key, []))
            observed = set(oilpalm[column].drop_nulls().unique().to_list())
            unexpected_values = observed - allowed - {"", "No data"}
            _check(
                checks,
                f"source category domain {column}",
                not unexpected_values,
                f"unexpected={sorted(unexpected_values)}",
            )
    else:
        _check(
            checks,
            "source date parsing",
            True,
            "skipped: source tables not supplied",
            warning=True,
        )

    checks_frame = pl.DataFrame(checks)
    failures = int(checks_frame.filter(pl.col("status") == "fail").height)
    warnings = int(checks_frame.filter(pl.col("status") == "warn").height)
    return ContractReport(
        ok=failures == 0,
        checks=checks_frame,
        summary={
            "rows": table.height,
            "feature_columns": len(feature_columns),
            "schema_features": schema.height,
            "checks": checks_frame.height,
            "failures": failures,
            "warnings": warnings,
        },
    )


def _md_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(lines)


def write_contract_report(report: ContractReport, path: Path = DEFAULT_CONTRACT_REPORT) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    report.checks.write_csv(path)
    return path


def write_data_contract_doc(
    table: pl.DataFrame,
    schema: pl.DataFrame,
    report: ContractReport,
    evaluation: dict[str, Any],
    path: Path = DEFAULT_CONTRACT_DOC,
) -> Path:
    """Write the data-contract reference document."""

    bounds_rows = []
    for feature, bounds in evaluation.get("contract", {}).get("bounds", {}).items():
        if feature in table.columns:
            series = table[feature].cast(pl.Float64)
            bounds_rows.append(
                [
                    f"`{feature}`",
                    bounds.get("min"),
                    bounds.get("max"),
                    series.min(),
                    series.max(),
                ]
            )
    schema_rows = [
        [
            f"`{row['feature']}`",
            f"`{row['base_feature']}`",
            row["group"],
            row["available_at"],
            row["dtype"],
            row["missing_pct"],
        ]
        for row in schema.select(
            "feature", "base_feature", "group", "available_at", "dtype", "missing_pct"
        ).iter_rows(named=True)
    ]
    contract_rows = [
        [row["check"], row["status"], row["details"]]
        for row in report.checks.iter_rows(named=True)
    ]
    target = table[TARGET].cast(pl.Float64)
    target_min = _as_float(target.min())
    target_max = _as_float(target.max())
    doc = f"""# Data Contract — OMP Yield Modeling

Status: **generated from the Phase 4 modeling table**

Generated at: `{datetime.now(UTC).isoformat()}`

## Table

| Property | Value |
|---|---|
| Rows | {table.height:,} |
| Feature columns | {report.summary["feature_columns"]} |
| Schema features | {report.summary["schema_features"]} |
| Target | `{TARGET}` metric tons |
| Keys | `NAME`, `UNIT`, `BLOCK`, `YEAR` |
| Target min / max | {target_min} / {target_max} |

## Key and target rules

- The business key `(NAME, UNIT, BLOCK, YEAR)` must be unique.
- The target must be non-null and non-negative.
- Rows must stay inside the mature 2019–2025 modeling range.
- The target is never a feature.
- Current-year target-derived `Y_*` columns are excluded.

## Numeric bounds

{_md_table(["Feature", "Configured min", "Configured max", "Observed min", "Observed max"], bounds_rows)}

`pre_mature_fraction` may exceed 1.0 slightly because of the known mature-stand
greater-than-total-stand data-quality cases; it is flagged, not dropped.

## Categorical domains

- Mature `Growth_Period`: `SAYP`, `PYP`, `DYP`.
- `HarvesterAccess`: `None`, `Incomplete`, `Full`, plus missing/`No data`.
- `Pruning`: `Correct`, `Neglected`, `Over`, `Under`, plus missing/`No data`.
- One-hot families follow `config/transforms.yaml`; all encoded one-hot
  indicators must be binary.

## Feature availability

Every feature in `data/processed/feature_schema.csv` must have an
`available_at` of `pre_season` or `mid_season`, and the `pre_season` /
`mid_season` flags must identify its view. The mid-season view is
`pre_season + mid_season`.

## Missingness

Nulls are retained. Missing numeric values are allowed and must be handled by
the model-specific pipeline. No feature may be entirely null.

## Anomaly flags

`anomaly_flags` and `has_anomaly` mark the known `124H` 2024/2025 area anomaly
and the `204D` 2025 zero-yield anomaly. These rows remain in the modeling table;
Phase 5/6 must decide whether `204D` 2025 is excluded from training.

## Contract checks

{_md_table(["Check", "Status", "Details"], contract_rows)}

## Feature schema

{_md_table(["Feature", "Base feature", "Group", "Available at", "Dtype", "Missing %"], schema_rows)}
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(doc, encoding="utf-8")
    return path


def write_splits_outputs(
    *,
    table_path: Path = DEFAULT_TABLE,
    schema_path: Path = DEFAULT_SCHEMA,
    config_path: Path = DEFAULT_CONFIG,
    splits_path: Path = DEFAULT_SPLITS,
    contract_report_path: Path = DEFAULT_CONTRACT_REPORT,
    contract_doc_path: Path = DEFAULT_CONTRACT_DOC,
    snapshot_dir: Path | None = None,
) -> dict[str, Any]:
    """Validate the contract, build splits, and write all Phase 5 artifacts."""

    table = pl.read_parquet(table_path)
    schema = pl.read_csv(schema_path)
    evaluation = load_evaluation_config(config_path)
    transforms = load_transforms(config_path.parent)
    source_tables = None
    if snapshot_dir is not None:
        source_tables = load_snapshot(snapshot_dir, verify=True).tables

    report = validate_contract(
        table,
        schema,
        evaluation,
        transforms,
        source_tables=source_tables,
    )
    report_path = write_contract_report(report, contract_report_path)
    doc_path = write_data_contract_doc(table, schema, report, evaluation, contract_doc_path)
    if not report.ok:
        failures = report.checks.filter(pl.col("status") == "fail")["check"].to_list()
        raise DataContractError(
            "Data contract failed: " + ", ".join(str(item) for item in failures)
        )

    splits = build_splits(
        table,
        evaluation,
        table_path=table_path,
        schema_path=schema_path,
        config_path=config_path,
    )
    splits_path.parent.mkdir(parents=True, exist_ok=True)
    splits_path.write_text(json.dumps(splits, indent=2), encoding="utf-8")
    return {
        "splits": splits,
        "splits_path": splits_path,
        "contract_report": report,
        "contract_report_path": report_path,
        "contract_doc_path": doc_path,
    }
