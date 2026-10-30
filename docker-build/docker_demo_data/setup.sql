-- Restore the database from the backup file
RESTORE DATABASE omp_as_demo
FROM DISK = '/var/opt/mssql/backup/OMP_ASDemo_20260618_01.bak'
WITH MOVE 'OMP_CurrDev' TO '/var/opt/mssql/data/omp_as_demo.mdf',
     MOVE 'OMP_CurrDev_log'  TO '/var/opt/mssql/data/omp_as_demo.ldf',
     REPLACE;
GO

-- Wait until the restored database is fully online before proceeding
DECLARE @retries INT = 0;
-- WHILE @retries < 30
WHILE @retries < 60
BEGIN
    IF EXISTS (
        SELECT 1 FROM sys.databases
        WHERE name = 'omp_as_demo' AND state_desc = 'ONLINE'
    )
        BREAK;

    WAITFOR DELAY '00:00:02';
    SET @retries = @retries + 1;
END

IF NOT EXISTS (
    SELECT 1 FROM sys.databases
    WHERE name = 'omp_as_demo' AND state_desc = 'ONLINE'
)
BEGIN
    RAISERROR('Database omp_as_demo did not come online within 60 seconds.', 16, 1);
    RETURN;
END
GO

-- Enable CLR
EXEC sp_configure 'clr enabled', 1;
RECONFIGURE;
GO

-- Trust the assembly
USE omp_as_demo;
GO

DECLARE
    @hash BINARY(64),
	@description NVARCHAR(4000);

SELECT
    @hash = HASHBYTES('SHA2_512', af.content),
	@description = a.clr_name
FROM sys.assemblies a
JOIN sys.assembly_files af
    ON a.assembly_id = af.assembly_id
WHERE a.is_user_defined = 1
    AND a.name = 'omp_plt_clrfctns';

IF @hash IS NULL
BEGIN
    RAISERROR('Assembly omp_plt_clrfctns not found in omp_as_demo. Cannot trust it.', 16, 1);
    RETURN;
END

-- Only add if not already trusted (idempotent)
IF NOT EXISTS (
    SELECT 1 FROM sys.trusted_assemblies WHERE hash = @hash
)
BEGIN
    EXEC sys.sp_add_trusted_assembly @hash, @description;
    PRINT 'Assembly trusted successfully.';
END
ELSE
    PRINT 'Assembly already trusted, skipping.';
GO
