"""
Profile Converter: transforms a filesystem profile JSON into Cowrie honeypot artifacts.

Generates:
  - fs.pickle  (virtual filesystem tree)
  - honeyfs/   (file contents for cat/head/tail)
  - txtcmds/   (static command outputs for uname, ps, ifconfig, etc.)
  - userdb.txt (Cowrie SSH accepted credentials)
  - LLM system prompt (for the hybrid fallback)
  - cowrie.cfg overrides (hostname, kernel, arch)
"""

import json
import pickle
import random
import shutil
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Cowrie filesystem constants (must match src/cowrie/shell/fs.py)
# ---------------------------------------------------------------------------
A_NAME = 0
A_TYPE = 1
A_UID = 2
A_GID = 3
A_SIZE = 4
A_MODE = 5
A_CTIME = 6
A_CONTENTS = 7
A_TARGET = 8
A_REALFILE = 9

# Must match Cowrie's fs.py: T_LINK, T_DIR, T_FILE, ... = range(0, 7)
T_LINK = 0
T_DIR = 1
T_FILE = 2
T_BLK = 3
T_CHR = 4
T_SOCK = 5
T_FIFO = 6

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uid_for_user(username: str, profile: dict) -> int:
    for u in profile["users"]:
        if u["name"] == username:
            return u["uid"]
    return 0


def _gid_for_user(username: str, profile: dict) -> int:
    for u in profile["users"]:
        if u["name"] == username:
            return u.get("gid", u["uid"])
    return 0


def _ensure_dir(dir_nodes: dict, path: str, now: float) -> list:
    """Recursively ensure a directory path exists in the pickle tree."""
    if path in dir_nodes:
        return dir_nodes[path]

    parent_path = str(Path(path).parent)
    parent_node = _ensure_dir(dir_nodes, parent_path, now)

    name = Path(path).name
    child = [name, T_DIR, 0, 0, 4096, 0o755, now, [], "", None]
    parent_node[A_CONTENTS].append(child)
    dir_nodes[path] = child
    return child


# ---------------------------------------------------------------------------
# Pickle generation
# ---------------------------------------------------------------------------

def profile_to_pickle(profile: dict) -> list:
    """
    Convert a filesystem profile to Cowrie's pickle tree structure.

    Returns the root node: a list-of-lists where each node has 10 fields
    (A_NAME .. A_REALFILE).
    """
    now = time.time()
    # Create varied timestamps to simulate a real server with history.
    # Base install ~90 days ago, some files modified more recently.
    install_time = now - 90 * 86400 + random.randint(-86400, 86400)
    boot_time = now - 47 * 86400
    recent_time = now - random.randint(3600, 7 * 86400)

    def _ts_install():
        return install_time + random.randint(0, 3600)

    def _ts_recent():
        return recent_time + random.randint(-86400, 86400)

    # Root node
    root = ["", T_DIR, 0, 0, 4096, 0o755, install_time, [], "", None]

    # Standard Linux directory skeleton (comprehensive)
    standard_dirs = [
        "/bin", "/boot", "/dev", "/dev/pts", "/etc",
        "/etc/alternatives", "/etc/apt", "/etc/apt/sources.list.d",
        "/etc/cron.d", "/etc/cron.daily", "/etc/cron.hourly",
        "/etc/cron.monthly", "/etc/cron.weekly",
        "/etc/default", "/etc/dpkg", "/etc/init.d",
        "/etc/ld.so.conf.d", "/etc/logrotate.d", "/etc/network",
        "/etc/network/interfaces.d", "/etc/pam.d", "/etc/profile.d",
        "/etc/security", "/etc/ssh", "/etc/ssl", "/etc/ssl/certs",
        "/etc/ssl/private", "/etc/sudoers.d", "/etc/systemd",
        "/etc/systemd/system", "/etc/update-motd.d",
        "/home", "/lib", "/lib/x86_64-linux-gnu",
        "/lib64", "/media", "/mnt",
        "/opt", "/proc", "/root", "/run", "/run/lock",
        "/run/sshd", "/sbin", "/srv", "/sys",
        "/sys/fs/cgroup",
        "/tmp", "/usr", "/usr/bin", "/usr/sbin", "/usr/lib",
        "/usr/local", "/usr/local/bin", "/usr/local/sbin",
        "/usr/share", "/usr/share/doc",
        "/var", "/var/backups", "/var/cache", "/var/cache/apt",
        "/var/lib", "/var/lib/dpkg", "/var/log",
        "/var/log/apt", "/var/mail", "/var/run",
        "/var/spool", "/var/spool/cron", "/var/spool/cron/crontabs",
        "/var/tmp", "/var/www",
    ]

    # Collect all directories referenced in the profile
    for dir_path in profile.get("directory_tree", {}):
        parts = dir_path.strip("/").split("/")
        for i in range(len(parts)):
            d = "/" + "/".join(parts[: i + 1])
            if d not in standard_dirs:
                standard_dirs.append(d)

    # Ensure parent dirs for all file_contents paths
    for file_path in profile.get("file_contents", {}):
        parent = str(Path(file_path).parent)
        if parent == "/":
            continue
        parts = parent.strip("/").split("/")
        for i in range(len(parts)):
            d = "/" + "/".join(parts[: i + 1])
            if d not in standard_dirs:
                standard_dirs.append(d)

    # Ensure parent dirs for user home directories (skip nologin/service users
    # whose homes like /nonexistent are not real directories on production systems)
    _SKIP_HOMES = {"/nonexistent", "/usr/sbin", "/bin", "/dev", "/"}
    for u in profile.get("users", []):
        home = u.get("home", "")
        shell = u.get("shell", "")
        if not home or home in _SKIP_HOMES:
            continue
        if "nologin" in shell or "false" in shell:
            continue
        parts = home.strip("/").split("/")
        for i in range(len(parts)):
            d = "/" + "/".join(parts[: i + 1])
            if d not in standard_dirs:
                standard_dirs.append(d)

    # Create all directories with install-time timestamps
    dir_nodes = {"/": root}
    for d in sorted(standard_dirs):
        _ensure_dir(dir_nodes, d, _ts_install())

    # Track which files we've already added (to avoid duplicates)
    added_files = set()

    # Add entries from directory_tree
    for dir_path, entries in profile.get("directory_tree", {}).items():
        parent_node = dir_nodes.get(dir_path)
        if not parent_node:
            parent_node = _ensure_dir(dir_nodes, dir_path, _ts_install())

        for entry in entries:
            name = entry["name"].rstrip("/")
            full_path = f"{dir_path.rstrip('/')}/{name}"

            if full_path in added_files:
                continue
            added_files.add(full_path)

            entry_type = {"file": T_FILE, "dir": T_DIR, "symlink": T_LINK}.get(
                entry["type"], T_FILE
            )
            perms = int(entry.get("permissions", "0755" if entry_type == T_DIR else "0644"), 8)
            owner = entry.get("owner", "root")
            group = entry.get("group", "root")
            size = entry.get("size", 0)
            uid = _uid_for_user(owner, profile)
            gid = _gid_for_user(group, profile)
            ts = _ts_recent()

            if entry_type == T_DIR:
                if full_path not in dir_nodes:
                    child = [name, T_DIR, uid, gid, 4096, perms, ts, [], "", None]
                    parent_node[A_CONTENTS].append(child)
                    dir_nodes[full_path] = child
            elif entry_type == T_LINK:
                target = entry.get("symlink_target", "")
                child = [name, T_LINK, uid, gid, len(target), perms, ts, None, target, None]
                parent_node[A_CONTENTS].append(child)
            else:
                # Regular file — use size from profile entry, or from
                # file_contents if available.
                if full_path in profile.get("file_contents", {}):
                    size = len(profile["file_contents"][full_path])
                child = [name, T_FILE, uid, gid, size, perms, ts, None, "", None]
                parent_node[A_CONTENTS].append(child)

    # Also add files that are in file_contents but not explicitly in directory_tree
    for file_path, content in profile.get("file_contents", {}).items():
        if file_path in added_files:
            continue
        added_files.add(file_path)

        parent_dir = str(Path(file_path).parent)
        parent_node = dir_nodes.get(parent_dir)
        if not parent_node:
            parent_node = _ensure_dir(dir_nodes, parent_dir, _ts_install())

        name = Path(file_path).name
        size = len(content)
        child = [name, T_FILE, 0, 0, size, 0o644, _ts_recent(), None, "", None]
        parent_node[A_CONTENTS].append(child)

    # Add nodes for auto-generated honeyfs files so init_honeyfs can link
    # them.  Use realistic sizes (estimated) and correct permissions.
    auto_files = {
        # path: (size_estimate, mode, uid, gid)
        "/etc/passwd": (1800, 0o644, 0, 0),
        "/etc/shadow": (1200, 0o640, 0, 42),  # root:shadow
        "/etc/group": (800, 0o644, 0, 0),
        "/etc/hostname": (20, 0o644, 0, 0),
        "/etc/os-release": (400, 0o644, 0, 0),
        "/etc/hosts": (220, 0o644, 0, 0),
        "/etc/resolv.conf": (120, 0o644, 0, 0),
        "/etc/fstab": (400, 0o644, 0, 0),
        "/etc/nsswitch.conf": (300, 0o644, 0, 0),
        "/etc/timezone": (10, 0o644, 0, 0),
        "/etc/default/locale": (25, 0o644, 0, 0),
        "/etc/motd": (500, 0o644, 0, 0),
        "/etc/ssh/sshd_config": (700, 0o644, 0, 0),
        "/etc/crontab": (600, 0o644, 0, 0),
        "/root/.bashrc": (1200, 0o644, 0, 0),
    }
    # Add sudoers.d entries
    for u in profile.get("users", []):
        if u.get("sudo_rules"):
            auto_files[f"/etc/sudoers.d/{u['name']}"] = (60, 0o440, 0, 0)

    # Add systemd service unit files for each profile service
    for svc in profile.get("services", []):
        auto_files[f"/etc/systemd/system/{svc['name']}.service"] = (250, 0o644, 0, 0)

    for file_path, (est_size, mode, uid, gid) in auto_files.items():
        if file_path in added_files:
            continue
        added_files.add(file_path)
        parent_dir = str(Path(file_path).parent)
        parent_node = dir_nodes.get(parent_dir)
        if not parent_node:
            parent_node = _ensure_dir(dir_nodes, parent_dir, _ts_install())
        name = Path(file_path).name
        child = [name, T_FILE, uid, gid, est_size, mode, _ts_install(), None, "", None]
        parent_node[A_CONTENTS].append(child)

    # Set SUID permission bits on standard binaries that every real Linux has.
    # Without these, `find / -perm -4000` returns nothing — a dead giveaway.
    suid_binaries = [
        "/usr/bin/passwd", "/usr/bin/su", "/usr/bin/sudo",
        "/usr/bin/newgrp", "/usr/bin/chfn", "/usr/bin/chsh",
        "/usr/bin/mount", "/usr/bin/umount", "/usr/bin/gpasswd",
        "/bin/mount", "/bin/umount", "/bin/su",
        "/usr/bin/ping",
    ]
    for suid_path in suid_binaries:
        parent_dir = str(Path(suid_path).parent)
        parent_node = dir_nodes.get(parent_dir)
        if not parent_node:
            continue
        name = Path(suid_path).name
        # Check if the file already exists
        existing = [c for c in parent_node[A_CONTENTS] if c[A_NAME] == name]
        if existing:
            existing[0][A_MODE] = 0o104755
        else:
            child = [name, T_FILE, 0, 0, random.randint(30000, 80000),
                     0o104755, _ts_install(), None, "", None]
            parent_node[A_CONTENTS].append(child)
            added_files.add(suid_path)

    # Add binary stubs for installed packages so `which` returns results.
    # Maps package name patterns to the binaries they provide.
    _PKG_BINARIES: dict[str, list[str]] = {
        "mysql-server": ["/usr/bin/mysql", "/usr/bin/mysqldump", "/usr/bin/mysqladmin"],
        "mysql-client": ["/usr/bin/mysql", "/usr/bin/mysqldump"],
        "mariadb-server": ["/usr/bin/mysql", "/usr/bin/mysqldump", "/usr/bin/mariadb"],
        "postgresql": ["/usr/bin/psql", "/usr/bin/pg_dump", "/usr/bin/pg_isready"],
        "curl": ["/usr/bin/curl"],
        "wget": ["/usr/bin/wget"],
        "net-tools": ["/sbin/ifconfig", "/usr/sbin/ifconfig", "/bin/netstat"],
        "iproute2": ["/sbin/ip", "/usr/sbin/ip", "/usr/bin/ip"],
        "nmap": ["/usr/bin/nmap"],
        "python3": ["/usr/bin/python3"],
        "python": ["/usr/bin/python"],
        "docker-ce": ["/usr/bin/docker"],
        "docker.io": ["/usr/bin/docker"],
        "git": ["/usr/bin/git"],
        "vim": ["/usr/bin/vim"],
        "nano": ["/usr/bin/nano"],
        "apache2": ["/usr/sbin/apache2", "/usr/sbin/apachectl"],
        "nginx": ["/usr/sbin/nginx"],
        "openssh-server": ["/usr/sbin/sshd"],
        "openssh-client": ["/usr/bin/ssh", "/usr/bin/scp", "/usr/bin/ssh-keygen"],
        "coreutils": ["/usr/bin/ls", "/usr/bin/cat", "/usr/bin/cp", "/usr/bin/mv"],
    }
    for pkg in profile.get("installed_packages", []):
        pkg_name = pkg.get("name", "").lower()
        for pattern, bins in _PKG_BINARIES.items():
            if pattern in pkg_name:
                for bin_path in bins:
                    if bin_path in added_files:
                        continue
                    added_files.add(bin_path)
                    parent_dir = str(Path(bin_path).parent)
                    parent_node = dir_nodes.get(parent_dir)
                    if not parent_node:
                        parent_node = _ensure_dir(dir_nodes, parent_dir, _ts_install())
                    name = Path(bin_path).name
                    existing = [c for c in parent_node[A_CONTENTS] if c[A_NAME] == name]
                    if not existing:
                        child = [name, T_FILE, 0, 0, random.randint(20000, 120000),
                                 0o755, _ts_install(), None, "", None]
                        parent_node[A_CONTENTS].append(child)

    return root


