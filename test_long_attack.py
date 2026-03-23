"""Long attack run: 200 iteration limit to stress-test context window and attacker behavior."""
import os
import json
from dotenv import load_dotenv
import config

load_dotenv()
os.environ["RUNID"] = config.run_id

from pathlib import Path
from Sangria import attacker_prompt
from Sangria.sangria import run_single_attack
from Reconfigurator.profile_converter import deploy_profile
from Blue_Lagoon.honeypot_tools import start_dockers, stop_dockers, clear_hp_logs, wait_for_cowrie
import Sangria.log_extractor as log_extractor
import shutil
from configparser import ConfigParser
from Utils.llm_client import _PROVIDER_URLS
from Utils.jsun import save_json_to_file

PROJECT_ROOT = Path(__file__).resolve().parent

# Deploy profile
profile_path = PROJECT_ROOT / config.initial_profile
with open(profile_path) as f:
    profile = json.load(f)

cowrie_base = PROJECT_ROOT / "cowrie_config"
result = deploy_profile(profile, cowrie_base)

# Create var directories
var_dir = cowrie_base / "var"
for subdir in ["log/cowrie", "lib/cowrie/tty", "lib/cowrie/downloads"]:
    (var_dir / subdir).mkdir(parents=True, exist_ok=True)
for dirpath, _dirnames, _filenames in os.walk(var_dir):
    os.chmod(dirpath, 0o777)

# Copy cowrie.cfg.dist
cfg_dist_src = PROJECT_ROOT / "Cowrie" / "cowrie-src" / "etc" / "cowrie.cfg.dist"
cfg_dist_dst = cowrie_base / "etc" / "cowrie.cfg.dist"
if cfg_dist_src.exists():
    shutil.copy2(cfg_dist_src, cfg_dist_dst)

# Write cowrie.cfg
cfg = ConfigParser()
cfg.add_section("honeypot")
cfg.set("honeypot", "hostname", result["config_overrides"].get("honeypot.hostname", "svr04"))
cfg.set("honeypot", "log_path", "var/log/cowrie")
cfg.set("honeypot", "contents_path", "honeyfs")
cfg.set("honeypot", "txtcmds_path", "share/cowrie/txtcmds")
cfg.set("honeypot", "interactive_timeout", "600")
cfg.set("honeypot", "idle_timeout", "300")
cfg.set("honeypot", "authentication_timeout", "120")
cfg.add_section("shell")
cfg.set("shell", "filesystem", "share/cowrie/fs.pickle")
cfg.set("shell", "processes", "share/cowrie/cmdoutput.json")
for key in ["shell.kernel_version", "shell.arch", "shell.hardware_platform", "shell.operating_system"]:
    if key in result["config_overrides"]:
        cfg.set("shell", key.split(".")[1], result["config_overrides"][key])
cfg.add_section("ssh")
cfg.set("ssh", "enabled", "true")
cfg.set("ssh", "listen_endpoints", "tcp:2222:interface=0.0.0.0")
cfg.add_section("output_jsonlog")
cfg.set("output_jsonlog", "enabled", "true")
cfg.set("output_jsonlog", "logfile", "var/log/cowrie/cowrie.json")
cfg.set("output_jsonlog", "epoch_timestamp", "false")
cfg.add_section("hybrid_llm")
cfg.set("hybrid_llm", "enabled", "true")
cfg.set("hybrid_llm", "prompt_file", "/cowrie/cowrie-git/etc/llm_prompt.txt")
cfg.set("hybrid_llm", "profile_file", "/cowrie/cowrie-git/etc/profile.json")
cfg.set("hybrid_llm", "debug", "true")
model_val = config.llm_model_honeypot.value if hasattr(config.llm_model_honeypot, 'value') else str(config.llm_model_honeypot)
cfg.set("hybrid_llm", "model", model_val)
hp_base_url = config.llm_base_url_hp or _PROVIDER_URLS.get(config.llm_provider_hp)
if hp_base_url:
    hp_base_url = hp_base_url.replace("localhost", "host.docker.internal").replace("127.0.0.1", "host.docker.internal")
    if "/v1" in hp_base_url:
        host_part = hp_base_url.split("/v1")[0]
        cfg.set("hybrid_llm", "host", host_part)
        cfg.set("hybrid_llm", "path", "/v1/chat/completions")
    else:
        cfg.set("hybrid_llm", "host", hp_base_url)
hp_api_key = config.llm_api_key_hp or os.getenv("TOGETHER_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
if hp_api_key:
    cfg.set("hybrid_llm", "api_key", hp_api_key)

with open(cowrie_base / "etc" / "cowrie.cfg", "w") as f:
    cfg.write(f)

print("Profile deployed, restarting containers...")
stop_dockers()
start_dockers()
clear_hp_logs()
log_extractor.reset_offset()
wait_for_cowrie()

# Create log paths
logs_dir = PROJECT_ROOT / "logs" / "test_long_run"
logs_dir.mkdir(parents=True, exist_ok=True)
logs_path = logs_dir / "attack_long.json"

# Build messages
messages = [
    {'role': 'system', 'content': attacker_prompt.get_prompt(profile)},
    {"role": "user", "content": "What is your next move?"}
]

MAX_ITERATIONS = 200
print(f"\n{'='*60}")
print(f"STARTING LONG TEST RUN: {MAX_ITERATIONS} iterations")
print(f"Model: {config.llm_model_sangria}")
print(f"History window: {config.history_window}")
print(f"Follow-up enabled: {config.followup_enabled}")
print(f"{'='*60}\n")

logs, tokens_used = run_single_attack(messages, MAX_ITERATIONS, logs_path, attack_counter=0, config_counter=1)

print(f"\n{'='*60}")
print(f"LONG TEST RUN COMPLETE")
print(f"Tokens used: {json.dumps(tokens_used, indent=2)}")
print(f"{'='*60}")

# Save tokens summary
save_json_to_file(tokens_used, logs_dir / "tokens_summary.json")
