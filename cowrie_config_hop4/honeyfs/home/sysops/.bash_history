sudo systemctl status grafana-server
sudo systemctl status prometheus
sudo systemctl restart alertmanager
docker ps
docker logs grafana --tail 50
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {instance: .labels.instance, health: .health}'
curl -s -u admin:Gr@f4na_Adm1n_M0n! http://localhost:3000/api/health
cat /opt/prometheus/prometheus.yml
sudo cat /etc/grafana/grafana.ini
cp /etc/alertmanager/alertmanager.yml ~/alertmanager_config_backup.yml
ssh app-prod-01 'systemctl status node_exporter'
ssh db-primary 'df -h /var/lib/postgresql'
ssh redis-01 'redis-cli info memory'
sudo journalctl -u prometheus --since '1 hour ago'
cat /home/sysops/.grafana_api_token
curl -H "Authorization: Bearer REDACTED_grafana_sa_sysops_automation" http://localhost:3000/api/dashboards/home