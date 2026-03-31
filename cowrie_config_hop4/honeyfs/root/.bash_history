systemctl status grafana-server
systemctl status prometheus
systemctl restart alertmanager
journalctl -u grafana-server -f
docker ps -a
ss -tlnp
curl -s http://localhost:9090/-/healthy
curl -s -u admin:Gr@f4na_Adm1n_M0n! http://localhost:3000/api/org
curl -H "Authorization: Bearer REDACTED_grafana_sa_sysops_automation" http://localhost:3000/api/dashboards/home
cat /etc/grafana/grafana.ini | grep password
prometheus --config.file=/opt/prometheus/prometheus.yml --check-config
cat /opt/prometheus/prometheus.yml
iptables -L -n
ufw status
apt update && apt upgrade -y
cat /var/log/grafana/grafana.log | tail -100