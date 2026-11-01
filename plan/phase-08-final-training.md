# Phase 8 — Final Training and Evaluation

Status: **planned**

## Overview

Refit the selected models on training + validation data, evaluate once on the
held-out test set, validate forecast backtests, and produce the model card.

## Goals and deliverables

- Fitted `pre_season` and `mid_season` yield models.
- Fitted forecast model(s) for 1–3 years; optional experimental 4–5 years.
- `models/<run_id>/` with serialized model, feature schema, metrics, and model
  card inputs.
- `reports/08_final_evaluation.html` — test metrics, residuals, calibration,
  error by segment, forecast backtest, and scenario comparison.
- `reports/model_card.md` — intended use, training data, features, performance,
  limitations, retraining, and what-if caveats.
- `docs/phase-8-final-training/README.md`.

## Technical details

- Refit on 2019–2024 for yield; keep 2025 as the once-only test.
- For forecast, refit on ≤2024 and forecast 2026–2028; optional 2029–2030 with
  explicit extended-horizon warnings.
- Report bootstrap confidence intervals and prediction intervals.
- Evaluate at block level and aggregate estate level.
- Report MAE/RMSE/MAPE/sMAPE/R²/bias; forecast MASE and interval coverage.
- Compare forecast to naive, 3-year average, linear trend, and company budget.
- Document the `204D` 2025 exclusion/correction decision.
- Model card must state that what-if effects are model associations, not proven
  causal effects.

## Locations

- `models/<run_id>/` (gitignored)
- `reports/08_final_evaluation.html`
- `reports/model_card.md`
- `docs/phase-8-final-training/`
- `reports/README.md`

## Verification

- Test set used once; no tuning after test evaluation.
- Metrics meet the agreed provisional thresholds or are explicitly re-baselined.
- Forecast intervals widen with horizon and scenario uncertainty.
- Model card reviewed and approved.

## Next

Phase 9 — explainability and what-if.
