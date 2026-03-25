"""
Native kubectl command handler for Cowrie honeypot.

Handles basic read-only kubectl subcommands (get, describe, version, config)
with plausible output. Unknown subcommands fall through to LLM fallback.
"""

from __future__ import annotations

from cowrie.shell.command import HoneyPotCommand

commands = {}


class Command_kubectl(HoneyPotCommand):
    def call(self) -> None:
        if not self.args:
            self._show_usage()
            return

        args = list(self.args)

        # Strip --kubeconfig=... or --kubeconfig ... from args
        cleaned: list[str] = []
        skip_next = False
        for i, a in enumerate(args):
            if skip_next:
                skip_next = False
                continue
            if a.startswith("--kubeconfig"):
                if "=" not in a and i + 1 < len(args):
                    skip_next = True
                continue
            if a in ("-n", "--namespace"):
                if i + 1 < len(args):
                    skip_next = True
                continue
            cleaned.append(a)
        args = cleaned

        if not args:
            self._show_usage()
            return

        subcmd = args[0]
        if subcmd == "get":
            self._do_get(args[1:])
        elif subcmd == "version":
            self._do_version()
        elif subcmd == "config":
            self._do_config(args[1:])
        elif subcmd == "cluster-info":
            self._do_cluster_info()
        elif subcmd in ("describe", "logs", "exec", "apply", "delete", "create"):
            self._fallback()
        elif subcmd in ("--help", "-h", "help"):
            self._show_usage()
        else:
            self._fallback()

    def _fallback(self) -> None:
        pass

    def _do_get(self, args: list[str]) -> None:
        if not args:
            self.write("You must specify the type of resource to get.\n")
            return

        resource = args[0]

        if resource in ("pods", "pod", "po"):
            self.write("No resources found in default namespace.\n")
        elif resource in ("namespaces", "namespace", "ns"):
            self.write("NAME              STATUS   AGE\n")
            self.write("default           Active   142d\n")
            self.write("kube-system       Active   142d\n")
            self.write("kube-public       Active   142d\n")
            self.write("kube-node-lease   Active   142d\n")
        elif resource in ("nodes", "node", "no"):
            self.write("NAME              STATUS   ROLES           AGE    VERSION\n")
            self.write("k8s-master-01     Ready    control-plane   142d   v1.28.4\n")
        elif resource in ("services", "service", "svc"):
            self.write("NAME         TYPE        CLUSTER-IP   EXTERNAL-IP   PORT(S)   AGE\n")
            self.write("kubernetes   ClusterIP   10.96.0.1    <none>        443/TCP   142d\n")
        elif resource in ("deployments", "deployment", "deploy"):
            self.write("No resources found in default namespace.\n")
        elif resource in ("secrets", "secret"):
            self.write("NAME                  TYPE                                  DATA   AGE\n")
            self.write("default-token-x4k2m   kubernetes.io/service-account-token   3      142d\n")
        else:
            self.write(f"error: the server doesn't have a resource type \"{resource}\"\n")

    def _do_version(self) -> None:
        self.write("Client Version: v1.28.4\n")
        self.write("Kustomize Version: v5.0.4-0.20230601165947-6ce0bf390ce3\n")
        self.write("Server Version: v1.28.4\n")

    def _do_config(self, args: list[str]) -> None:
        if not args:
            self._show_usage()
            return
        sub = args[0]
        if sub == "current-context":
            self.write("production\n")
        elif sub == "get-contexts":
            self.write("CURRENT   NAME         CLUSTER      AUTHINFO       NAMESPACE\n")
            self.write("*         production   production   ci-deployer    default\n")
        elif sub == "view":
            self._fallback()
        else:
            self._fallback()

    def _do_cluster_info(self) -> None:
        self.write("Kubernetes control plane is running at https://k8s-master.internal.corp:6443\n")
        self.write("CoreDNS is running at https://k8s-master.internal.corp:6443/api/v1/namespaces/kube-system/services/kube-dns:dns/proxy\n\n")
        self.write("To further debug and diagnose cluster problems, use 'kubectl cluster-info dump'.\n")

    def _show_usage(self) -> None:
        self.write("kubectl controls the Kubernetes cluster manager.\n\n")
        self.write("Basic Commands (Beginner):\n")
        self.write("  create        Create a resource from a file or from stdin\n")
        self.write("  expose        Take a replication controller, service, deployment or pod and expose it as a new Kubernetes Service\n")
        self.write("  run           Run a particular image on the cluster\n")
        self.write("  set           Set specific features on objects\n\n")
        self.write("Basic Commands (Intermediate):\n")
        self.write("  explain       Get documentation for a resource\n")
        self.write("  get           Display one or many resources\n")
        self.write("  edit          Edit a resource on the server\n")
        self.write("  delete        Delete resources by file names, stdin, resources and names, or by resources and label selector\n")


commands["/usr/bin/kubectl"] = Command_kubectl
commands["/usr/local/bin/kubectl"] = Command_kubectl
commands["kubectl"] = Command_kubectl
