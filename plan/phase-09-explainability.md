# Phase 9 — Explainability and What-If

Status: **planned**

## Overview

Explain global model behavior and provide a local what-if simulator that varies
one approved management lever at a time while holding other features at a
reference row.

## Goals and deliverables

- `src/omp_yield/explain.py` — prediction, SHAP/PDP/ICE, lever simulation.
- `config/management_levers.yaml` — approved lever list and ranges.
- `reports/09_explainability.html` — global and local explanations, lever
  sensitivity, and stability checks.
- `docs/phase-9-explainability/README.md`.
- Optional companion Ridge/ElasticNet model for interpretable marginal effects.

## Technical details

- Global: permutation importance, SHAP summary/bar, PDP/ICE.
- Local: for a block-year, vary one lever across an observed/agronomic grid;
  hold all other features at that row or a documented reference.
- Output: predicted total tons, tons/ha, delta, percent delta, observed-range
  percentile, and extrapolation flag.
- Accept only levers with `adjustable: true`; context features are read-only.
- Clip to observed 5th–95th percentile or approved agronomic bounds.
- Check direction, magnitude, monotonicity, and stability across the two cutoffs.
- State clearly that what-if output is model-implied association, not causal
  proof. For high-stakes decisions, use domain review or causal methods.

## Locations

- `src/omp_yield/explain.py` (planned)
- `config/management_levers.yaml`
- `reports/09_explainability.html`
- `docs/phase-9-explainability/`

## Verification

- Non-lever features are rejected by the simulator.
- Extrapolation flags are present.
- Lever effects are plausible to domain reviewers.
- No target-derived feature enters the explanation input.

## Next

Phase 10 — ONNX export and parity.
