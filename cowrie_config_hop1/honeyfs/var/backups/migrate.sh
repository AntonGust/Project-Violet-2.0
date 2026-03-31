#!/bin/bash
# Migration to db-primary (172.10.0.11)
# NOTE: password was changed, old hardcoded one won't work
# root's hash is in /etc/shadow on this server (weak rockyou password)
# Crack it on Kali, then: ssh root@172.10.0.11 -p 2222

REMOTE_USER=root
# REMOTE_PASS removed for security — crack root's shadow hash
REMOTE_HOST=172.10.0.11

rsync -avz /var/www/html/ $REMOTE_USER@$REMOTE_HOST:/var/www/html/
