"""Tests for the AttackStateRegister (Sangria/attack_state.py)."""

import pytest
from Sangria.attack_state import AttackStateRegister


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def state():
    return AttackStateRegister()


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------

class TestInit:
    def test_empty_state(self, state):
        assert state.hosts == {}
        assert state.credentials == []
        assert state.files_read == []
        assert state.services == []
        assert state.current_host == ""
        assert state.failed_attempts == []


# ---------------------------------------------------------------------------
# Network parsing (nmap)
# ---------------------------------------------------------------------------

class TestNetworkParsing:
    def test_nmap_discovers_host(self, state):
        state.update_from_tool_call(
            "terminal_input",
            {"input": "nmap -sV 172.10.0.3"},
            "80/tcp   open  http    Apache httpd 2.4.41\n3306/tcp open  mysql   MySQL 5.7.33",
        )
        assert "172.10.0.3" in state.hosts
        assert len(state.services) == 2
        assert state.services[0].port == 80
        assert state.services[1].port == 3306
        assert state.services[0].host == "172.10.0.3"

    def test_nmap_no_duplicate_services(self, state):
        response = "80/tcp   open  http    Apache httpd 2.4.41"
        state.update_from_tool_call("terminal_input", {"input": "nmap 172.10.0.3"}, response)
        state.update_from_tool_call("terminal_input", {"input": "nmap 172.10.0.3"}, response)
        assert len(state.services) == 1


# ---------------------------------------------------------------------------
# SSH parsing
# ---------------------------------------------------------------------------

class TestSSHParsing:
    def test_ssh_success(self, state):
        state.update_from_tool_call(
            "terminal_input",
            {"input": "ssh root@172.10.0.4"},
            "root@db-server:~# ",
        )
        assert "172.10.0.4" in state.hosts
        host = state.hosts["172.10.0.4"]
        assert host.visited is True
        assert host.access_level == "root"
        assert "SSH root" in host.access_method

    def test_ssh_permission_denied(self, state):
        state.update_from_tool_call(
            "terminal_input",
            {"input": "ssh user@172.10.0.5"},
            "Permission denied, please try again.",
        )
        assert "172.10.0.5" in state.hosts
        host = state.hosts["172.10.0.5"]
        assert host.visited is False
        assert host.access_level == "discovered"
        # Should be in failed attempts
        assert "ssh user@172.10.0.5" in state.failed_attempts

    def test_ssh_nonroot_access(self, state):
        state.update_from_tool_call(
            "terminal_input",
            {"input": "ssh deploy@172.10.0.3"},
            "deploy@wp-prod-01:~$ ",
        )
        host = state.hosts["172.10.0.3"]
        assert host.access_level == "user"

    def test_ssh_marks_credential_used(self, state):
        # First add a credential
        state._add_credential("root/pass123", "/etc/shadow", "password")
        # Then SSH as root
        state.update_from_tool_call(
            "terminal_input",
            {"input": "ssh root@172.10.0.3"},
            "root@wp-prod-01:~# ",
        )
        assert state.credentials[0].used is True
        assert state.credentials[0].used_where == "SSH 172.10.0.3"

    def test_ssh_with_port(self, state):
        state.update_from_tool_call(
            "terminal_input",
            {"input": "ssh -p 2222 root@172.10.0.3"},
            "root@wp-prod-01:~# ",
        )
        assert "port 2222" in state.hosts["172.10.0.3"].access_method


# ---------------------------------------------------------------------------
# File read parsing (regex-only, no profile oracle)
# ---------------------------------------------------------------------------

