FROM mcr.microsoft.com/mssql/server:2025-latest

# Switch to root to create directories and set permissions
USER root

# Copy your files into the image
COPY OMP_ASDemo_20260618_01.bak /var/opt/mssql/backup/
COPY setup.sql /app/scripts/
COPY entrypoint.sh /app/scripts/

# Make the entrypoint script executable
RUN chmod +x /app/scripts/entrypoint.sh

# Switch back to the mssql user for security
USER mssql

# Set the entrypoint to our custom script
ENTRYPOINT ["/app/scripts/entrypoint.sh"]
