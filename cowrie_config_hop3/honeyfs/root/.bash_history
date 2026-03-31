systemctl status jenkins
journalctl -u jenkins -f
docker ps -a
docker system prune -af
curl -sSL https://get.docker.com | sh
usermod -aG docker jenkins
systemctl restart jenkins
cat /var/lib/jenkins/secrets/initialAdminPassword
iptables -L -n
ss -tlnp
gitlab-runner register
cat /home/gitlab-runner/.gitlab-runner/config.toml
kubectl get pods -A
kubectl get nodes
cat /root/.kube/config
ssh root@172.10.0.13 -p 2222
