# Phase 12 — Freeze, Release, and Handover

Status: **planned**

## Overview

Freeze the approved pipeline and produce a reproducible release that another
engineer or LLM can rerun and audit.

## Goals and deliverables

- Frozen `config/features.yaml`, `config/transforms.yaml`,
  `config/management_levers.yaml`, `config/model.yaml`, and
  `config/evaluation.yaml`.
- Frozen environment (`uv.lock`), data snapshot ID, config hashes, and git tag.
- `models/<run_id>/` with ONNX, schemas, metrics, and model card.
- `reports/reproducibility.md` — exact commands, checksums, and expected metrics.
- Release notes and handover notes in `docs/phase-12-freeze/`.
- Optional local MLflow run IDs.

## Technical details

- Re-run the full pipeline from the frozen snapshot in a clean environment.
- Verify ONNX parity and snapshot checksums.
- Compare metrics to the frozen release within an agreed tolerance.
- Record:
  - Python/uv version
  - git commit/tag
  - snapshot ID and manifest SHA256
  - config hashes
  - feature count and model family
  - metrics and confidence intervals
- Archive model card, feature schema, lever schema, and inference example.
- Define retraining cadence and drift triggers; annual post-harvest retraining is
  the default.

## Locations

- `models/<run_id>/`
- `config/`
- `docs/phase-12-freeze/`
- `reports/reproducibility.md`
- `reports/model_card.md`

## Verification

- Independent rerun reproduces the artifacts and metrics within tolerance.
- Model card and runbook are complete.
- User signs off on the frozen release.
- No uncommitted changes remain in the release commit.

## Ongoing operations

After release:

- Monitor feature and prediction drift.
- Compare forecasts to actuals when harvest data arrives.
- Retrain after each harvest or when drift/error thresholds are exceeded.
- Never silently change the feature list or target; create a new plan phase and
  approval record.
