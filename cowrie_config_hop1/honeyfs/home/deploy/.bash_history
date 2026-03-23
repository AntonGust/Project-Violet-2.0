sudo systemctl restart apache2
mysql -u wp_admin -p wordpress_prod
cd /var/www/html
git pull origin main
sudo chown -R www-data:www-data /var/www/html
docker ps
docker compose logs -f
cat /var/www/html/.env
sudo tail -f /var/log/apache2/error.log
ss -tlnp
df -h
free -m
bash backup_db.sh
aws s3 ls s3://wp-prod-backups/
ssh deploy@db-replica-01
cat /etc/hosts
sudo cat /etc/shadow
history