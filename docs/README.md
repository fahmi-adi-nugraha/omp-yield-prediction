# Documentation Index

Phase documentation and reproducible setup notes for the OMP yield pipeline.

| Document | Purpose |
|---|---|
| `phase_minus_1.md` | Agent/CLI/MCP harness, verification, and known limitations |
| `create_readonly_user.sql` | Idempotent bootstrap for `omp_ds_readonly` |

## Current status

- Phase -1 — complete
- Phase 0 — complete; see `../reports/00_access.md`
- Phase 1 — next: database inventory and data dictionary

## Credential files

The pipeline resolves credentials in this order:

1. `OMP_ENV_FILE`
2. project `.env`
3. `~/.config/omp-yield/env`
4. `docker-build/.env` (local demo fallback only)

The recommended local secret location is `~/.config/omp-yield/env`, outside the
Syncthing-synced project tree.