# ---------------------------------------------------------------------------
# Honeyfs generation
# ---------------------------------------------------------------------------

def generate_honeyfs(profile: dict, output_dir: Path) -> None:
    """Write file contents to a honeyfs directory structure."""
    # Write explicit file_contents
    for file_path, content in profile.get("file_contents", {}).items():
        target = output_dir / file_path.lstrip("/")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    sys_info = profile.get("system", {})
    hostname = sys_info.get("hostname", "localhost")
    os_name = sys_info.get("os", "Linux")
    os_parts = os_name.split()
    distro_id = os_parts[0].lower() if os_parts else "linux"
    distro_name = os_parts[0] if os_parts else "Linux"
    version_str = " ".join(os_parts[1:]) if len(os_parts) > 1 else ""
    # Extract version components (e.g., "20.04.6 LTS" -> "20.04")
    version_id = version_str.split()[0] if version_str else "20.04"
    version_codename = _ubuntu_codename(version_id)

    etc_dir = output_dir / "etc"
    etc_dir.mkdir(parents=True, exist_ok=True)

    # Standard system accounts that exist on every Debian/Ubuntu system
    system_accounts = [
        ("daemon", 1, 1, "daemon", "/usr/sbin", "/usr/sbin/nologin"),
        ("bin", 2, 2, "bin", "/bin", "/usr/sbin/nologin"),
        ("sys", 3, 3, "sys", "/dev", "/usr/sbin/nologin"),
        ("sync", 4, 65534, "sync", "/bin", "/bin/sync"),
        ("games", 5, 60, "games", "/usr/games", "/usr/sbin/nologin"),
        ("man", 6, 12, "man", "/var/cache/man", "/usr/sbin/nologin"),
        ("lp", 7, 7, "lp", "/var/spool/lpd", "/usr/sbin/nologin"),
        ("mail", 8, 8, "mail", "/var/mail", "/usr/sbin/nologin"),
        ("news", 9, 9, "news", "/var/spool/news", "/usr/sbin/nologin"),
        ("uucp", 10, 10, "uucp", "/var/spool/uucp", "/usr/sbin/nologin"),
        ("proxy", 13, 13, "proxy", "/bin", "/usr/sbin/nologin"),
        ("backup", 34, 34, "backup", "/var/backups", "/usr/sbin/nologin"),
        ("list", 38, 38, "Mailing List Manager", "/var/list", "/usr/sbin/nologin"),
        ("irc", 39, 39, "ircd", "/var/run/ircd", "/usr/sbin/nologin"),
        ("gnats", 41, 41, "Gnats Bug-Reporting System", "/var/lib/gnats", "/usr/sbin/nologin"),
        ("nobody", 65534, 65534, "nobody", "/nonexistent", "/usr/sbin/nologin"),
        ("systemd-network", 100, 102, "systemd Network Management", "/run/systemd", "/usr/sbin/nologin"),
        ("systemd-resolve", 101, 103, "systemd Resolver", "/run/systemd", "/usr/sbin/nologin"),
        ("syslog", 102, 106, "syslog", "/home/syslog", "/usr/sbin/nologin"),
        ("messagebus", 103, 107, "dbus", "/nonexistent", "/usr/sbin/nologin"),
        ("_apt", 104, 65534, "apt", "/nonexistent", "/usr/sbin/nologin"),
        ("sshd", 105, 65534, "sshd", "/run/sshd", "/usr/sbin/nologin"),
    ]

    # Build /etc/passwd: system accounts + profile users
    passwd_lines = []
    shadow_lines = []
    profile_uids = {u["uid"] for u in profile.get("users", [])}

    # Root first (from profile)
    for u in profile.get("users", []):
        if u["uid"] == 0:
            passwd_lines.append(
                f"{u['name']}:x:{u['uid']}:{u.get('gid', u['uid'])}:"
                f"{u['name']}:{u['home']}:{u['shell']}"
            )
            shadow_lines.append(f"{u['name']}:{u.get('password_hash', '*')}:19000:0:99999:7:::")
            break

    # System accounts
    for name, uid, gid, gecos, home, shell in system_accounts:
        if uid not in profile_uids:
            passwd_lines.append(f"{name}:x:{uid}:{gid}:{gecos}:{home}:{shell}")
            shadow_lines.append(f"{name}:*:19000:0:99999:7:::")

    # Non-root profile users
    for u in profile.get("users", []):
        if u["uid"] == 0:
            continue
        passwd_lines.append(
            f"{u['name']}:x:{u['uid']}:{u.get('gid', u['uid'])}:"
            f"{u['name']}:{u['home']}:{u['shell']}"
        )
        shadow_lines.append(f"{u['name']}:{u.get('password_hash', '*')}:19000:0:99999:7:::")

    # Extra shadow entries injected by credential_chain (e.g. crackable hashes)
    for entry in profile.get("_extra_shadow_entries", []):
        shadow_lines.append(f"{entry['username']}:{entry['hash']}:19000:0:99999:7:::")

    (etc_dir / "passwd").write_text("\n".join(passwd_lines) + "\n", encoding="utf-8")
    (etc_dir / "shadow").write_text("\n".join(shadow_lines) + "\n", encoding="utf-8")

    # /etc/group: system groups + profile groups
    group_lines = [
        "root:x:0:",
        "daemon:x:1:",
        "bin:x:2:",
        "sys:x:3:",
        "adm:x:4:syslog",
        "tty:x:5:",
        "disk:x:6:",
        "lp:x:7:",
        "mail:x:8:",
        "news:x:9:",
        "uucp:x:10:",
        "man:x:12:",
        "proxy:x:13:",
        "kmem:x:15:",
        "dialout:x:20:",
        "fax:x:21:",
        "voice:x:22:",
        "cdrom:x:24:",
        "floppy:x:25:",
        "tape:x:26:",
        "sudo:x:27:",
        "audio:x:29:",
        "dip:x:30:",
        "www-data:x:33:",
        "backup:x:34:",
        "operator:x:37:",
        "list:x:38:",
        "irc:x:39:",
        "src:x:40:",
        "gnats:x:41:",
        "shadow:x:42:",
        "utmp:x:43:",
        "video:x:44:",
        "sasl:x:45:",
        "plugdev:x:46:",
        "staff:x:50:",
        "games:x:60:",
        "users:x:100:",
        "nogroup:x:65534:",
        "systemd-journal:x:101:",
        "systemd-network:x:102:",
        "systemd-resolve:x:103:",
        "crontab:x:104:",
        "syslog:x:106:",
        "messagebus:x:107:",
        "ssh:x:108:",
    ]
    # Add profile user groups with memberships
    seen_groups = {line.split(":")[0] for line in group_lines}
    for u in profile.get("users", []):
        gname = u["name"]
        gid = u.get("gid", u["uid"])
        if gname not in seen_groups and gid != 0:
            group_lines.append(f"{gname}:x:{gid}:")
            seen_groups.add(gname)
        # Add user to groups they belong to
        for g in u.get("groups", []):
            if g in seen_groups and g != gname:
                for i, line in enumerate(group_lines):
                    parts = line.split(":")
                    if parts[0] == g:
                        members = parts[3]
                        if members:
                            members += f",{u['name']}"
                        else:
                            members = u["name"]
                        group_lines[i] = f"{parts[0]}:{parts[1]}:{parts[2]}:{members}"
                        break

    (etc_dir / "group").write_text("\n".join(group_lines) + "\n", encoding="utf-8")

    # /etc/hostname
    (etc_dir / "hostname").write_text(hostname + "\n", encoding="utf-8")

    # /etc/os-release (full, matching real Ubuntu output)
    (etc_dir / "os-release").write_text(
        f'PRETTY_NAME="{os_name}"\n'
        f'NAME="{distro_name}"\n'
        f'VERSION_ID="{version_id}"\n'
        f'VERSION="{version_str}"\n'
        f"ID={distro_id}\n"
        f'ID_LIKE=debian\n'
        f'HOME_URL="https://www.ubuntu.com/"\n'
        f'SUPPORT_URL="https://help.ubuntu.com/"\n'
        f'BUG_REPORT_URL="https://bugs.launchpad.net/ubuntu/"\n'
        f'PRIVACY_POLICY_URL="https://www.ubuntu.com/legal/terms-and-policies/privacy-policy"\n'
        f'VERSION_CODENAME={version_codename}\n'
        f'UBUNTU_CODENAME={version_codename}\n',
        encoding="utf-8",
    )

    # /etc/hosts — only auto-generate if the profile didn't already provide one
    # via file_contents (which may contain lateral movement targets)
    if "/etc/hosts" not in profile.get("file_contents", {}):
        (etc_dir / "hosts").write_text(
            f"127.0.0.1\tlocalhost\n"
            f"127.0.1.1\t{hostname}\n"
            f"\n"
            f"# The following lines are desirable for IPv6 capable hosts\n"
            f"::1     localhost ip6-localhost ip6-loopback\n"
            f"ff02::1 ip6-allnodes\n"
            f"ff02::2 ip6-allrouters\n",
            encoding="utf-8",
        )

    # /etc/resolv.conf
    (etc_dir / "resolv.conf").write_text(
        f"# Dynamic resolv.conf(5) file for glibc resolver(3) generated by resolvconf(8)\n"
        f"nameserver 8.8.8.8\n"
        f"nameserver 8.8.4.4\n"
        f"search localdomain\n",
        encoding="utf-8",
    )

    # /etc/fstab
    (etc_dir / "fstab").write_text(
        f"# /etc/fstab: static file system information.\n"
        f"#\n"
        f"# <file system> <mount point>   <type>  <options>       <dump>  <pass>\n"
        f"UUID=a1b2c3d4-e5f6-7890-abcd-000000000001 /               ext4    errors=remount-ro 0       1\n"
        f"UUID=a1b2c3d4-e5f6-7890-abcd-000000000002 none            swap    sw              0       0\n"
        f"/dev/sr0        /media/cdrom0   udf,iso9660 user,noauto     0       0\n",
        encoding="utf-8",
    )

    # /etc/nsswitch.conf
    (etc_dir / "nsswitch.conf").write_text(
        "passwd:         files systemd\n"
        "group:          files systemd\n"
        "shadow:         files\n"
        "gshadow:        files\n"
        "\n"
        "hosts:          files dns\n"
        "networks:       files\n"
        "\n"
        "protocols:      db files\n"
        "services:       db files\n"
        "ethers:         db files\n"
        "rpc:            db files\n"
        "\n"
        "netgroup:       nis\n",
        encoding="utf-8",
    )

    # /etc/ssh/sshd_config
    ssh_dir = etc_dir / "ssh"
    ssh_dir.mkdir(parents=True, exist_ok=True)
    ssh_cfg = profile.get("ssh_config", {})
    (ssh_dir / "sshd_config").write_text(
        f"# Package generated configuration file\n"
        f"# See the sshd_config(5) manpage for details\n"
        f"\n"
        f"Port {ssh_cfg.get('port', 22)}\n"
        f"AddressFamily any\n"
        f"ListenAddress 0.0.0.0\n"
        f"ListenAddress ::\n"
        f"\n"
        f"HostKey /etc/ssh/ssh_host_rsa_key\n"
        f"HostKey /etc/ssh/ssh_host_ecdsa_key\n"
        f"HostKey /etc/ssh/ssh_host_ed25519_key\n"
        f"\n"
        f"SyslogFacility AUTH\n"
        f"LogLevel INFO\n"
        f"\n"
        f"LoginGraceTime 2m\n"
        f"PermitRootLogin {'yes' if ssh_cfg.get('permit_root_login', True) else 'no'}\n"
        f"StrictModes yes\n"
        f"MaxAuthTries 6\n"
        f"MaxSessions 10\n"
        f"\n"
        f"PubkeyAuthentication yes\n"
        f"AuthorizedKeysFile\t.ssh/authorized_keys\n"
        f"\n"
        f"PasswordAuthentication {'yes' if ssh_cfg.get('password_auth', True) else 'no'}\n"
        f"ChallengeResponseAuthentication no\n"
        f"\n"
        f"UsePAM yes\n"
        f"X11Forwarding yes\n"
        f"PrintMotd no\n"
        f"AcceptEnv LANG LC_*\n"
        f"Subsystem\tsftp\t/usr/lib/openssh/sftp-server\n",
        encoding="utf-8",
    )

    # /etc/motd (login banner) — OS-aware with randomized stats
    (output_dir / "etc" / "motd").write_text(
        _generate_motd(os_name, sys_info, profile),
        encoding="utf-8",
    )

    # /etc/default/locale
    default_dir = etc_dir / "default"
    default_dir.mkdir(parents=True, exist_ok=True)
    (default_dir / "locale").write_text(
        'LANG="en_US.UTF-8"\n', encoding="utf-8"
    )

    # /etc/timezone
    (etc_dir / "timezone").write_text(
        f"{sys_info.get('timezone', 'UTC')}\n", encoding="utf-8"
    )

    # /etc/sudoers.d/ entries
    sudoers_dir = etc_dir / "sudoers.d"
    sudoers_dir.mkdir(parents=True, exist_ok=True)
    for u in profile.get("users", []):
        if u.get("sudo_rules"):
            (sudoers_dir / u["name"]).write_text(
                u["sudo_rules"] + "\n", encoding="utf-8"
            )

    # /etc/crontab (from profile crontabs data)
    crontabs = profile.get("crontabs", {})
    if crontabs:
        crontab_lines = [
            "# /etc/crontab: system-wide crontab",
            "# Unlike any other crontab you don't have to run the `crontab'",
            "# command to install the new version when you edit this file",
            "# and files in /etc/cron.d. These files also have username fields,",
            "# that none of the other crontabs do.",
            "",
            "SHELL=/bin/sh",
            "PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin",
            "",
            "# m h dom mon dow user\tcommand",
            "17 *\t* * *\troot\tcd / && run-parts --report /etc/cron.hourly",
            "25 6\t* * *\troot\ttest -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.daily )",
            "47 6\t* * 7\troot\ttest -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.weekly )",
            "52 6\t1 * *\troot\ttest -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.monthly )",
            "#",
        ]
        # Append user-specific crontab entries
        for user, entries in crontabs.items():
            for entry_line in entries.strip().split("\n"):
                entry_line = entry_line.strip()
                if entry_line:
                    crontab_lines.append(f"{entry_line}")
        (etc_dir / "crontab").write_text(
            "\n".join(crontab_lines) + "\n", encoding="utf-8"
        )

    # /etc/systemd/system/*.service — generate unit files from profile services
    systemd_dir = etc_dir / "systemd" / "system"
    systemd_dir.mkdir(parents=True, exist_ok=True)
    for svc in profile.get("services", []):
        svc_name = svc["name"]
        # Normalize: strip suffixes like "-worker" for the service type
        svc_user = svc.get("user", "root")
        svc_cmd = svc.get("command", f"/usr/sbin/{svc_name}")
        svc_desc = svc_name.replace("-", " ").title()
        ports = svc.get("ports", [])
        unit_content = (
            f"[Unit]\n"
            f"Description={svc_desc}\n"
            f"After=network.target\n"
            f"\n"
            f"[Service]\n"
            f"Type=forking\n"
            f"User={svc_user}\n"
            f"ExecStart={svc_cmd}\n"
            f"Restart=on-failure\n"
            f"RestartSec=5s\n"
            f"\n"
            f"[Install]\n"
            f"WantedBy=multi-user.target\n"
        )
        (systemd_dir / f"{svc_name}.service").write_text(unit_content, encoding="utf-8")

    # Default .bashrc for root (if not in file_contents)
    if "/root/.bashrc" not in profile.get("file_contents", {}):
        root_dir = output_dir / "root"
        root_dir.mkdir(parents=True, exist_ok=True)
        (root_dir / ".bashrc").write_text(_default_bashrc(), encoding="utf-8")


