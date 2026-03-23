#!/bin/bash
# Replicate WAL archives and base backup to standby server
set -e

STANDBY_HOST="db-standby.internal.corp"
STANDBY_USER="dba"
DATA_DIR="/var/lib/pgsql/14/data"
WAL_DIR="${DATA_DIR}/pg_wal"
BACKUP_DIR="/var/backups/pg"

echo "$(date '+%Y-%m-%d %H:%M:%S') - Starting replication sync to ${STANDBY_HOST}"

# Archive current WAL segments
/usr/pgsql-14/bin/pg_basebackup -h localhost -U replicator -D /tmp/pg_basebackup_tmp -Fp -Xs -P 2>/dev/null

# Sync WAL archives
rsync -avz --delete ${WAL_DIR}/ ${STANDBY_USER}@${STANDBY_HOST}:${WAL_DIR}/

# Sync latest backup
LATEST=$(ls -t ${BACKUP_DIR}/daily_*.sql.gz | head -1)
if [ -n "$LATEST" ]; then
    scp "$LATEST" ${STANDBY_USER}@${STANDBY_HOST}:${BACKUP_DIR}/
fi

rm -rf /tmp/pg_basebackup_tmp
echo "$(date '+%Y-%m-%d %H:%M:%S') - Replication sync complete"