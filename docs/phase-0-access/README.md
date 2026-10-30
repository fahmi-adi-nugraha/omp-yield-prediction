# Phase 0 — Read-Only Database Access

Status: **complete**

## Summary

- Database: `omp_as_demo` in the `omp-as-demo-db` container
- Login: `omp_ds_readonly`
- Grants: `db_datareader`, `VIEW DEFINITION`
- No `sysadmin`, `db_owner`, `db_datawriter`, DDL, or `EXECUTE`
- Credentials: `~/.config/omp-yield/env` (mode `600`), outside the project tree
- `sa` is used only for local bootstrap

## Verification

- `db ping` reports login `omp_ds_readonly` and 2,909 `OILPALM` rows.
- 274 tables and 207 `OILPALM` columns are visible.
- `CREATE TABLE` is denied.
- Integration tests pass against the read-only account.

Full report: `../../reports/00_access.md`.

## Bootstrap

The idempotent account-creation script is `create_readonly_user.sql`:

```bash
read -r -s OMP_READONLY_PASSWORD
sqlcmd -C -S localhost,1433 -U sa -P "$SA_PASSWORD" -d master \
  -v ReadOnlyPassword="$OMP_READONLY_PASSWORD" \
  -b -i docs/phase-0-access/create_readonly_user.sql
```

Do not commit the real password or a filled-in SQL file.