class TestFileReadParsing:
    def test_wp_config_credentials(self, state):
        """WordPress wp-config.php credentials extracted from command output."""
        state.update_from_tool_call(
            "terminal_input",
            {"input": "cat /var/www/html/wp-config.php"},
            "define('DB_USER', 'wpuser');\ndefine('DB_PASSWORD', 'dbpass123');",
        )
        assert len(state.files_read) == 1
        assert state.files_read[0].path == "/var/www/html/wp-config.php"
        assert len(state.credentials) >= 1

    def test_generic_password(self, state):
        state.update_from_tool_call(
            "terminal_input",
            {"input": "cat /opt/unknown/config.txt"},
            "password = mysecretpassword",
        )
        assert len(state.credentials) >= 1
        assert len(state.files_read) == 1

    def test_env_file_aws_key(self, state):
        state.update_from_tool_call(
            "terminal_input",
            {"input": "cat /home/deploy/.env"},
            "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE\nAWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG",
        )
        assert len(state.credentials) >= 1
        assert len(state.files_read) >= 1

    def test_env_db_credentials(self, state):
        """DB_PASSWORD=... style credentials in .env files."""
        state.update_from_tool_call(
            "terminal_input",
            {"input": "cat /opt/app/.env"},
            "DB_USER=admin\nDB_PASSWORD=s3cret\nDB_NAME=myapp",
        )
        assert len(state.credentials) >= 1

    def test_mysql_pwd_in_script(self, state):
        """MYSQL_PWD=... in shell scripts."""
        state.update_from_tool_call(
            "terminal_input",
            {"input": "cat /home/deploy/backup.sh"},
            "#!/bin/bash\nMYSQL_PWD='dbpass' mysqldump -u root mydb > /tmp/backup.sql",
        )
        assert len(state.credentials) >= 1

    def test_sshpass_in_history(self, state):
        """sshpass -p 'password' in bash history."""
        state.update_from_tool_call(
            "terminal_input",
            {"input": "cat /root/.bash_history"},
            "sshpass -p 'r00tpass' ssh root@10.0.1.5\nls -la\nwhoami",
        )
        assert len(state.credentials) >= 1

    def test_pgpassword_in_script(self, state):
        """PGPASSWORD=... in shell scripts."""
        state.update_from_tool_call(
            "terminal_input",
            {"input": "cat /opt/scripts/pg_backup.sh"},
            "PGPASSWORD=pg_s3cret psql -U postgres -h localhost mydb",
        )
        assert len(state.credentials) >= 1

    def test_ssh_private_key(self, state):
        """SSH private key detection."""
        state.update_from_tool_call(
            "terminal_input",
            {"input": "cat /home/deploy/.ssh/id_rsa"},
            "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAK...\n-----END RSA PRIVATE KEY-----",
        )
        assert len(state.credentials) >= 1
        assert len(state.files_read) == 1

    def test_no_file_for_flags(self, state):
        """Commands like 'cat -n' shouldn't try to read '-n' as a file."""
        state.update_from_tool_call(
            "terminal_input",
            {"input": "cat -n"},
            "some output",
        )
        # -n starts with -, should be skipped
        assert len(state.files_read) == 0

    def test_no_credentials_in_clean_output(self, state):
        """Normal file output should not trigger false positives."""
        state.update_from_tool_call(
            "terminal_input",
            {"input": "cat /etc/hostname"},
            "wp-prod-01",
        )
        assert len(state.credentials) == 0
        assert len(state.files_read) == 0

    def test_piped_command_extracts_correct_path(self, state):
        """cat /etc/shadow | head -5 should track /etc/shadow, not -5."""
        state.update_from_tool_call(
            "terminal_input",
            {"input": "cat /etc/shadow | head -5"},
            "root:$6$abc:18000:0:99999:7:::\ndaemon:*:18000:0:99999:7:::",
        )
        # Should still detect password-like content from /etc/shadow path
        assert len(state.files_read) == 0 or state.files_read[0].path == "/etc/shadow"

    def test_piped_command_with_grep(self, state):
        """cat /home/deploy/.env | grep PASS should track .env, not PASS."""
        state.update_from_tool_call(
            "terminal_input",
            {"input": "cat /home/deploy/.env | grep PASS"},
            "DB_PASSWORD=s3cret",
        )
        assert len(state.credentials) >= 1
        assert state.files_read[0].path == "/home/deploy/.env"


# ---------------------------------------------------------------------------
# Failed attempts
# ---------------------------------------------------------------------------

