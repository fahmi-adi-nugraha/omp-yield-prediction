# Phase 0 — Read-Only Database Access

Status: **complete**

## Source

| Item | Value |
|---|---|
| Container | `omp-as-demo-db` |
| Server | SQL Server 2025 (RTM-CU6) 17.0.4055.5 |
| Database | `omp_as_demo` |
| Login | `omp_ds_readonly` |
| `OILPALM` rows | 2,909 |

`sa` was used only to create the read-only account. The pipeline does not use
`sa`.

## Account creation

The repeatable bootstrap script is
`docs/phase-0-access/create_readonly_user.sql`. It is idempotent for the login,
user, and role membership.

Granted:

- `db_datareader` on `omp_as_demo`
- `VIEW DEFINITION`
- `CONNECT` via the login/user

Not granted:

- `sysadmin`
- `db_owner`
- `db_datawriter`
- DDL/`ALTER`/`CREATE`
- `EXECUTE`

## Credentials

The generated password is stored outside the project at:

```text
~/.config/omp-yield/env
```

The file is mode `600` and is not in the repository. The project-local `.env`
is also supported as a fallback, but using a path outside the Syncthing-synced
project tree is safer.

The CLI resolves credentials in this order:

1. `OMP_ENV_FILE`, if set
2. project `.env`
3. `~/.config/omp-yield/env`
4. `docker-build/.env` (local demo fallback only)

Shell environment variables take precedence over all files.

## Verification

### Connectivity and identity

```text
database_name: omp_as_demo
login_name: omp_ds_readonly
oilpalm_rows: 2909
```

### Permissions

```text
is_sysadmin: 0
is_datareader: 1
can_select(OILPALM): 1
can_insert(OILPALM): 0
```

### Metadata visibility

```text
tables: 274
OILPALM columns: 207
```

### Write rejection

```sql
CREATE TABLE dbo._phase0_write_test (id int);
```

```text
Msg 262, Level 14, State 1
CREATE TABLE permission denied in database 'omp_as_demo'.
```

The CLI also rejects writes before they reach SQL Server:

```text
$ uv run omp-yield db query "DELETE FROM OILPALM"
Error: Only SELECT and WITH queries are allowed.
```

### Tests

```text
$ OMP_RUN_INTEGRATION=1 uv run pytest tests/test_db_integration.py
2 passed

$ uv run pytest
17 passed, 2 skipped

$ uv run ruff check .
All checks passed!

$ uv run mypy src tests
Success: no issues found in 11 source files
```

## Security notes

- `sa` remains in `docker-build/.env` for local DB bootstrap only. Do not use it
  in the pipeline, notebooks, or CI.
- The project lives under a Syncthing-synced directory. Keep the password file
  outside that tree, or add it to Syncthing's ignore list.
- The MCP server is local stdio and therefore unauthenticated. Its safety boundary
  is the read-only SQL login plus the query guard.
- Rotate the `omp_ds_readonly` password periodically. Re-running the bootstrap
  script with a new `ReadOnlyPassword` updates the login without changing
  grants.
- Do not commit `~/.config/omp-yield/env`, project `.env`, or any SQL file
  containing the real password.

## Rollback

```sql
USE [omp_as_demo];
DROP USER IF EXISTS [omp_ds_readonly];
GO
DROP LOGIN IF EXISTS [omp_ds_readonly];
GO
```

## Next

Phase 1 — database inventory and data dictionary:

1. Inventory all tables, columns, row counts, keys, and date ranges.
2. Map join keys and measure match rates against `OILPALM`.
3. Capture growth-period definitions and the estate/division hierarchy.
4. Build the data dictionary and ERD.