def _ubuntu_kernel_build(kernel_version: str) -> str:
    """Generate a realistic Ubuntu kernel build string for the given version."""
    # Map kernel families to plausible Ubuntu build numbers
    builds = {
        "5.4.0": ("#187-Ubuntu SMP Thu Nov 23 14:52:28 UTC 2023", "Ubuntu"),
        "5.15.0": ("#105-Ubuntu SMP Thu Dec  7 10:03:36 UTC 2023", "Ubuntu"),
        "6.2.0": ("#36-Ubuntu SMP PREEMPT_DYNAMIC Mon Dec 18 18:17:01 UTC 2023", "Ubuntu"),
        "6.5.0": ("#44-Ubuntu SMP PREEMPT_DYNAMIC Fri Jan 12 11:17:42 UTC 2024", "Ubuntu"),
    }
    # Match on the major.minor.patch prefix
    prefix = ".".join(kernel_version.split(".")[:3]).rstrip("-generic")
    if prefix in builds:
        return builds[prefix][0]
    # Fallback: generate a plausible build string
    return f"#187-Ubuntu SMP Thu Nov 23 14:52:28 UTC 2023"


def _ubuntu_codename(version_id: str) -> str:
    """Map Ubuntu version to codename."""
    codenames = {
        "24.04": "noble", "22.04": "jammy", "20.04": "focal",
        "18.04": "bionic", "16.04": "xenial",
    }
    return codenames.get(version_id, "focal")


