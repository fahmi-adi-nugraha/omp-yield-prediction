#!/bin/bash

# Mirror the official Microsoft entrypoint EULA check
if [ "${ACCEPT_EULA}" != "Y" ] && [ "${ACCEPT_EULA}" != "YES" ]; then
    echo "ERROR: You must accept the End User License Agreement (EULA) by setting"
    echo "the ACCEPT_EULA environment variable to 'Y' or 'YES'."
    echo "e.g. ACCEPT_EULA=Y"
    exit 1
fi

# Path to our initialization flag
FLAG_FILE="/var/opt/mssql/.setup_done"

# Start SQL Server in the background, capturing its PID
/opt/mssql/bin/sqlservr --accept-eula --sa-password "$MSSQL_SA_PASSWORD" &
SQLSERVR_PID=$!

# Wait for it to be ready
echo "Waiting for SQL Server to start..."
STATUS=1
i=0
while [ $STATUS -ne 0 ] && [ $i -lt 60 ]; do
    i=$((i+1))
    /opt/mssql-tools18/bin/sqlcmd -C -S localhost -U sa -P "$MSSQL_SA_PASSWORD" -Q "SELECT 1" > /dev/null 2>&1
    STATUS=$?
    sleep 1
done

if [ $STATUS -ne 0 ]; then
    echo "SQL Server failed to start within 60 seconds. Exiting."
    exit 1
fi

# Check if we have already initialized this database volume
if [ ! -f "$FLAG_FILE" ]; then
    echo "First-time setup: Running setup.sql..."
    /opt/mssql-tools18/bin/sqlcmd -C -S localhost -U sa -P "$MSSQL_SA_PASSWORD" -i /app/scripts/setup.sql -b
    
    if [ $? -eq 0 ]; then
        echo "Database setup completed successfully."
        touch "$FLAG_FILE"
    else
        echo "ERROR: Database setup failed!"
        exit 1
    fi
else
    echo "Database already initialized. Skipping setup.sql."
fi

echo "Setup complete. Keeping container alive..."
wait $SQLSERVR_PID
