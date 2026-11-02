# Phase -1 — Agent and Tooling Harness

Status: **complete**

## What was created

### Project scaffold

- `pyproject.toml`, `uv.lock`, `.python-version` (Python 3.12)
- `src/omp_yield/` package with:
  - `config.py` — environment settings and MSSQL connection URL
  - `db.py` — read-only ConnectorX/Polars client
  - `sql.py` — single-statement read-only SQL guard
  - `cli.py` — `omp-yield` CLI
  - `mcp_server.py` — local MCP server
- `tests/` — SQL guard, settings, and CLI tests
- `.env.example`, `.gitignore`, `README.md`

### Agent and skills

- `.opencode/agents/data-science.md` — primary DS build agent
- `.opencode/agents/ds-reviewer.md` — read-only review subagent
- `.opencode/skills/omp-db-access/SKILL.md` — schema map, joins, safety
- `.opencode/skills/omp-data-profiling/SKILL.md` — cleaning/leakage/lever audit
- `opencode.jsonc` — default agent and `omp-yield` MCP server

### Read-only database tools

CLI:

```bash
uv run omp-yield db ping
uv run omp-yield db tables
uv run omp-yield db schema --table OILPALM
uv run omp-yield db query "SELECT TOP 5 ... FROM OILPALM"
```

MCP tools:

- `db_ping`
- `db_tables`
- `db_schema`
- `db_query`

### Demo database lifecycle tools

The MCP server also exposes scoped Docker Compose lifecycle tools for the
local `docker-build/` stack:

- `demo_db_status`
- `demo_db_logs`
- `demo_db_build`
- `demo_db_up`
- `demo_db_stop`
- `demo_db_start`
- `demo_db_restart`
- `demo_db_down`

Matching CLI commands:

```bash
uv run omp-yield demo-db status
uv run omp-yield demo-db build [--force]
uv run omp-yield demo-db up [--recreate]
uv run omp-yield demo-db logs [--tail 100]
uv run omp-yield demo-db stop
uv run omp-yield demo-db start
uv run omp-yield demo-db restart
uv run omp-yield demo-db down [--remove-volumes]
```

Safety rules:

- Every command is scoped to the `docker-build` Compose project.
- `down` without `--remove-volumes` preserves the database volume.
- `down --remove-volumes` is destructive; the next `up` performs a full
  restore from the `.bak` file.
- Mutating tools can be disabled with
  `OMP_MCP_ALLOW_DOCKER_MUTATIONS=0`.
- The tools operate on the active Docker context and require Docker socket
  access from the MCP server process.

`up` returns immediately after the container starts. Use `demo_db_logs` to
watch the restore and `db_ping` to confirm database readiness.

## Verification performed

### Connectivity

```text
database_name: omp_as_demo
login_name: sa
server_version: Microsoft SQL Server 2025 (RTM-CU6) 17.0.4055.5
oilpalm_rows: 2909
```

`sa` is used only for local bootstrap. Phase 0 creates `omp_ds_readonly`.

### Read-only guard

```text
$ uv run omp-yield db query "DELETE FROM OILPALM"
Error: Only SELECT and WITH queries are allowed.
exit=1
```

### Tests

```text
$ uv run pytest
17 passed, 2 skipped

$ OMP_RUN_INTEGRATION=1 uv run pytest tests/test_db_integration.py
2 passed

$ uv run ruff check .
All checks passed!

$ uv run mypy src tests
Success: no issues found in 11 source files
```

### MCP server

The local MCP server was started over stdio and queried with an MCP client:

```text
tools: ['db_ping', 'db_tables', 'db_schema', 'db_query']
db_ping: ok=True, oilpalm_rows=2909
db_schema('OILPALM'): 207 columns
```

OpenCode connects to it successfully:

```text
$ opencode mcp list
✓ omp-yield  connected
```

## Known Phase -1 limitations

- The client-side row limit fetches the result and truncates it in Polars. This
  is acceptable for the current tables; a server-side or cursor-based limit can
  be added later for large extracts.
- No retry/backoff yet. DB connection errors are surfaced with context.
- The MCP server has no authentication because it is a local stdio server. The
  DB account itself must be read-only.
- Local development falls back to `~/.config/omp-yield/env`, then
  `docker-build/.env` when no project `.env` exists. Production should use
  environment variables or a managed secret store.
- `sa` was the local account during Phase -1; Phase 0 created
  `omp_ds_readonly` and the CLI now uses it.

## Next

Phase 0, Phase 1, Phase 2, and Phase 3 are complete. See
`../../reports/00_access.md`, `../phase-1-inventory/README.md`,
`../phase-2-extraction/README.md`, `../phase-3-cleaning/README.md`, and
`../../reports/03_cleaning_report.html`.

Phase 4:

1. Use the approved `config/features.yaml` and `config/management_levers.yaml`.
2. Build cutoff-safe derived features and the final modeling table.
3. Run feature regression tests and leakage checks.
4. Proceed to time-aware model training and validation.