def _default_bashrc() -> str:
    """Return a realistic default .bashrc for root."""
    return """# ~/.bashrc: executed by bash(1) for non-login shells.

# If not running interactively, don't do anything
[ -z "$PS1" ] && return

# don't put duplicate lines or lines starting with space in the history.
HISTCONTROL=ignoreboth

# append to the history file, don't overwrite it
shopt -s histappend

HISTSIZE=1000
HISTFILESIZE=2000

# check the window size after each command
shopt -s checkwinsize

# set a fancy prompt
PS1='${debian_chroot:+($debian_chroot)}\\u@\\h:\\w\\$ '

# enable color support of ls
if [ -x /usr/bin/dircolors ]; then
    test -r ~/.dircolors && eval "$(dircolors -b ~/.dircolors)" || eval "$(dircolors -b)"
    alias ls='ls --color=auto'
    alias grep='grep --color=auto'
fi

alias ll='ls -alF'
alias la='ls -A'
alias l='ls -CF'
"""


# ---------------------------------------------------------------------------
# txtcmds generation
# ---------------------------------------------------------------------------

def generate_txtcmds(profile: dict, output_dir: Path) -> None:
    """Generate static command output files for Cowrie's txtcmds system."""
    sys_info = profile.get("system", {})
    hostname = sys_info.get("hostname", "localhost")
    kernel = sys_info.get("kernel_version", "5.4.0-generic")
    arch = sys_info.get("arch", "x86_64")
    os_name = sys_info.get("os", "Linux")
    distro = os_name.split()[0] if os_name else "Linux"

    cmds = {}

    # Build a realistic Ubuntu kernel build string
    # e.g., "5.4.0-169-generic" → "#187-Ubuntu SMP Thu Nov 23 14:52:28 UTC 2023"
    kernel_build = _ubuntu_kernel_build(kernel)

    # uname -a (matches real Ubuntu format)
    cmds["usr/bin/uname"] = (
        f"Linux {hostname} {kernel} {kernel_build} {arch} {arch} {arch} GNU/Linux\n"
    )

    # hostname
    cmds["usr/bin/hostname"] = f"{hostname}\n"

    # whoami (attacker logs in as root typically)
    cmds["usr/bin/whoami"] = "root\n"

    # id
    cmds["usr/bin/id"] = "uid=0(root) gid=0(root) groups=0(root)\n"

    # uptime
    cmds["usr/bin/uptime"] = (
        " 14:23:01 up 47 days,  3:12,  1 user,"
        "  load average: 0.08, 0.03, 0.01\n"
    )

    # arch
    cmds["usr/bin/arch"] = f"{arch}\n"

    # ps aux — realistic VSZ/RSS values
    ps_lines = [
        "USER         PID %CPU %MEM    VSZ   RSS TTY"
        "      STAT START   TIME COMMAND"
    ]
    _vsz_rss = {
        "apache2": (171680, 5244), "mysqld": (1793204, 178432),
        "sshd": (72304, 5520), "cron": (8544, 3200),
        "dockerd": (1564832, 89424), "nginx": (141456, 4892),
    }
    for svc in profile.get("services", []):
        user = svc.get("user", "root")
        pid = svc.get("pid", 1)
        cmd_line = svc.get("command", svc["name"])
        svc_name = svc["name"].split("-")[0]  # "apache2-worker" → "apache2"
        vsz, rss = _vsz_rss.get(svc_name, (12345 + pid * 7, 6789 + pid * 3))
        mem_pct = round(rss / 4096000 * 100, 1)
        ps_lines.append(
            f"{user:<12} {pid:>5}  0.1 {mem_pct:>4}  {vsz:>7} {rss:>6} ?"
            f"        Ss   Jan01   0:42 {cmd_line}"
        )
    cmds["usr/bin/ps"] = "\n".join(ps_lines) + "\n"

    # ifconfig
    ifconfig_lines = []
    for iface in profile.get("network", {}).get("interfaces", []):
        if iface["name"] == "lo":
            ifconfig_lines.append(
                f"lo: flags=73<UP,LOOPBACK,RUNNING>  mtu 65536"
            )
        else:
            ifconfig_lines.append(
                f"{iface['name']}: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500"
            )
        ifconfig_lines.append(
            f"        inet {iface['ip']}"
            f"  netmask {iface.get('netmask', '255.255.255.0')}"
        )
        if iface.get("mac") and iface["mac"] != "00:00:00:00:00:00":
            ifconfig_lines.append(
                f"        ether {iface['mac']}  txqueuelen 1000  (Ethernet)"
            )
        ifconfig_lines.append(
            "        RX packets 1234567  bytes 123456789 (123.4 MB)"
        )
        ifconfig_lines.append(
            "        TX packets 987654  bytes 98765432 (98.7 MB)"
        )
        ifconfig_lines.append("")
    cmds["usr/sbin/ifconfig"] = "\n".join(ifconfig_lines) + "\n"

    # ip addr — iproute2-style output consistent with ifconfig above
    ip_lines = []
    for idx, iface in enumerate(
        profile.get("network", {}).get("interfaces", []), 1
    ):
        name = iface.get("name", f"eth{idx - 1}")
        ip_addr = iface.get("ip", "127.0.0.1")
        mask = iface.get("netmask", "255.255.255.0")
        mac = iface.get("mac", "00:00:00:00:00:00")
        cidr = sum(bin(int(x)).count("1") for x in mask.split("."))
        ip_parts = [int(x) for x in ip_addr.split(".")]
        mask_parts = [int(x) for x in mask.split(".")]
        bcast = ".".join(
            str(ip_parts[i] | (255 - mask_parts[i])) for i in range(4)
        )
        if name == "lo":
            ip_lines.append(
                f"{idx}: {name}: <LOOPBACK,UP,LOWER_UP> mtu 65536"
                f" qdisc noqueue state UNKNOWN group default qlen 1000"
            )
            ip_lines.append(
                "    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00"
            )
        else:
            ip_lines.append(
                f"{idx}: {name}: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500"
                f" qdisc fq_codel state UP group default qlen 1000"
            )
            ip_lines.append(
                f"    link/ether {mac} brd ff:ff:ff:ff:ff:ff"
            )
        ip_lines.append(
            f"    inet {ip_addr}/{cidr} brd {bcast}"
            f" scope global {name}"
        )
        ip_lines.append("       valid_lft forever preferred_lft forever")
    ip_output = "\n".join(ip_lines) + "\n"
    cmds["sbin/ip"] = ip_output
    cmds["usr/sbin/ip"] = ip_output
    cmds["usr/bin/ip"] = ip_output

    # netstat -tlnp — consistent with profile services, correct format
    netstat_lines = [
        "Active Internet connections (only servers)",
        "Proto Recv-Q Send-Q Local Address           Foreign Address         State       PID/Program name",
    ]
    for svc in profile.get("services", []):
        for port in svc.get("ports", []):
            local_addr = f"127.0.0.1:{port}" if port == 3306 else f"0.0.0.0:{port}"
            netstat_lines.append(
                f"tcp        0      0 {local_addr:<24}"
                f"0.0.0.0:*               LISTEN"
                f"      {svc.get('pid', 1)}/{svc['name']}"
            )
            netstat_lines.append(
                f"tcp6       0      0 :::{port:<21}"
                f":::*                    LISTEN"
                f"      {svc.get('pid', 1)}/{svc['name']}"
            )
    cmds["usr/bin/netstat"] = "\n".join(netstat_lines) + "\n"

    # df -h — use profile disk_layout if available, otherwise generic
    disk_layout = profile.get("disk_layout")
    if disk_layout:
        df_lines = ["Filesystem      Size  Used Avail Use% Mounted on"]
        for disk in disk_layout:
            fs = disk.get("filesystem", "/dev/sda1")
            size = disk.get("size", "50G")
            used = disk.get("used", "23G")
            mount = disk.get("mount", "/")
            # Parse sizes to compute avail and use%
            def _parse_size(s):
                s = s.strip()
                if s.endswith("G"):
                    return float(s[:-1])
                elif s.endswith("T"):
                    return float(s[:-1]) * 1024
                elif s.endswith("M"):
                    return float(s[:-1]) / 1024
                return float(s)
            try:
                size_g = _parse_size(size)
                used_g = _parse_size(used)
                avail_g = size_g - used_g
                use_pct = int(used_g / size_g * 100) if size_g > 0 else 0
                avail = f"{avail_g:.0f}G" if avail_g >= 1 else f"{avail_g * 1024:.0f}M"
            except (ValueError, ZeroDivisionError):
                avail = "10G"
                use_pct = 50
            df_lines.append(
                f"{fs:<16s}{size:>5s}  {used:>4s}  {avail:>5s}  {use_pct:>2d}% {mount}"
            )
        df_lines.append("tmpfs           2.0G     0  2.0G   0% /dev/shm")
        df_lines.append("tmpfs           393M  5.6M  388M   2% /run")
        cmds["usr/bin/df"] = "\n".join(df_lines) + "\n"
    else:
        cmds["usr/bin/df"] = (
            "Filesystem      Size  Used Avail Use% Mounted on\n"
            "/dev/sda1        50G   23G   25G  48% /\n"
            "tmpfs           2.0G     0  2.0G   0% /dev/shm\n"
            "tmpfs           393M  5.6M  388M   2% /run\n"
            "/dev/sda2       200G   89G  101G  47% /var\n"
        )

    # free -m
    cmds["usr/bin/free"] = (
        "              total        used        free      shared"
        "  buff/cache   available\n"
        "Mem:           3944        1247         312          56"
        "        2384        2421\n"
        "Swap:          2047         128        1919\n"
    )

    # last — show recent login history
    # Pull IPs from /etc/hosts lateral targets or network interfaces
    fake_ips = ["10.0.1.1"]
    for iface in profile.get("network", {}).get("interfaces", []):
        ip = iface.get("ip", "")
        if ip and ip not in ("127.0.0.1",):
            # Use the subnet gateway as a source
            parts = ip.rsplit(".", 1)
            fake_ips.append(parts[0] + ".1")
            fake_ips.append(parts[0] + "." + str(random.randint(50, 200)))
    # Deduplicate
    fake_ips = list(dict.fromkeys(fake_ips))

    nonroot_users = [u["name"] for u in profile.get("users", [])
                     if u.get("shell", "").endswith(("/bash", "/sh", "/zsh"))
                     and u["name"] != "root"]
    login_users = ["root"] + nonroot_users[:2]

    last_lines = []
    days_back = [0, 0, 1, 2, 3, 5, 7, 12, 15, 20]
    for i, d in enumerate(days_back[:random.randint(6, 10)]):
        user = login_users[i % len(login_users)]
        ip = fake_ips[i % len(fake_ips)]
        # Approximate dates going backwards
        ts_offset = d * 86400 + random.randint(0, 43200)
        import time as _time
        login_time = _time.time() - ts_offset
        lt = _time.localtime(login_time)
        day_str = _time.strftime("%a %b %d %H:%M", lt)
        duration = f"{random.randint(0, 8):02d}:{random.randint(0, 59):02d}" if d > 0 else "  still logged in"
        last_lines.append(f"{user:<10s} pts/{i:<3d} {ip:<16s} {day_str}   - {day_str}  ({duration})")
    last_lines.append("")
    last_lines.append(f"wtmp begins {_time.strftime('%a %b %d %H:%M:%S %Y', _time.localtime(_time.time() - 90 * 86400))}")
    cmds["usr/bin/last"] = "\n".join(last_lines) + "\n"

    # w — show currently logged-in users
    w_header = (
        f" {_time.strftime('%H:%M:%S', _time.localtime())} up 47 days,  3:12,"
        f"  1 user,  load average: 0.08, 0.03, 0.01"
    )
    w_lines = [
        w_header,
        "USER     TTY      FROM             LOGIN@   IDLE   JCPU   PCPU WHAT",
        f"root     pts/0    {fake_ips[0]:<16s} 14:23    0.00s  0.04s  0.00s w",
    ]
    cmds["usr/bin/w"] = "\n".join(w_lines) + "\n"

    # Profile-defined extra txtcmds (e.g. grafana-cli --version)
    for cmd_path, output in profile.get("extra_txtcmds", {}).items():
        cmds[cmd_path] = output

    # Write all txtcmds
    for cmd_path, output in cmds.items():
        target = output_dir / cmd_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(output.encode("utf-8"))


