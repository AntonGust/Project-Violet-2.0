#!/bin/bash
# EMERGENCY DB RESTORE - contact DBA team first!
set -e
BACKUP_FILE="$1"
if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file.sql.gz>"
    exit 1
fi
systemctl stop pgbouncer
PGPASSWORD='P0stgr3s_Sup3r_SV3cret!' dropdb -U postgres app_production
PGPASSWORD='P0stgr3s_Sup3r_S3cret!' createdb -U postgres app_production
gunzip -c $BACKUP_FILE | PGPASSWORD='P0stgr3s_Sup3r_S3cret!' psql -U postgres app_production
systemctl start pgbouncer
echo "Restore complete. Verify data integrity!"