yum install postgresql14-server
/usr/pgsql-14/bin/postgresql-14-setup initdb
systemctl start postgresql-14
systemctl enable postgresql-14
su - postgres -c 'psql'
firewall-cmd --permanent --add-port=5432/tcp
firewall-cmd --reload
yum install pgbouncer
systemctl enable pgbouncer
cat /etc/pgbouncer/userlist.txt
ss -tlnp | grep 5432
df -h /var/lib/pgsql
free -m
top
cat /home/dba/.pgpass
ssh dba@db-standby.internal.corp 'pg_isready'
cat /var/log/pg_backup.log | tail -20ssh root@172.10.2.12 -p 2222
sshpass -p 'root' ssh root@172.10.2.12 -p 2222