# ---------------------------------------------------------------------------
# Cowrie config overrides
# ---------------------------------------------------------------------------

def generate_cowrie_config_overrides(profile: dict) -> dict:
    """Return cowrie.cfg key-value overrides derived from the profile."""
    sys_info = profile.get("system", {})
    arch = sys_info.get("arch", "x86_64")
    return {
        "honeypot.hostname": sys_info.get("hostname", "svr04"),
        "shell.kernel_version": sys_info.get("kernel_version", "5.4.0-generic"),
        "shell.arch": f"linux-{'x64' if arch == 'x86_64' else 'arm'}-lsb",
        "shell.hardware_platform": arch,
        "shell.operating_system": "GNU/Linux",
    }


# ---------------------------------------------------------------------------
# Cowrie userdb.txt
# ---------------------------------------------------------------------------

def generate_userdb(profile: dict, output_path: Path) -> None:
    """
    Generate Cowrie's userdb.txt from the profile's ssh_config.accepted_passwords.

    Format per line: username:uid:password
    A line with '*' as password denies all attempts for that user.
    """
    lines = []
    accepted = profile.get("ssh_config", {}).get("accepted_passwords", {})
    for username, passwords in accepted.items():
        uid = 0
        for u in profile.get("users", []):
            if u["name"] == username:
                uid = u["uid"]
                break
        for pw in passwords:
            lines.append(f"{username}:{uid}:{pw}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# LLM system prompt
# ---------------------------------------------------------------------------

def _extract_db_version(profile: dict, engine: str, fallback: str) -> str:
    """Extract the spoofed DB version from packages or services."""
    search_terms = (
        ("mysql-server", "mysql", "mariadb") if engine == "mysql"
        else ("postgresql", "postgres")
    )
    for pkg in profile.get("installed_packages", []):
        name = pkg["name"].lower()
        if any(t in name for t in search_terms):
            version = pkg.get("version", "")
            if version:
                import re as _re
                return _re.split(r"[-+~]", version)[0]
    return fallback


def generate_llm_prompt(profile: dict) -> str:
    """Build the LLM fallback system prompt from the profile."""
    sys_info = profile.get("system", {})

    # Services
    services_str = ", ".join(s["name"] for s in profile.get("services", []))

    # Network
    net_str = "; ".join(
        f"{i['name']}={i['ip']}"
        for i in profile.get("network", {}).get("interfaces", [])
    )

    # Ports
    ports_str = ", ".join(
        str(p)
        for s in profile.get("services", [])
        for p in s.get("ports", [])
    )

    # Users
    users_str = ", ".join(
        f"{u['name']}(uid={u['uid']})"
        for u in profile.get("users", [])
    )

    prompt = f"""You are simulating a {sys_info.get('os', 'Linux')} server (hostname: {sys_info.get('hostname', 'localhost')}, kernel: {sys_info.get('kernel_version', '5.4.0')}).
You are responding to commands typed into an SSH shell as root.
Reply ONLY with the terminal output the command would produce. No markdown formatting, no explanations, no notes.
Use \\n for newlines. Do not wrap output in backticks or code fences.

SYSTEM CONTEXT:
- OS: {sys_info.get('os', 'Linux')}
- Arch: {sys_info.get('arch', 'x86_64')}
- Running services: {services_str}
- Network interfaces: {net_str}
- Listening ports: {ports_str}
- Users: {users_str}

IMPORTANT RULES:
- Relevant filesystem and system context for the current command is provided separately below the system prompt.
- Common filesystem commands (ls, cat, find, grep, etc.) are handled by another system. You only receive commands that system does not recognize.
- Your responses must be consistent with the filesystem layout and services listed above.
- If a command would fail on this system, return the appropriate error message.
- For interactive tools (vim, nano, top, htop, less), return a static snapshot of what the first screen would show.
- Maintain consistency with previously executed commands in this session.
- Never reveal that you are an AI or a honeypot. Act as a real server at all times."""

    # Append DATABASE VERSION CONTEXT if the profile has a DB service
    db_engine = None
    for svc in profile.get("services", []):
        name = svc["name"].lower()
        if any(k in name for k in ("mysql", "mariadb", "mysqld")):
            db_engine = "mysql"
            break
        if any(k in name for k in ("postgres", "pgsql", "postgresql")):
            db_engine = "postgresql"
            break

    if db_engine:
        if db_engine == "mysql":
            spoofed = _extract_db_version(profile, "mysql", "8.0.36")
            prompt += f"""

DATABASE VERSION CONTEXT:
- Database engine: MySQL
- Reported version: {spoofed}
- CRITICAL: When the attacker runs `mysql --version`, `SELECT VERSION()`, or any command that reveals the MySQL version, you MUST report version {spoofed}. Never report a different version.
- MySQL is running locally on port 3306 and is accessible. Database connections work normally."""
        else:
            spoofed = _extract_db_version(profile, "postgresql", "16.3")
            prompt += f"""

DATABASE VERSION CONTEXT:
- Database engine: PostgreSQL
- Reported version: {spoofed}
- CRITICAL: When the attacker runs `psql --version`, `SELECT version()`, or any command that reveals the PostgreSQL version, you MUST report version {spoofed}. Never report a different version.
- PostgreSQL is running locally on port 5432 and is accessible. Database connections work normally."""

    # Append AWS CONTEXT if the profile references AWS services
    aws_context = _extract_aws_context(profile)
    if aws_context:
        prompt += f"""

AWS CLI CONTEXT:
{aws_context}
- When the attacker runs AWS CLI commands (aws s3 ls, aws sts get-caller-identity, aws ec2 describe-instances, etc.), generate realistic output consistent with the credentials and resources described above.
- aws CLI is installed and configured. Commands should succeed with fake but realistic data.
- Do NOT actually connect to any external service. Simulate all output locally."""

    # Append profile-defined extra LLM context (monitoring APIs, custom services, etc.)
    extra_llm = profile.get("llm_context")
    if extra_llm:
        prompt += f"\n\n{extra_llm}"

    return prompt


def _extract_aws_context(profile: dict) -> str | None:
    """Extract AWS context from profile file_contents if AWS references exist."""
    file_contents = profile.get("file_contents", {})
    packages = profile.get("installed_packages", [])

    # Check if AWS is referenced anywhere in the profile
    has_aws = any("awscli" in p.get("name", "").lower() or "aws-cli" in p.get("name", "").lower()
                  for p in packages)
    if not has_aws:
        # Check file contents for AWS references
        for content in file_contents.values():
            if "aws " in content or "AWS_ACCESS_KEY" in content or "s3://" in content:
                has_aws = True
                break

    if not has_aws:
        return None

    lines = []

    # Extract AWS credentials from .env files or ~/.aws/credentials
    access_key = None
    secret_key = None
    region = "us-east-1"
    s3_buckets = []

    import re as _re
    for path, content in file_contents.items():
        # AWS access key
        m = _re.search(r'AWS_ACCESS_KEY_ID\s*=\s*(\S+)', content)
        if m:
            access_key = m.group(1)
        m = _re.search(r'aws_access_key_id\s*=\s*(\S+)', content)
        if m:
            access_key = m.group(1)

        # AWS secret key
        m = _re.search(r'AWS_SECRET_ACCESS_KEY\s*=\s*(\S+)', content)
        if m:
            secret_key = m.group(1)
        m = _re.search(r'aws_secret_access_key\s*=\s*(\S+)', content)
        if m:
            secret_key = m.group(1)

        # Region
        m = _re.search(r'region\s*=\s*(\S+)', content)
        if m:
            region = m.group(1)

        # S3 buckets (both s3://bucket-name and S3_BUCKET=bucket-name)
        for bucket_match in _re.finditer(r's3://([a-zA-Z0-9._-]+)', content):
            bucket = bucket_match.group(1)
            if bucket not in s3_buckets:
                s3_buckets.append(bucket)
        m = _re.search(r'S3_BUCKET\s*=\s*(\S+)', content)
        if m and m.group(1) not in s3_buckets:
            s3_buckets.append(m.group(1))

    if access_key:
        lines.append(f"- AWS Access Key ID: {access_key}")
    if secret_key:
        lines.append(f"- AWS Secret Access Key: {secret_key[:4]}...{secret_key[-4:]}")
    lines.append(f"- AWS Region: {region}")
    if s3_buckets:
        lines.append(f"- S3 Buckets: {', '.join(s3_buckets)}")
    lines.append(f"- Fake AWS Account ID: 123456789012")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Full deployment
# ---------------------------------------------------------------------------

def _enrich_aws_context(profile: dict) -> None:
    """Ensure profiles referencing AWS have consistent awscli package and config files.

    Mutates *profile* in-place: adds awscli to installed_packages, adds
    ~/.aws/credentials and ~/.aws/config to directory_tree + file_contents
    when the profile already contains AWS references (S3 buckets, access keys)
    but is missing the CLI package or config files.
    """
    import re as _re

    file_contents = profile.get("file_contents", {})
    packages = profile.setdefault("installed_packages", [])
    dir_tree = profile.setdefault("directory_tree", {})

    # Detect AWS references in file_contents
    has_aws_refs = False
    access_key = None
    secret_key = None
    region = "us-east-1"
    for content in file_contents.values():
        if "aws " in content or "AWS_ACCESS_KEY" in content or "s3://" in content:
            has_aws_refs = True
        m = _re.search(r'AWS_ACCESS_KEY_ID\s*=\s*(\S+)', content)
        if m:
            access_key = m.group(1)
        m = _re.search(r'aws_access_key_id\s*=\s*(\S+)', content)
        if m:
            access_key = m.group(1)
        m = _re.search(r'AWS_SECRET_ACCESS_KEY\s*=\s*(\S+)', content)
        if m:
            secret_key = m.group(1)
        m = _re.search(r'aws_secret_access_key\s*=\s*(\S+)', content)
        if m:
            secret_key = m.group(1)
        m = _re.search(r'region\s*=\s*([\w-]+)', content)
        if m and m.group(1) != "us-east-1":
            region = m.group(1)

    if not has_aws_refs:
        return

    # Add awscli package if missing
    pkg_names = {p.get("name", "").lower() for p in packages}
    if "awscli" not in pkg_names and "aws-cli" not in pkg_names:
        packages.append({"name": "awscli", "version": "1.27.162-1"})

    # Add ~/.aws directory and files if missing
    if access_key and secret_key:
        # Add to /root directory tree
        root_entries = dir_tree.get("/root", [])
        aws_dir_exists = any(e.get("name") == ".aws" for e in root_entries)
        if not aws_dir_exists:
            root_entries.append({
                "name": ".aws", "type": "dir", "permissions": "0700",
                "owner": "root", "group": "root"
            })
            dir_tree["/root"] = root_entries

        # Add /root/.aws contents
        if "/root/.aws" not in dir_tree:
            dir_tree["/root/.aws"] = [
                {"name": "credentials", "type": "file", "permissions": "0600",
                 "owner": "root", "group": "root", "size": 116},
                {"name": "config", "type": "file", "permissions": "0600",
                 "owner": "root", "group": "root", "size": 43},
            ]

        # Add file contents
        if "/root/.aws/credentials" not in file_contents:
            file_contents["/root/.aws/credentials"] = (
                f"[default]\n"
                f"aws_access_key_id = {access_key}\n"
                f"aws_secret_access_key = {secret_key}"
            )
        if "/root/.aws/config" not in file_contents:
            file_contents["/root/.aws/config"] = (
                f"[default]\n"
                f"region = {region}\n"
                f"output = json"
            )


def generate_cmdoutput(profile: dict, output_path: Path) -> None:
    """Generate cmdoutput.json for Cowrie's native ps handler (server.process)."""
    _vsz_rss = {
        "apache2": (171680, 5244), "mysqld": (1793204, 178432),
        "sshd": (72304, 5520), "cron": (8544, 3200),
        "dockerd": (1564832, 89424), "nginx": (141456, 4892),
        "node_exporter": (24680, 8120), "rsyncd": (8840, 3400),
        "borg": (45200, 18900), "postfix": (82400, 6200),
        "rsyslogd": (28428, 1508), "dovecot": (36200, 4800),
        "named": (98400, 22100), "redis": (58320, 12400),
        "postgres": (142800, 18600), "containerd": (842000, 42800),
    }

    ps_entries = []
    # Standard kernel/init entries
    ps_entries.append({
        "USER": "root", "PID": 1, "CPU": 0.0, "MEM": 0.4,
        "VSZ": 167340, "RSS": 11200, "TTY": "?", "STAT": "Ss",
        "START": "Jan01", "TIME": 0.48, "COMMAND": "/sbin/init"
    })
    ps_entries.append({
        "USER": "root", "PID": 2, "CPU": 0.0, "MEM": 0.0,
        "VSZ": 0, "RSS": 0, "TTY": "?", "STAT": "S",
        "START": "Jan01", "TIME": 0.00, "COMMAND": "[kthreadd]"
    })

    # Profile services
    for svc in profile.get("services", []):
        pid = svc.get("pid", 100)
        svc_base = svc["name"].split("-")[0]
        vsz, rss = _vsz_rss.get(svc_base, (12345 + pid * 7, 6789 + pid * 3))
        mem_pct = round(rss / 4096000 * 100, 1)
        ps_entries.append({
            "USER": svc.get("user", "root"),
            "PID": pid,
            "CPU": 0.1,
            "MEM": mem_pct,
            "VSZ": vsz,
            "RSS": rss,
            "TTY": "?",
            "STAT": "Ss",
            "START": "Jan01",
            "TIME": 0.42,
            "COMMAND": svc.get("command", svc["name"])
        })

    cmdoutput = {"command": {"ps": ps_entries}}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(cmdoutput, indent=2), encoding="utf-8")


