# Phase 11 — Packaging, Reproducibility, and Operations

Status: **planned**

## Overview

Make the pipeline reproducible and operable: CLI, config, logging, tests, CI,
optional Docker, local MLflow, documentation, and monitoring. The Go REST API is
a separate deployment component and is not implemented here.

## Goals and deliverables

- Stable CLI commands: `db`, `inventory`, `extract`, `verify-snapshot`, `clean`,
  `train`, `forecast`, `explain`, `export-onnx`, `all`.
- Config-driven runs with Pydantic settings and YAML.
- Structured logging, run IDs, retries, query timeouts, schema-drift detection.
- Tests: unit, leakage, split integrity, ONNX parity, pipeline smoke test.
- CI: `ruff`, `mypy`, `pytest`, smoke pipeline, Docker build.
- Optional `Dockerfile` for the Python pipeline; no serving API.
- Local MLflow: `MLFLOW_TRACKING_URI=file:./mlruns`.
- `docs/runbook.md`, updated README/docs/model card.
- Monitoring plan: feature drift, prediction drift, actual-vs-predicted error,
  retraining triggers.

## Technical details

- Pin dependencies with `uv.lock`; Python 3.12.
- Keep raw data immutable; derived data under `data/interim`/`data/processed`.
- Never commit credentials or raw snapshots.
- Log data snapshot hash, config hash, git commit, feature list, and metrics.
- Docker image should run as non-root and expose the CLI, not an HTTP server.
- Optional orchestration: cron or GitHub Actions first; Prefect/Dagster/Airflow
  only if needed.
- The separate Go REST API consumes the ONNX artifacts; its deployment is out of
  scope for this repository.

## Locations

- `src/omp_yield/cli.py` and pipeline modules
- `Dockerfile` (planned)
- `.github/workflows/` or equivalent CI (planned)
- `docs/runbook.md`, `reports/model_card.md`
- `mlruns/` (local, gitignored)

## Verification

- Fresh clone + `uv sync` reproduces tests and reports.
- CI is green.
- Docker image runs the CLI against a mounted config/data directory.
- No secrets or raw data are committed.

## Next

Phase 12 — freeze, release, and handover.
