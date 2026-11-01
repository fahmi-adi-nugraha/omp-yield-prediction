# Phase 7 — Hyperparameter Search

Status: **planned**

## Overview

Tune the approved model family with reproducible random search, logging every
trial and its errors. Keep MLflow optional and local.

## Goals and deliverables

- `src/omp_yield/tuning.py` — random-search runner and trial logger.
- `config/tuning.yaml` — search spaces, iteration budget, CV strategy, seed.
- `runs/tuning.jsonl` / `runs/tuning.parquet` — every trial.
- `reports/07_tuning_report.html` — best params, score distributions, learning
  curves, and stability.
- `config/model.yaml` — selected hyperparameters.
- `docs/phase-7-hyperparameter-search/README.md`.

## Technical details

- Use `RandomizedSearchCV` or an equivalent loop with 50–100 trials.
- Scoring: negative RMSE for yield; MASE/RMSE for forecast.
- CV: `GroupKFold` by block inside training; temporal validation for the final
  decision.
- Log per trial: trial ID, model, params, fold, train/validation errors, fit
  time, feature count, seed, and status.
- HGB search space: `learning_rate`, `max_iter`, `max_leaf_nodes`,
  `min_samples_leaf`, `l2_regularization`, `max_bins`, early stopping.
- RF/ET: `n_estimators`, `max_depth`, `min_samples_leaf`, `max_features`,
  `bootstrap`.
- Ridge/ElasticNet: `alpha` log-uniform, `l1_ratio`.
- Optional LightGBM: `num_leaves`, `learning_rate`, `n_estimators`,
  `min_child_samples`, `subsample`, `colsample_bytree`, regularization.
- MLflow: `--mlflow` or `MLFLOW_TRACKING_URI=file:./mlruns`; if absent, local
  JSONL is the source of truth.
- Never evaluate the test set during search.

## Locations

- `src/omp_yield/tuning.py` (planned)
- `config/tuning.yaml`, `config/model.yaml` (planned)
- `runs/tuning.jsonl` (gitignored)
- `reports/07_tuning_report.html`
- `docs/phase-7-hyperparameter-search/`

## Verification

- Best params reproducible with a fixed seed.
- Every trial has a complete log entry.
- Tuning report shows train vs validation gap and stability across folds.
- Test set untouched.

## Next

Phase 8 — final training and evaluation.
