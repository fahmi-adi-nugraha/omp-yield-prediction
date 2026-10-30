-- Create the least-privilege read-only account used by the yield pipeline.
--
-- Usage (local bootstrap; do not commit the password):
--   read -r -s OMP_READONLY_PASSWORD
--   sqlcmd -C -S localhost,1433 -U sa -P "$SA_PASSWORD" -d master \
--     -v ReadOnlyPassword="$OMP_READONLY_PASSWORD" \
--     -b -i docs/create_readonly_user.sql
--
-- The account is a SQL login with:
--   * db_datareader on omp_as_demo
--   * VIEW DEFINITION (so INFORMATION_SCHEMA introspection works)
--   * no write, DDL, or sysadmin permissions
--
-- This script is idempotent for the login, user, and role membership.

:setvar ReadOnlyPassword "CHANGE_ME"

IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = N'omp_ds_readonly')
BEGIN
    CREATE LOGIN [omp_ds_readonly]
        WITH PASSWORD = N'$(ReadOnlyPassword)',
             CHECK_POLICY = ON,
             CHECK_EXPIRATION = OFF;
END
ELSE
BEGIN
    ALTER LOGIN [omp_ds_readonly]
        WITH PASSWORD = N'$(ReadOnlyPassword)',
             CHECK_POLICY = ON,
             CHECK_EXPIRATION = OFF;
END
GO

USE [omp_as_demo];
GO

IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = N'omp_ds_readonly')
BEGIN
    CREATE USER [omp_ds_readonly] FOR LOGIN [omp_ds_readonly];
END
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.database_role_members drm
    JOIN sys.database_principals r ON r.principal_id = drm.role_principal_id
    JOIN sys.database_principals u ON u.principal_id = drm.member_principal_id
    WHERE r.name = N'db_datareader'
      AND u.name = N'omp_ds_readonly'
)
BEGIN
    ALTER ROLE [db_datareader] ADD MEMBER [omp_ds_readonly];
END
GO

GRANT VIEW DEFINITION TO [omp_ds_readonly];
GO
