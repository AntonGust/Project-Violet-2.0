"""
Unit tests for Reconfigurator.profile_converter

Tests pickle generation, honeyfs, txtcmds, userdb, LLM prompt, and deploy_profile.
"""

import json
import pickle
import shutil
import tempfile
from pathlib import Path

import pytest

from Reconfigurator.profile_converter import (
    A_CONTENTS,
    A_GID,
    A_MODE,
    A_NAME,
    A_REALFILE,
    A_SIZE,
    A_TARGET,
    A_TYPE,
    A_UID,
    T_DIR,
    T_FILE,
    T_LINK,
    deploy_profile,
    generate_honeyfs,
    generate_llm_prompt,
    generate_txtcmds,
    generate_userdb,
    profile_to_pickle,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PROFILES_DIR = Path(__file__).resolve().parent.parent / "Reconfigurator" / "profiles"


@pytest.fixture
def wordpress_profile():
    with open(PROFILES_DIR / "wordpress_server.json") as f:
        return json.load(f)


@pytest.fixture
def cicd_profile():
    with open(PROFILES_DIR / "cicd_runner.json") as f:
        return json.load(f)


@pytest.fixture
def database_profile():
    with open(PROFILES_DIR / "database_server.json") as f:
        return json.load(f)


@pytest.fixture
def tmp_dir():
    d = Path(tempfile.mkdtemp())
    yield d
    shutil.rmtree(d)


def _find_node(root, path):
    """Walk the pickle tree to find a node at the given absolute path."""
    parts = [p for p in path.strip("/").split("/") if p]
    node = root
    for part in parts:
        if node[A_TYPE] != T_DIR or node[A_CONTENTS] is None:
            return None
        found = None
        for child in node[A_CONTENTS]:
            if child[A_NAME] == part:
                found = child
                break
        if found is None:
            return None
        node = found
    return node


# ---------------------------------------------------------------------------
# Pickle structure tests
# ---------------------------------------------------------------------------


class TestProfileToPickle:
    def test_root_is_directory(self, wordpress_profile):
        tree = profile_to_pickle(wordpress_profile)
        assert tree[A_TYPE] == T_DIR
        assert tree[A_NAME] == ""
        assert isinstance(tree[A_CONTENTS], list)

    def test_node_has_ten_fields(self, wordpress_profile):
        tree = profile_to_pickle(wordpress_profile)
        assert len(tree) == 10
        # Check a child too
        for child in tree[A_CONTENTS]:
            assert len(child) == 10

    def test_standard_dirs_exist(self, wordpress_profile):
        tree = profile_to_pickle(wordpress_profile)
        for d in ["/bin", "/etc", "/home", "/tmp", "/usr", "/var", "/root",
                   "/opt", "/proc", "/sys", "/dev", "/lib", "/sbin"]:
            node = _find_node(tree, d)
            assert node is not None, f"{d} missing from pickle"
            assert node[A_TYPE] == T_DIR

    def test_profile_directories_exist(self, wordpress_profile):
        tree = profile_to_pickle(wordpress_profile)
        for d in ["/var/www/html", "/home/deploy/.ssh", "/etc/cron.d"]:
            node = _find_node(tree, d)
            assert node is not None, f"{d} missing"
            assert node[A_TYPE] == T_DIR

    def test_profile_files_exist(self, wordpress_profile):
        tree = profile_to_pickle(wordpress_profile)
        node = _find_node(tree, "/var/www/html/wp-config.php")
        assert node is not None
        assert node[A_TYPE] == T_FILE
        assert node[A_REALFILE] is None

    def test_file_size_matches_content(self, wordpress_profile):
        tree = profile_to_pickle(wordpress_profile)
        node = _find_node(tree, "/var/www/html/.env")
        assert node is not None
        expected_size = len(wordpress_profile["file_contents"]["/var/www/html/.env"])
        assert node[A_SIZE] == expected_size

    def test_uid_gid_resolution(self, wordpress_profile):
        tree = profile_to_pickle(wordpress_profile)
        # deploy user has uid=1000, gid=1000
        node = _find_node(tree, "/home/deploy/.ssh/id_rsa")
        assert node is not None
        assert node[A_UID] == 1000
        assert node[A_GID] == 1000

    def test_permissions_parsed(self, wordpress_profile):
        tree = profile_to_pickle(wordpress_profile)
        node = _find_node(tree, "/home/deploy/.ssh/id_rsa")
        assert node is not None
        assert node[A_MODE] == 0o600

    def test_directory_contents_correct(self, wordpress_profile):
        tree = profile_to_pickle(wordpress_profile)
        node = _find_node(tree, "/var/www/html")
        assert node is not None
        names = {c[A_NAME] for c in node[A_CONTENTS]}
        assert "wp-config.php" in names
        assert ".env" in names
        assert "uploads" in names

    def test_pickle_serializable(self, wordpress_profile):
        tree = profile_to_pickle(wordpress_profile)
        data = pickle.dumps(tree, protocol=2)
        loaded = pickle.loads(data)
        assert loaded[A_TYPE] == T_DIR
        assert len(loaded[A_CONTENTS]) == len(tree[A_CONTENTS])

    def test_file_contents_without_directory_tree_entry(self, wordpress_profile):
        """Files in file_contents but not in directory_tree should still appear."""
        tree = profile_to_pickle(wordpress_profile)
        # root/.bash_history is in directory_tree AND file_contents
        node = _find_node(tree, "/root/.bash_history")
        assert node is not None
        assert node[A_TYPE] == T_FILE

    def test_all_profiles_produce_valid_trees(self, wordpress_profile, cicd_profile, database_profile):
        for p in [wordpress_profile, cicd_profile, database_profile]:
            tree = profile_to_pickle(p)
            assert tree[A_TYPE] == T_DIR
            assert len(tree[A_CONTENTS]) > 0
            # Verify pickle round-trip
            data = pickle.dumps(tree, protocol=2)
            loaded = pickle.loads(data)
            assert len(loaded[A_CONTENTS]) == len(tree[A_CONTENTS])


# ---------------------------------------------------------------------------
# Honeyfs tests
# ---------------------------------------------------------------------------


class TestGenerateHoneyfs:
    def test_passwd_generated(self, wordpress_profile, tmp_dir):
        generate_honeyfs(wordpress_profile, tmp_dir)
        passwd = tmp_dir / "etc" / "passwd"
        assert passwd.exists()
        content = passwd.read_text()
        assert "root:x:0:0:" in content
        assert "deploy:x:1000:1000:" in content
        assert "www-data:x:33:33:" in content

    def test_shadow_generated(self, wordpress_profile, tmp_dir):
        generate_honeyfs(wordpress_profile, tmp_dir)
        shadow = tmp_dir / "etc" / "shadow"
        assert shadow.exists()
        content = shadow.read_text()
        assert "root:" in content

    def test_hostname_generated(self, wordpress_profile, tmp_dir):
        generate_honeyfs(wordpress_profile, tmp_dir)
        hostname = tmp_dir / "etc" / "hostname"
        assert hostname.exists()
        assert hostname.read_text().strip() == "wp-prod-01"

    def test_os_release_generated(self, wordpress_profile, tmp_dir):
        generate_honeyfs(wordpress_profile, tmp_dir)
        os_release = tmp_dir / "etc" / "os-release"
        assert os_release.exists()
        content = os_release.read_text()
        assert "Ubuntu 20.04.6 LTS" in content

    def test_file_contents_written(self, wordpress_profile, tmp_dir):
        generate_honeyfs(wordpress_profile, tmp_dir)
        wpconfig = tmp_dir / "var" / "www" / "html" / "wp-config.php"
        assert wpconfig.exists()
        content = wpconfig.read_text()
        assert "DB_PASSWORD" in content
        assert "Str0ng_But_Le4ked!" in content

    def test_sudoers_generated(self, wordpress_profile, tmp_dir):
        generate_honeyfs(wordpress_profile, tmp_dir)
        sudoers = tmp_dir / "etc" / "sudoers.d" / "deploy"
        assert sudoers.exists()
        assert "NOPASSWD" in sudoers.read_text()

    def test_group_generated(self, wordpress_profile, tmp_dir):
        generate_honeyfs(wordpress_profile, tmp_dir)
        group = tmp_dir / "etc" / "group"
        assert group.exists()
        content = group.read_text()
        assert "root:" in content


# ---------------------------------------------------------------------------
# txtcmds tests
# ---------------------------------------------------------------------------


class TestGenerateTxtcmds:
    def test_uname_contains_hostname(self, wordpress_profile, tmp_dir):
        generate_txtcmds(wordpress_profile, tmp_dir)
        uname = tmp_dir / "usr" / "bin" / "uname"
        assert uname.exists()
        content = uname.read_text()
        assert "wp-prod-01" in content
        assert "5.4.0-169-generic" in content

    def test_ps_contains_services(self, wordpress_profile, tmp_dir):
        generate_txtcmds(wordpress_profile, tmp_dir)
        ps = tmp_dir / "usr" / "bin" / "ps"
        assert ps.exists()
        content = ps.read_text()
        assert "apache2" in content
        assert "mysqld" in content
        assert "sshd" in content
        lines = content.strip().split("\n")
        # Header + 6 services
        assert len(lines) >= 7

    def test_ifconfig_contains_interfaces(self, wordpress_profile, tmp_dir):
        generate_txtcmds(wordpress_profile, tmp_dir)
        ifconfig = tmp_dir / "usr" / "sbin" / "ifconfig"
        assert ifconfig.exists()
        content = ifconfig.read_text()
        assert "eth0" in content
        assert "10.0.1.15" in content
        assert "docker0" in content

    def test_netstat_contains_ports(self, wordpress_profile, tmp_dir):
        generate_txtcmds(wordpress_profile, tmp_dir)
        netstat = tmp_dir / "usr" / "bin" / "netstat"
        assert netstat.exists()
        content = netstat.read_text()
        assert "80" in content
        assert "3306" in content
        assert "22" in content

    def test_df_exists(self, wordpress_profile, tmp_dir):
        generate_txtcmds(wordpress_profile, tmp_dir)
        df = tmp_dir / "usr" / "bin" / "df"
        assert df.exists()

    def test_different_profile_different_output(self, wordpress_profile, cicd_profile, tmp_dir):
        wp_dir = tmp_dir / "wp"
        ci_dir = tmp_dir / "ci"
        generate_txtcmds(wordpress_profile, wp_dir)
        generate_txtcmds(cicd_profile, ci_dir)
        wp_uname = (wp_dir / "usr" / "bin" / "uname").read_text()
        ci_uname = (ci_dir / "usr" / "bin" / "uname").read_text()
        assert wp_uname != ci_uname
        assert "wp-prod-01" in wp_uname
        assert "ci-runner-07" in ci_uname


# ---------------------------------------------------------------------------
# Userdb tests
# ---------------------------------------------------------------------------


class TestGenerateUserdb:
    def test_userdb_format(self, wordpress_profile, tmp_dir):
        path = tmp_dir / "userdb.txt"
        generate_userdb(wordpress_profile, path)
        assert path.exists()
        lines = path.read_text().strip().split("\n")
        # root has 4 passwords, deploy has 2 = 6 total
        assert len(lines) == 6
        # Each line: username:uid:password
        for line in lines:
            parts = line.split(":")
            assert len(parts) == 3

    def test_userdb_contains_passwords(self, wordpress_profile, tmp_dir):
        path = tmp_dir / "userdb.txt"
        generate_userdb(wordpress_profile, path)
        content = path.read_text()
        assert "root:0:123456" in content
        assert "deploy:1000:deploy123" in content


# ---------------------------------------------------------------------------
# LLM prompt tests
# ---------------------------------------------------------------------------


class TestGenerateLlmPrompt:
    def test_prompt_contains_os(self, wordpress_profile):
        prompt = generate_llm_prompt(wordpress_profile)
        assert "Ubuntu 20.04.6 LTS" in prompt

    def test_prompt_contains_hostname(self, wordpress_profile):
        prompt = generate_llm_prompt(wordpress_profile)
        assert "wp-prod-01" in prompt

    def test_prompt_contains_services(self, wordpress_profile):
        prompt = generate_llm_prompt(wordpress_profile)
        assert "apache2" in prompt
        assert "mysqld" in prompt

    def test_prompt_no_directory_listing(self, wordpress_profile):
        """Prompt should no longer contain the directory tree block;
        context is now provided separately by the prequery system."""
        prompt = generate_llm_prompt(wordpress_profile)
        assert "FILESYSTEM (key directories):" not in prompt
        assert "Relevant filesystem and system context for the current command is provided separately" in prompt

    def test_prompt_no_markdown(self, wordpress_profile):
        prompt = generate_llm_prompt(wordpress_profile)
        assert "```" not in prompt

    def test_different_profiles_different_prompts(self, wordpress_profile, database_profile):
        wp_prompt = generate_llm_prompt(wordpress_profile)
        db_prompt = generate_llm_prompt(database_profile)
        assert "wp-prod-01" in wp_prompt
        assert "db-primary" in db_prompt
        assert wp_prompt != db_prompt


# ---------------------------------------------------------------------------
# deploy_profile end-to-end tests
# ---------------------------------------------------------------------------


class TestDeployProfile:
    def test_all_artifacts_generated(self, wordpress_profile, tmp_dir):
        result = deploy_profile(wordpress_profile, tmp_dir)
        assert Path(result["pickle_path"]).exists()
        assert Path(result["honeyfs_path"]).is_dir()
        assert Path(result["txtcmds_path"]).is_dir()
        assert Path(result["userdb_path"]).exists()
        assert Path(result["prompt_path"]).exists()
        assert Path(result["profile_path"]).exists()
        assert "config_overrides" in result
        assert "llm_prompt" in result

    def test_profile_json_written(self, wordpress_profile, tmp_dir):
        """deploy_profile must write profile.json for the LLM pre-query system."""
        result = deploy_profile(wordpress_profile, tmp_dir)
        import json as _json
        with open(result["profile_path"]) as f:
            loaded = _json.load(f)
        assert loaded["system"]["hostname"] == wordpress_profile["system"]["hostname"]
        assert loaded["services"] == wordpress_profile["services"]

    def test_pickle_loadable(self, wordpress_profile, tmp_dir):
        result = deploy_profile(wordpress_profile, tmp_dir)
        with open(result["pickle_path"], "rb") as f:
            tree = pickle.load(f)
        assert tree[A_TYPE] == T_DIR
        assert len(tree[A_CONTENTS]) > 0

    def test_config_overrides(self, wordpress_profile, tmp_dir):
        result = deploy_profile(wordpress_profile, tmp_dir)
        overrides = result["config_overrides"]
        assert overrides["honeypot.hostname"] == "wp-prod-01"
        assert "5.4.0-169-generic" in overrides["shell.kernel_version"]

    def test_redeploy_cleans_previous(self, wordpress_profile, cicd_profile, tmp_dir):
        """Deploying a second profile should replace the first cleanly."""
        deploy_profile(wordpress_profile, tmp_dir)
        result = deploy_profile(cicd_profile, tmp_dir)
        # Honeyfs should now have CI/CD content, not WordPress
        honeyfs = Path(result["honeyfs_path"])
        assert not (honeyfs / "var" / "www" / "html" / "wp-config.php").exists()
        hostname = (honeyfs / "etc" / "hostname").read_text().strip()
        assert hostname == "ci-runner-07"

    @pytest.mark.parametrize("profile_name", [
        "wordpress_server", "cicd_runner", "database_server"
    ])
    def test_all_profiles_deploy(self, profile_name, tmp_dir):
        with open(PROFILES_DIR / f"{profile_name}.json") as f:
            profile = json.load(f)
        result = deploy_profile(profile, tmp_dir)
        assert Path(result["pickle_path"]).exists()
        with open(result["pickle_path"], "rb") as f:
            tree = pickle.load(f)
        assert tree[A_TYPE] == T_DIR