def generate_remote_files(profile: dict, honeyfs_dir: Path, etc_dir: Path) -> None:
    """Deploy remote_files content to honeyfs and build a lookup index.

    Text files are written to ``honeyfs/_remote/<host>/<path>`` so the SCP
    handler can serve them.  An index at ``etc/remote_files.json`` maps
    ``host + path`` to the honeyfs-relative path and file size.
    """
    remote_files = profile.get("remote_files")
    if not remote_files:
        return

    index: dict[str, dict[str, dict]] = {}  # {host: {path: {size, honeyfs_path}}}

    for host, files in remote_files.items():
        for rpath, meta in files.items():
            content_type = meta.get("content_type", "binary")
            size = meta.get("size", 4096)
            rel = f"_remote/{host}{rpath}"
            disk_path = honeyfs_dir / rel

            disk_path.parent.mkdir(parents=True, exist_ok=True)

            if content_type == "text" and meta.get("content"):
                disk_path.write_text(meta["content"], encoding="utf-8")
                size = disk_path.stat().st_size
            else:
                # Binary stub: minimal content so the file exists on disk
                import struct, gzip as _gzip, io as _io
                if rpath.endswith((".gz", ".tgz")):
                    buf = _io.BytesIO()
                    with _gzip.GzipFile(fileobj=buf, mode="wb") as gz:
                        gz.write(b"\x00" * min(size, 1024))
                    stub = buf.getvalue()
                else:
                    stub = b"\x00" * min(size, 4096)
                disk_path.write_bytes(stub)
                size = max(size, len(stub))

            index.setdefault(host, {})[rpath] = {
                "size": size,
                "honeyfs_path": rel,
            }

    # Write index
    etc_dir.mkdir(parents=True, exist_ok=True)
    (etc_dir / "remote_files.json").write_text(
        json.dumps(index, indent=2), encoding="utf-8"
    )


