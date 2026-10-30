# OMP Yield Prediction

Data cleaning, feature engineering, model training, forecasting, and ONNX export
for OMP oil palm yield prediction.

**Current phase:** Phase -1 — agent/CLI/MCP harness.

## Quickstart

```bash
uv sync
uv run omp-yield --version
uv run omp-yield db ping
uv run omp-yield db tables
uv run omp-yield db schema --table OILPALM
uv run omp-yield db query "SELECT TOP 5 NAME, UNIT, BLOCK, YEAR, Y_TOTAL_ton FROM OILPALM"
```

For local development the CLI falls back to `docker-build/.env` when `.env`
does not exist. Production should use a read-only account and environment
variables.

```bash
cp .env.example .env
# edit .env with the omp_ds_readonly credentials created in Phase 0
```

## Agent setup

- `.opencode/agents/data-science.md` — primary data-science build agent.
- `.opencode/agents/ds-reviewer.md` — read-only review subagent.
- `.opencode/skills/omp-db-access/SKILL.md` — schema map, joins, safety.
- `.opencode/skills/omp-data-profiling/SKILL.md` — cleaning/leakage/lever audit.
- `opencode.jsonc` — default agent and the `omp-yield` MCP server.

The DS agent is primary because this project involves long, iterative sessions
with approval gates. The reviewer subagent is used for independent leakage,
validation, metric, and ONNX audits.

## MCP tools

The local server exposes:

- `db_ping` — connectivity and `OILPALM` row count.
- `db_tables` — user tables.
- `db_schema` — column metadata, optionally by table.
- `db_query` — one read-only `SELECT`/`WITH` query with a row limit.

Tools are thin wrappers around `src/omp_yield/db.py`; the CLI is the source of
truth.

## Project structure

```text
src/omp_yield/
  config.py      # env settings and connection URL
  db.py          # read-only ConnectorX/Polars client
  sql.py         # read-only SQL guard
  cli.py         # omp-yield CLI
  mcp_server.py  # local MCP wrapper
tests/
  test_sql.py
  test_config.py
  test_cli.py
.opencode/
  agents/
  skills/
```

## Phase -1 acceptance

- `uv run omp-yield db ping` returns the database identity and `OILPALM`
  row count.
- `uv run omp-yield db schema --table OILPALM` returns column metadata.
- `uv run omp-yield db query ...` enforces read-only SQL and row limits.
- The MCP server starts and exposes the same read-only tools.
- Tests pass.

## Phase -1 report

See `docs/phase_minus_1.md` for the completed harness, verification output, and
known limitations.

## Next phase

Phase 0 — create `omp_ds_readonly`, verify minimum-privilege access, and run the
project scaffold checks against the demo database.
