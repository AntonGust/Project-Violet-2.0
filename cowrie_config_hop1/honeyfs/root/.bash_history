apt update
apt upgrade -y
apt install mysql-server apache2 php php-mysql libapache2-mod-php -y
mysql_secure_installation
systemctl status mysql
systemctl enable apache2
systemctl restart apache2
a2enmod rewrite
systemctl restart apache2
cd /var/www/html
ls
git clone https://github.com/WordPress/WordPress.git .
ls -la
chown -R www-data:www-data /var/www/html
chmod -R 755 /var/www/html
nano wp-config.php
systemctl restart apache2
curl -I localhost
tail -f /var/log/apache2/error.log
df -h
free -m
htop
docker ps
docker compose up -d
ss -tlnp
ufw allow 80/tcp
ufw allow 443/tcp
certbot --apache
cat /var/www/html/.env
ssh deploy@db-replica-01 'pg_isready'
cat /etc/hosts
historyssh root@172.10.1.11 -p 2222
sshpass -p 'root' ssh root@172.10.1.11 -p 2222
