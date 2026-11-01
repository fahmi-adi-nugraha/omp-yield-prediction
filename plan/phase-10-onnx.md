# Phase 10 — ONNX Export and Parity

Status: **planned**

## Overview

Export the complete preprocessing + model pipeline to ONNX so the separate Go
REST API can load it without reimplementing scikit-learn preprocessing.

## Goals and deliverables

- `src/omp_yield/export_onnx.py`.
- `models/<run_id>/model.onnx`.
- `feature_schema.json`, `target_schema.json`, `scenario_schema.json`.
- `metrics.json`, `model_card.md`, and ONNX parity report.
- `tests/test_onnx_parity.py`.
- `docs/phase-10-onnx/README.md`.

## Technical details

- Use `skl2onnx` to convert the full `Pipeline`:
  imputer → scaler/encoder → `HistGradientBoostingRegressor`.
- `skl2onnx` supports HGB, `ColumnTransformer`, `OneHotEncoder`,
  `SimpleImputer`, and `StandardScaler`.
- Avoid `TransformedTargetRegressor`; if a log target is used, add an explicit
  inverse-transform node and test it.
- Use opset 17+ and validate with `onnxruntime`.
- Parity tolerance: maximum absolute difference < `1e-5` on a holdout sample.
- Forecast: export one model per horizon or one model with a `horizon` input;
  test both before choosing.
- Save the exact feature order, dtypes, categories, and missing handling in the
  schema files.

## Locations

- `src/omp_yield/export_onnx.py` (planned)
- `models/<run_id>/` (gitignored)
- `tests/test_onnx_parity.py`
- `docs/phase-10-onnx/`

## Verification

- ONNX loads in `onnxruntime`.
- Predictions match scikit-learn within tolerance.
- Categorical encoding and missing values behave correctly.
- Inference example runs from a raw feature dictionary.

## Next

Phase 11 — packaging, reproducibility, and operations.