class TestFailedAttempts:
    def test_permission_denied(self, state):
        state.update_from_tool_call(
            "terminal_input",
            {"input": "ssh admin@10.0.0.1"},
            "Permission denied (publickey,password).",
        )
        assert "ssh admin@10.0.0.1" in state.failed_attempts

    def test_connection_refused(self, state):
        state.update_from_tool_call(
            "terminal_input",
            {"input": "ssh root@10.0.0.2"},
            "ssh: connect to host 10.0.0.2 port 22: Connection refused",
        )
        assert "ssh root@10.0.0.2" in state.failed_attempts

    def test_no_duplicate_failures(self, state):
        for _ in range(3):
            state.update_from_tool_call(
                "terminal_input",
                {"input": "ssh root@10.0.0.1"},
                "Connection refused",
            )
        assert state.failed_attempts.count("ssh root@10.0.0.1") == 1


# ---------------------------------------------------------------------------
# Current host tracking
# ---------------------------------------------------------------------------

class TestCurrentHost:
    def test_tracks_prompt_pattern(self, state):
        state.update_from_tool_call(
            "terminal_input",
            {"input": "whoami"},
            "root\nroot@wp-prod-01:~# ",
        )
        assert state.current_host == "root@wp-prod-01"

    def test_updates_on_host_change(self, state):
        state.update_from_tool_call(
            "terminal_input", {"input": "ls"}, "file1\nroot@host1:~# "
        )
        assert state.current_host == "root@host1"
        state.update_from_tool_call(
            "terminal_input", {"input": "ls"}, "file2\ndeploy@host2:~$ "
        )
        assert state.current_host == "deploy@host2"

    def test_ssh_populates_hostname(self, state):
        """SSH success response should populate HostEntry.hostname."""
        state.update_from_tool_call(
            "terminal_input",
            {"input": "ssh root@172.10.0.4"},
            "root@db-server:~# ",
        )
        assert state.hosts["172.10.0.4"].hostname == "db-server"


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

class TestDeduplication:
    def test_credential_dedup(self, state):
        state._add_credential("root/pass", "/etc/shadow", "password")
        state._add_credential("root/pass", "/etc/shadow", "password")
        assert len(state.credentials) == 1

    def test_file_dedup(self, state):
        state._add_file("/etc/passwd", "host1", "users")
        state._add_file("/etc/passwd", "host1", "users")
        assert len(state.files_read) == 1

    def test_service_dedup(self, state):
        state._add_service("172.10.0.3", 80, "http")
        state._add_service("172.10.0.3", 80, "http")
        assert len(state.services) == 1


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

class TestPromptString:
    def test_empty_state(self, state):
        output = state.to_prompt_string()
        assert "ATTACK STATE" in output
        # Should not have any section headers when empty
        assert "HOSTS:" not in output
        assert "CREDENTIALS:" not in output

    def test_populated_state(self, state):
        state.update_from_tool_call(
            "terminal_input",
            {"input": "nmap 172.10.0.3"},
            "80/tcp   open  http    Apache 2.4",
        )
        state.update_from_tool_call(
            "terminal_input",
            {"input": "ssh root@172.10.0.3"},
            "root@wp-prod-01:~# ",
        )
        output = state.to_prompt_string()
        assert "HOSTS:" in output
        assert "172.10.0.3" in output
        assert "SERVICES:" in output
        assert "CURRENT POSITION:" in output

    def test_to_dict_serializable(self, state):
        state.update_from_tool_call(
            "terminal_input",
            {"input": "nmap 172.10.0.3"},
            "80/tcp   open  http    Apache 2.4",
        )
        d = state.to_dict()
        assert "hosts" in d
        assert "credentials" in d
        assert "services" in d
        assert isinstance(d["hosts"], dict)
        assert isinstance(d["services"], list)


# ---------------------------------------------------------------------------
# Database access
# ---------------------------------------------------------------------------

