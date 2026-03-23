#!/bin/bash
# Quick DB backup script
MYSQL_PWD='Str0ng_But_Le4ked!' mysqldump -u wp_admin wordpress_prod | gzip > /tmp/db_backup_$(date +%Y%m%d).sql.gz
aws s3 cp /tmp/db_backup_*.sql.gz s3://wp-prod-backups/
scp /tmp/db_backup_*.sql.gz deploy@10.0.1.20:/var/backups/wp/
rm /tmp/db_backup_*.sql.gz