# Phase 0 — Read-Only Database Access

Status: **complete**

## Overview

Create a dedicated, least-privilege SQL Server account for the pipeline and
verify that it can read and introspect the demo database but cannot write.

## Goals and deliverables

- SQL login/user `omp_ds_readonly` on `omp_as_demo`.
- `db_datareader` and `VIEW DEFINITION`; no `sysadmin`, `db_owner`,
  `db_datawriter`, DDL, or `EXECUTE`.
- Credentials stored outside the project at `~/.config/omp-yield/env` (mode
  `600`). Project `.env` is supported but not recommended in the
  Syncthing-synced tree.
- Idempotent bootstrap script at `docs/phase-0-access/create_readonly_user.sql`.
- Access report at `reports/00_access.md`.

## Technical details

`sa` is used only for the local bootstrap. The account is created with:

```sql
CREATE LOGIN [omp_ds_readonly] WITH PASSWORD = N'<strong-password>',
    CHECK_POLICY = ON, CHECK_EXPIRATION = OFF;
CREATE USER [omp_ds_readonly] FOR LOGIN [omp_ds_readonly];
ALTER ROLE [db_datareader] ADD MEMBER [omp_ds_readonly];
GRANT VIEW DEFINITION TO [omp_ds_readonly];
```

The pipeline connects through `connectorx` using
`OMP_DB_USER=omp_ds_readonly` and the password from the user env file. The
read-only SQL guard is an additional safety layer, not a replacement for DB
permissions.

## Locations

- `docs/phase-0-access/README.md`
- `docs/phase-0-access/create_readonly_user.sql`
- `reports/00_access.md`
- `~/.config/omp-yield/env` (not in repo)
- `.env.example`

## Verification

```bash
uv run omp-yield db ping
uv run omp-yield db schema --table OILPALM
uv run omp-yield db query "SELECT TOP 1 NAME FROM OILPALM"
```

Expected: login `omp_ds_readonly`, 2,909 OILPALM rows, 274 visible tables, 207
OILPALM columns, and a rejected `CREATE TABLE`.

## Next

Phase 1 — inventory the schema and build the data dictionary.