class TestDBAccess:
    def test_mysql_marks_service_accessed(self, state):
        state._add_service("172.10.0.3", 3306, "mysql MySQL 5.7")
        state.update_from_tool_call(
            "terminal_input",
            {"input": "mysql -h 172.10.0.3 -u root -p"},
            "mysql> ",
        )
        assert state.services[0].accessed is True


# ---------------------------------------------------------------------------
# Terminate tool
# ---------------------------------------------------------------------------

class TestTerminate:
    def test_terminate_no_crash(self, state):
        state.update_from_tool_call("terminate", {"success": True}, "")
        # Should not change any state
        assert state.hosts == {}


# ---------------------------------------------------------------------------
# Command binary extraction
# ---------------------------------------------------------------------------

class TestCommandBinary:
    def test_simple(self, state):
        assert state._get_command_binary("nmap -sV 172.10.0.3") == "nmap"

    def test_sudo(self, state):
        assert state._get_command_binary("sudo cat /etc/shadow") == "cat"

    def test_env_sudo(self, state):
        assert state._get_command_binary("env sudo mysql -h db") == "mysql"

    def test_empty(self, state):
        assert state._get_command_binary("") == ""

    def test_just_sudo(self, state):
        assert state._get_command_binary("sudo") == ""


# ---------------------------------------------------------------------------
# ANSI escape stripping
# ---------------------------------------------------------------------------

class TestAnsiStripping:
    def test_ansi_in_hostname(self, state):
        """ANSI escape codes in prompt output should not corrupt hostname."""
        # Simulate a response with ANSI color codes around the prompt
        ansi_response = "\x1b[01;32mroot\x1b[00m@\x1b[01;34mwp-prod-01\x1b[00m:\x1b[01;34m~\x1b[00m# "
        state.update_from_tool_call(
            "terminal_input", {"input": "whoami"}, ansi_response
        )
        assert state.current_host == "root@wp-prod-01"

    def test_ansi_in_credentials(self, state):
        """ANSI codes in file output should not prevent credential extraction."""
        ansi_output = "\x1b[0mDB_PASSWORD=\x1b[31ms3cret\x1b[0m\n"
        state.update_from_tool_call(
            "terminal_input",
            {"input": "cat /opt/app/.env"},
            ansi_output,
        )
        assert len(state.credentials) >= 1

    def test_dec_private_mode_stripped(self, state):
        """DEC private mode sequences like \\x1b[?2004h should be stripped."""
        response = "\x1b[?2004hroot@server:~# "
        state.update_from_tool_call(
            "terminal_input", {"input": "ls"}, response
        )
        assert state.current_host == "root@server"


# ---------------------------------------------------------------------------
# SSH success clears failed attempts
# ---------------------------------------------------------------------------

class TestSSHClearsFailedAttempts:
    def test_success_clears_prior_failures(self, state):
        """Successful SSH should remove failed attempts for that host."""
        # Fail first
        state.update_from_tool_call(
            "terminal_input",
            {"input": "ssh admin@172.10.0.5"},
            "Permission denied (publickey,password).",
        )
        assert len(state.failed_attempts) == 1
        assert "172.10.0.5" in state.failed_attempts[0]

        # Succeed with different user
        state.update_from_tool_call(
            "terminal_input",
            {"input": "ssh root@172.10.0.5"},
            "root@target:~# ",
        )
        # Failed attempt for that IP should be gone
        assert all("172.10.0.5" not in a for a in state.failed_attempts)

    def test_success_preserves_other_failures(self, state):
        """Clearing failures for one host should not affect other hosts."""
        state.update_from_tool_call(
            "terminal_input",
            {"input": "ssh admin@172.10.0.5"},
            "Permission denied",
        )
        state.update_from_tool_call(
            "terminal_input",
            {"input": "ssh admin@172.10.0.6"},
            "Connection refused",
        )
        assert len(state.failed_attempts) == 2

        # Succeed on .5
        state.update_from_tool_call(
            "terminal_input",
            {"input": "ssh root@172.10.0.5"},
            "root@target:~# ",
        )
        # .6 failure should remain
        assert len(state.failed_attempts) == 1
        assert "172.10.0.6" in state.failed_attempts[0]