_MOTD_HELP_URLS = {
    "ubuntu": (
        " * Documentation:  https://help.ubuntu.com\n"
        " * Management:     https://landscape.canonical.com\n"
        " * Support:        https://ubuntu.com/advantage\n"
    ),
    "debian": (
        " * Documentation:  https://www.debian.org/doc\n"
        " * Wiki:           https://wiki.debian.org\n"
        " * Support:        https://www.debian.org/support\n"
    ),
    "centos": (
        " * Documentation:  https://docs.centos.org\n"
        " * Community:      https://centos.org/forums\n"
        " * Bug Reports:    https://bugs.centos.org\n"
    ),
    "rhel": (
        " * Documentation:  https://access.redhat.com/documentation\n"
        " * Support:        https://access.redhat.com/support\n"
        " * Knowledge Base: https://access.redhat.com/solutions\n"
    ),
}

_MOTD_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_MOTD_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _detect_os_family(os_name: str) -> str:
    """Detect OS family from the profile os_name string."""
    lower = os_name.lower()
    for family in ("ubuntu", "debian", "centos", "rhel"):
        if family in lower:
            return family
    if "red hat" in lower:
        return "rhel"
    return "ubuntu"  # default fallback


def _generate_motd(os_name: str, sys_info: dict, profile: dict) -> str:
    """Generate a realistic, OS-appropriate MOTD with randomized system stats."""
    os_family = _detect_os_family(os_name)
    arch = sys_info.get("arch", "x86_64")
    ip = profile.get("network", {}).get("interfaces", [{}])[0].get("ip", "10.0.1.15")

    help_urls = _MOTD_HELP_URLS.get(os_family, _MOTD_HELP_URLS["ubuntu"])

    # Randomize system stats
    load = round(random.uniform(0.01, 0.95), 2)
    processes = random.randint(95, 280)
    disk_pct = round(random.uniform(15.0, 65.0), 1)
    disk_total = random.choice(["19.56GB", "49.10GB", "98.30GB", "196.50GB"])
    memory_pct = random.randint(20, 75)
    swap_pct = random.randint(0, 15)
    updates = random.choice([0, 0, 0, 1, 2, 5, 12])

    # Randomize timestamp
    day_name = random.choice(_MOTD_DAYS)
    month = random.choice(_MOTD_MONTHS)
    day_num = random.randint(1, 28)
    hour = random.randint(0, 23)
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    timestamp = f"{day_name} {month} {day_num:2d} {hour:02d}:{minute:02d}:{second:02d} UTC 2026"

    last_day = random.choice(_MOTD_DAYS)
    last_month = random.choice(_MOTD_MONTHS)
    last_day_num = random.randint(1, 28)
    last_hour = random.randint(0, 23)
    last_minute = random.randint(0, 59)
    last_second = random.randint(0, 59)
    last_login = f"{last_day} {last_month} {last_day_num:2d} {last_hour:02d}:{last_minute:02d}:{last_second:02d} 2026"
    last_from = f"10.0.{random.randint(0, 5)}.{random.randint(1, 254)}"

    update_line = (
        f"{updates} updates can be applied immediately."
        if updates > 0
        else "0 updates can be applied immediately."
    )

    return (
        f"Welcome to {os_name} ({arch})\n"
        f"\n"
        f"{help_urls}"
        f"\n"
        f"  System information as of {timestamp}\n"
        f"\n"
        f"  System load:  {load:<19}Processes:           {processes}\n"
        f"  Usage of /:   {disk_pct}% of {disk_total:<9}Users logged in:     0\n"
        f"  Memory usage: {memory_pct}%{' ' * (16 - len(str(memory_pct)))}IPv4 address for eth0: {ip}\n"
        f"  Swap usage:   {swap_pct}%\n"
        f"\n"
        f"{update_line}\n"
        f"\n"
        f"Last login: {last_login} from {last_from}\n"
    )


