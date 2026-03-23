#!/bin/bash
# Script from 10.0.2.10:/opt/ci/deploy.sh
export MYSQL_PWD='Bkp_r00t_2024!'
mysqldump -u root --all-databases > /var/backups/full_dump.sql
gzip /var/backups/full_dump.sql
