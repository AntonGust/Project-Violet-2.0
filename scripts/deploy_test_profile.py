#!/usr/bin/env python3
"""
Deploy the wordpress_server profile to cowrie_config/ for integration testing.

Runs deploy_profile() from profile_converter, then writes a cowrie.cfg
that enables the hybrid LLM backend.
"""

import json
import os
import shutil
import sys
from configparser import ConfigParser
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from Reconfigurator.profile_converter import deploy_profile


def write_cowrie_cfg(cowrie_base: Path, config_overrides: dict) -> Path:
    """
    Write a cowrie.cfg that enables the hybrid LLM backend.

    This cfg is loaded by Cowrie and overrides defaults from cowrie.cfg.dist.
    """
    cfg = ConfigParser()

    # [honeypot] overrides from profile
    cfg.add_section("honeypot")
    cfg.set("honeypot", "hostname", config_overrides.get("honeypot.hostname", "svr04"))
    cfg.set("honeypot", "log_path", "var/log/cowrie")
    # Point contents_path and txtcmds_path to our mounted volumes
    cfg.set("honeypot", "contents_path", "honeyfs")
    cfg.set("honeypot", "txtcmds_path", "share/cowrie/txtcmds")

    # [shell] overrides from profile
    cfg.add_section("shell")
    cfg.set("shell", "filesystem", "share/cowrie/fs.pickle")
    if "shell.kernel_version" in config_overrides:
        cfg.set("shell", "kernel_version", config_overrides["shell.kernel_version"])
    if "shell.arch" in config_overrides:
        cfg.set("shell", "arch", config_overrides["shell.arch"])
    if "shell.hardware_platform" in config_overrides:
        cfg.set("shell", "hardware_platform", config_overrides["shell.hardware_platform"])
    if "shell.operating_system" in config_overrides:
        cfg.set("shell", "operating_system", config_overrides["shell.operating_system"])

    # [ssh] listen on 2222
    cfg.add_section("ssh")
    cfg.set("ssh", "enabled", "true")
    cfg.set("ssh", "listen_endpoints", "tcp:2222:interface=0.0.0.0")

    # [output_jsonlog] log to file (not /dev/stdout - Twisted's DailyLogFile can't seek on it)
    cfg.add_section("output_jsonlog")
    cfg.set("output_jsonlog", "enabled", "true")
    cfg.set("output_jsonlog", "logfile", "var/log/cowrie/cowrie.json")
    cfg.set("output_jsonlog", "epoch_timestamp", "false")

    # [hybrid_llm] enabled
    cfg.add_section("hybrid_llm")
    cfg.set("hybrid_llm", "enabled", "true")
    # api_key is left empty here; at runtime Cowrie's EnvironmentConfigParser
    # reads COWRIE_HYBRID_LLM_API_KEY from the environment automatically.
    cfg.set("hybrid_llm", "prompt_file", "/cowrie/cowrie-git/etc/llm_prompt.txt")
    cfg.set("hybrid_llm", "profile_file", "/cowrie/cowrie-git/etc/profile.json")
    cfg.set("hybrid_llm", "debug", "true")

    cfg_path = cowrie_base / "etc" / "cowrie.cfg"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cfg_path, "w") as f:
        cfg.write(f)

    return cfg_path


def main():
    profile_path = PROJECT_ROOT / "Reconfigurator" / "profiles" / "wordpress_server.json"
    cowrie_base = PROJECT_ROOT / "cowrie_config"

    print(f"Loading profile: {profile_path}")
    with open(profile_path) as f:
        profile = json.load(f)

    print(f"Deploying to: {cowrie_base}")
    result = deploy_profile(profile, cowrie_base)

    # Create var directories for runtime (writable by cowrie user UID 999 in container)
    var_dir = cowrie_base / "var"
    for subdir in [
        "log/cowrie",
        "lib/cowrie/tty",
        "lib/cowrie/downloads",
    ]:
        (var_dir / subdir).mkdir(parents=True, exist_ok=True)
    # Make var/ tree writable by the cowrie container user
    for dirpath, dirnames, filenames in os.walk(var_dir):
        os.chmod(dirpath, 0o777)

    # Copy cowrie.cfg.dist so Cowrie can read defaults from it
    cfg_dist_src = PROJECT_ROOT / "Cowrie" / "cowrie-src" / "etc" / "cowrie.cfg.dist"
    cfg_dist_dst = cowrie_base / "etc" / "cowrie.cfg.dist"
    shutil.copy2(cfg_dist_src, cfg_dist_dst)

    # Write cowrie.cfg with hybrid_llm enabled
    cfg_path = write_cowrie_cfg(cowrie_base, result["config_overrides"])

    print("\nDeployed artifacts:")
    print(f"  fs.pickle:    {result['pickle_path']}")
    print(f"  honeyfs:      {result['honeyfs_path']}")
    print(f"  txtcmds:      {result['txtcmds_path']}")
    print(f"  userdb.txt:   {result['userdb_path']}")
    print(f"  llm_prompt:   {result['prompt_path']}")
    print(f"  cowrie.cfg:   {cfg_path}")
    print(f"  var dir:      {var_dir}")

    print("\nConfig overrides applied:")
    for k, v in result["config_overrides"].items():
        print(f"  {k} = {v}")

    print("\nDone. Run 'docker-compose build cowrie' next.")


if __name__ == "__main__":
    main()
