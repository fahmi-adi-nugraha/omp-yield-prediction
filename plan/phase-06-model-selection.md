# Phase 6 — Model Selection

Status: **planned**

## Overview

Compare candidate models on the approved modeling table using the Phase 5
validation protocol. Select the primary yield models and the forecast
architecture with evidence from validation only.

## Goals and deliverables

- `src/omp_yield/modeling.py` or `train.py` — estimator definitions and
  evaluation helpers.
- `config/model_selection.yaml` — candidate model grid and metrics.
- `reports/06_model_selection.html` — model comparison, learning curves,
  residual diagnostics, feature importance, and recommendation.
- `docs/phase-6-model-selection/README.md`.
- Optional local experiment records under `runs/` (JSONL/Parquet).

## Candidate models

| Model | Strengths | Weaknesses | Role |
|---|---|---|---|
| Ridge / ElasticNet | Interpretable, stable, fast, ONNX-friendly | Linear/additive; needs encoding/scaling | Baseline and glass-box companion |
| Random Forest | Non-linear, robust, ONNX-friendly | Poor extrapolation; biased importance; large | Benchmark |
| ExtraTrees | Faster variance reduction | Similar extrapolation issues | Benchmark |
| `HistGradientBoostingRegressor` | Strong tabular performance, native NaN, ONNX support | Tuning, extrapolation, less interpretable | Primary candidate |
| LightGBM | Strong tabular performance, categorical support, SHAP | Extra dependency and ONNX complexity | Optional challenger |
| Tweedie/Gamma GLM | Handles positive/skewed targets | Linear structure | Alternative diagnostic |

## Technical details

Yield models:

- Train separate `pre_season` and `mid_season` configurations.
- Use `GroupKFold` by block inside training; temporal validation for the
  decision metric.
- Evaluate RMSE, MAE, MAPE/sMAPE, R², bias, and error by year/division/age band.
- Inspect residuals, learning curves, permutation importance, PDP/ICE, and
  SHAP where supported.
- Keep management levers in all candidate models even if marginal importance is
  low.

Forecast models:

- Train at block level and aggregate to `UNIT`, then `NAME`.
- Compare direct multi-horizon models (`horizon` feature or one model per
  horizon), direct division-level models, and estate-level naive/trend
  baselines.
- Compare unconditional and scenario-conditional variants.
- Backtest with rolling origins and report estate-level metrics.

## Locations

- `src/omp_yield/modeling.py` / `train.py` (planned)
- `config/model_selection.yaml` (planned)
- `reports/06_model_selection.html`
- `docs/phase-6-model-selection/`
- `runs/` (optional local logs, gitignored)

## Verification

- Candidate comparison uses validation/CV only.
- Test set is not touched.
- Recommendation includes predictive metrics and domain plausibility.
- User approves the model family and target definition before Phase 7.

## Next

Phase 7 — hyperparameter search.
