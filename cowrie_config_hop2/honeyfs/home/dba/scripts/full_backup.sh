#!/bin/bash
set -e
BACKUP_DIR=/var/backups/pg
DATE=$(date +%Y-%m-%d)
FILENAME="daily_${DATE}.sql.gz"

export PGPASSWORD='P0stgr3s_Sup3r_S3cret!'
pg_dumpall -U postgres | gzip > ${BACKUP_DIR}/${FILENAME}

# Upload to S3
aws s3 cp ${BACKUP_DIR}/${FILENAME} s3://corp-db-backups/pg-primary/${FILENAME}

# Replicate to standby
scp ${BACKUP_DIR}/${FILENAME} dba@db-standby.internal.corp:/var/backups/pg/

# Cleanup old backups (keep 14 days)
find ${BACKUP_DIR} -name 'daily_*.sql.gz' -mtime +14 -delete

echo "Backup complete: ${FILENAME}"