def _generate_encrypted_files(profile: dict, honeyfs_dir: Path) -> None:
    """Generate GPG-encrypted files from ``_encrypted_credentials`` metadata.

    Called during deploy to produce binary .gpg files in honeyfs that the
    attacker must exfiltrate and decrypt (Tier 2 credential difficulty).
    """
    import subprocess

    for entry in profile.get("_encrypted_credentials", []):
        output_path = honeyfs_dir / entry["path"].lstrip("/")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if entry["method"] == "gpg-symmetric":
            subprocess.run(
                [
                    "gpg", "--batch", "--yes",
                    "--passphrase", entry["passphrase"],
                    "--symmetric", "--cipher-algo", "AES256",
                    "--output", str(output_path),
                ],
                input=entry["plaintext"].encode(),
                capture_output=True,
            )
        elif entry["method"] == "openssl":
            subprocess.run(
                [
                    "openssl", "enc", "-aes-256-cbc", "-pbkdf2",
                    "-pass", f"pass:{entry['passphrase']}",
                    "-out", str(output_path),
                ],
                input=entry["plaintext"].encode(),
                capture_output=True,
            )


def _generate_protected_archives(profile: dict, honeyfs_dir: Path) -> None:
    """Generate password-protected ZIP files from ``_protected_archives`` metadata.

    Called during deploy to produce .zip files in honeyfs that the attacker
    must find the password for (Tier 3 credential difficulty).

    Uses the ``zip`` CLI because Python's zipfile module cannot write
    encrypted archives.
    """
    import subprocess
    import tempfile

    for entry in profile.get("_protected_archives", []):
        output_path = honeyfs_dir / entry["archive_path"].lstrip("/")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write inner file to a temp location, then zip it
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=f"_{entry['inner_file']}", delete=False,
        ) as tmp:
            tmp.write(entry["content"])
            tmp_path = tmp.name

        try:
            subprocess.run(
                [
                    "zip", "-j", "-P", entry["zip_password"],
                    str(output_path), tmp_path,
                ],
                capture_output=True,
            )
            # Rename the inner file inside the zip to the desired name
            # (zip -j strips path, uses the tmp filename — rename via zipnote
            # isn't worth the complexity; the attacker will see the content)
        finally:
            Path(tmp_path).unlink(missing_ok=True)


def deploy_profile(profile: dict, cowrie_base: Path) -> dict:
    """
    Full deployment: generate all Cowrie artifacts from a filesystem profile.

    Args:
        profile: parsed filesystem profile dict
        cowrie_base: path to the cowrie_config/ directory

    Returns:
        dict with paths to generated artifacts and the LLM prompt string.
    """
    # 0. Enrich profile with consistent AWS context if needed
    _enrich_aws_context(profile)

    # 1. Generate and save pickle
    tree = profile_to_pickle(profile)
    pickle_path = cowrie_base / "share" / "fs.pickle"
    pickle_path.parent.mkdir(parents=True, exist_ok=True)
    with open(pickle_path, "wb") as f:
        pickle.dump(tree, f, protocol=2)

    # 2. Generate honeyfs
    honeyfs_path = cowrie_base / "honeyfs"
    if honeyfs_path.exists():
        shutil.rmtree(honeyfs_path)
    generate_honeyfs(profile, honeyfs_path)

    # 2b. Generate encrypted files / protected archives (credential tiers)
    _generate_encrypted_files(profile, honeyfs_path)
    _generate_protected_archives(profile, honeyfs_path)

    # 3. Generate txtcmds
    txtcmds_path = cowrie_base / "share" / "txtcmds"
    if txtcmds_path.exists():
        shutil.rmtree(txtcmds_path)
    generate_txtcmds(profile, txtcmds_path)

    # 4. Generate userdb
    userdb_path = cowrie_base / "etc" / "userdb.txt"
    generate_userdb(profile, userdb_path)

    # 5. Generate LLM prompt
    llm_prompt = generate_llm_prompt(profile)
    prompt_path = cowrie_base / "etc" / "llm_prompt.txt"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(llm_prompt, encoding="utf-8")

    # 6. Write profile JSON for runtime use by LLMFallbackHandler's pre-query system
    profile_path = cowrie_base / "etc" / "profile.json"
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")

    # 7. Generate cmdoutput.json for native ps handler
    cmdoutput_path = cowrie_base / "share" / "cowrie" / "cmdoutput.json"
    generate_cmdoutput(profile, cmdoutput_path)

    # 8. Deploy remote files for SCP pull simulation
    generate_remote_files(profile, honeyfs_path, cowrie_base / "etc")

    # 9. Config overrides
    overrides = generate_cowrie_config_overrides(profile)

    return {
        "pickle_path": str(pickle_path),
        "honeyfs_path": str(honeyfs_path),
        "txtcmds_path": str(txtcmds_path),
        "userdb_path": str(userdb_path),
        "prompt_path": str(prompt_path),
        "profile_path": str(profile_path),
        "cmdoutput_path": str(cmdoutput_path),
        "config_overrides": overrides,
        "llm_prompt": llm_prompt,
    }
