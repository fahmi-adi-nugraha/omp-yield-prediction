# OMP Yield Prediction

Data cleaning, feature engineering, model training, forecasting, and ONNX export
for OMP oil palm yield prediction.

**Current phase:** Phase 0 complete — read-only database access verified.
Next: Phase 1 — database inventory and data dictionary.

## Phase status

| Phase | Status |
|---|---|
| Phase -1 — agent/CLI/MCP harness | Complete |
| Phase 0 — read-only database access | Complete |
| Phase 1 — database inventory and data dictionary | Next |

## Quickstart

```bash
uv sync
uv run omp-yield --version
uv run omp-yield db ping
uv run omp-yield db tables
uv run omp-yield db schema --table OILPALM
uv run omp-yield db query "SELECT TOP 5 NAME, UNIT, BLOCK, YEAR, Y_TOTAL_ton FROM OILPALM"
```

Credential resolution order:

1. `OMP_ENV_FILE`
2. project `.env`
3. `~/.config/omp-yield/env`
4. `docker-build/.env` (local demo fallback only)

Recommended local setup:

```bash
mkdir -p ~/.config/omp-yield
cp .env.example ~/.config/omp-yield/env
chmod 600 ~/.config/omp-yield/env
# edit ~/.config/omp-yield/env with the omp_ds_readonly credentials
```

Keep the password file outside the Syncthing-synced project tree where possible.

## Agent setup

- `.opencode/agents/data-science.md` — primary data-science build agent.
- `.opencode/agents/ds-reviewer.md` — read-only review subagent.
- `.opencode/skills/omp-db-access/SKILL.md` — schema map, joins, safety.
- `.opencode/skills/omp-data-profiling/SKILL.md` — cleaning/leakage/lever audit.
- `opencode.jsonc` — default agent and the `omp-yield` MCP server.

The DS agent is primary because this project involves long, iterative sessions
with approval gates. The reviewer subagent is used for independent leakage,
validation, metric, and ONNX audits.

## Database access

Phase 0 created the least-privilege account `omp_ds_readonly` on
`omp_as_demo`:

- `db_datareader`
- `VIEW DEFINITION`
- no `sysadmin`, `db_owner`, `db_datawriter`, DDL, or `EXECUTE`

The pipeline does not use `sa`. `sa` is only for local DB bootstrap.

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
  test_mcp_contract.py
  test_db_integration.py
docs/
  phase_minus_1.md
  create_readonly_user.sql
reports/
  00_access.md
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

See `docs/phase_minus_1.md` for the completed harness, verification output, and
known limitations.

## Phase 0 acceptance

- `omp_ds_readonly` created with `db_datareader` and `VIEW DEFINITION`.
- `db ping` reports login `omp_ds_readonly` and 2,909 `OILPALM` rows.
- 274 tables and 207 `OILPALM` columns are visible.
- Write attempts are rejected.
- Integration tests pass against the read-only account.
- Credentials live in `~/.config/omp-yield/env` (mode `600`), outside the
  project tree.

See `reports/00_access.md` for the access report and
`docs/create_readonly_user.sql` for the idempotent bootstrap script.

## Next phase

Phase 1 — database inventory and data dictionary:

1. Inventory all tables, columns, row counts, keys, and date ranges.
2. Map join keys and measure match rates against `OILPALM`.
3. Capture growth-period definitions and the estate/division hierarchy.
4. Build the data dictionary and ERD.
