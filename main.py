from dotenv import load_dotenv
import json
import os
import shutil
import config

load_dotenv()
os.environ["RUNID"] = config.run_id

from configparser import ConfigParser
from pathlib import Path

from Sangria import attacker_prompt
from Sangria.sangria import run_single_attack, MODEL_PRICING
from Sangria.extraction import extract_session
from Sangria.session_formatter import format_session_report

from Reconfigurator.profile_converter import deploy_profile
from Reconfigurator.new_config_pipeline import generate_new_profile
from Reconfigurator.lure_agent import enrich_lures
from Reconfigurator.db_seed_generator import extract_db_config, generate_init_sql, write_db_init_scripts

from Blue_Lagoon.honeypot_tools import (
    start_dockers, stop_dockers, clear_hp_logs, wait_for_cowrie, wait_for_db,
    wait_for_all_cowrie, wait_for_honeynet_dbs, generate_db_compose,
    remove_db_compose, stop_single_hop, start_single_hop,
)
from Blue_Lagoon.credential_chain import (
    build_chain_manifest, inject_next_hop_breadcrumbs,
    CredentialTier, ensure_crackable_password, lock_down_hop_passwords,
)
from Blue_Lagoon.compose_generator import generate_honeynet_compose
from Purple.session_correlator import correlate_sessions, print_correlation_report
import Sangria.log_extractor as log_extractor

from Utils.meta import create_experiment_folder, select_reconfigurator
from Utils.jsun import save_json_to_file, append_json_to_file, load_json
from Sangria import display
from Purple.cheat_detector import CheaTDetector
from Reconfigurator.cheat.unicode_tokens import apply_honeytokens_to_profile
from Reconfigurator.cheat.canary_urls import apply_canary_urls_to_profile
from Reconfigurator.cheat.payload_templates import apply_prompt_traps_to_profile
from Reconfigurator.cheat.tool_traps import apply_tool_traps_to_txtcmds

PROJECT_ROOT = Path(__file__).resolve().parent


def _get_hp_token_log_path() -> Path:
    """Return the path to the honeypot LLM token usage log."""
    if config.honeynet_enabled:
        return PROJECT_ROOT / "cowrie_config_hop1" / "var" / "llm_tokens.jsonl"
    return PROJECT_ROOT / "cowrie_config" / "var" / "llm_tokens.jsonl"


def read_and_reset_hp_tokens() -> dict:
    """Read honeypot LLM token usage from the volume-mapped JSONL file,
    then truncate it for the next session.

    Returns a dict with prompt_tokens, completion_tokens, cached_tokens,
    and estimated_cost_usd for the honeypot defender.
    """
    token_log = _get_hp_token_log_path()
    totals = {"prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0}

    if token_log.exists():
        try:
            for line in token_log.read_text().strip().splitlines():
                entry = json.loads(line)
                totals["prompt_tokens"] += entry.get("prompt_tokens", 0)
                totals["completion_tokens"] += entry.get("completion_tokens", 0)
                totals["cached_tokens"] += entry.get("cached_tokens", 0)
        except (json.JSONDecodeError, OSError):
            pass
        # Truncate for next session
        try:
            token_log.write_text("")
        except OSError:
            pass

    # Calculate cost
    model_name = getattr(config.llm_model_honeypot, "value", str(config.llm_model_honeypot))
    pricing = MODEL_PRICING.get(model_name)
    cost = 0.0
    if pricing:
        cost += (totals["prompt_tokens"] - totals["cached_tokens"]) * pricing["input"] / 1_000_000
        cost += totals["cached_tokens"] * pricing["cached"] / 1_000_000
        cost += totals["completion_tokens"] * pricing["output"] / 1_000_000

    totals["estimated_cost_usd"] = cost
    return totals


def deploy_cowrie_config(profile: dict, hop_index: int = -1) -> dict:
    """Deploy a filesystem profile to cowrie_config/ and write cowrie.cfg.

    Args:
        profile: parsed filesystem profile dict
        hop_index: When >= 0 and honeynet_enabled, deploy to cowrie_config_hop{N}/
                   instead of cowrie_config/.
    """
    if config.honeynet_enabled and hop_index >= 0:
        cowrie_base = PROJECT_ROOT / f"cowrie_config_hop{hop_index + 1}"
    else:
        cowrie_base = PROJECT_ROOT / "cowrie_config"

    result = deploy_profile(profile, cowrie_base)

    # Create var directories for Cowrie runtime
    var_dir = cowrie_base / "var"
    for subdir in ["log/cowrie", "lib/cowrie/tty", "lib/cowrie/downloads"]:
        (var_dir / subdir).mkdir(parents=True, exist_ok=True)
    for dirpath, _dirnames, _filenames in os.walk(var_dir):
        os.chmod(dirpath, 0o777)

    # Copy cowrie.cfg.dist so Cowrie can read defaults
    cfg_dist_src = PROJECT_ROOT / "Cowrie" / "cowrie-src" / "etc" / "cowrie.cfg.dist"
    cfg_dist_dst = cowrie_base / "etc" / "cowrie.cfg.dist"
    if cfg_dist_src.exists():
        shutil.copy2(cfg_dist_src, cfg_dist_dst)

    # Write cowrie.cfg with hybrid LLM enabled
    _write_cowrie_cfg(cowrie_base, result["config_overrides"])

    # Database honeypot setup
    db_config = extract_db_config(profile)
    if db_config:
        init_sql = generate_init_sql(db_config, profile)
        write_db_init_scripts(cowrie_base, db_config, init_sql)
        generate_db_compose(db_config, cowrie_base)

        # Write db_config.json for honeypot_tools._compose_env()
        db_config_path = cowrie_base / "db_config.json"
        db_config_path.write_text(json.dumps(db_config, indent=2), encoding="utf-8")

        # Create log directories for DB
        (var_dir / "log" / "db").mkdir(parents=True, exist_ok=True)
        os.chmod(str(var_dir / "log" / "db"), 0o777)

        print(f"Database honeypot configured: {db_config['engine']} "
              f"(spoofed version: {db_config['spoofed_version']})")
    else:
        remove_db_compose()
        # Clean up stale DB files
        for stale in [cowrie_base / "db_config.json", cowrie_base / "db_init"]:
            if stale.is_file():
                stale.unlink()
            elif stale.is_dir():
                shutil.rmtree(stale)

    return result


def _write_cowrie_cfg(cowrie_base: Path, config_overrides: dict) -> None:
    """Write a cowrie.cfg that enables the hybrid LLM backend."""
    cfg = ConfigParser()

    cfg.add_section("honeypot")
    cfg.set("honeypot", "hostname", config_overrides.get("honeypot.hostname", "svr04"))
    cfg.set("honeypot", "log_path", "var/log/cowrie")
    cfg.set("honeypot", "contents_path", "honeyfs")
    cfg.set("honeypot", "txtcmds_path", "share/cowrie/txtcmds")
    cfg.set("honeypot", "interactive_timeout", "900")
    cfg.set("honeypot", "idle_timeout", "600")
    cfg.set("honeypot", "authentication_timeout", "120")

    cfg.add_section("shell")
    cfg.set("shell", "filesystem", "share/cowrie/fs.pickle")
    cfg.set("shell", "processes", "share/cowrie/cmdoutput.json")
    for key in ["shell.kernel_version", "shell.arch", "shell.hardware_platform", "shell.operating_system"]:
        if key in config_overrides:
            cfg.set("shell", key.split(".")[1], config_overrides[key])

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
    cfg.set("hybrid_llm", "model", config.llm_model_honeypot.value if hasattr(config.llm_model_honeypot, 'value') else str(config.llm_model_honeypot))

    # Local model support: configure host/path for non-OpenAI providers
    from Utils.llm_client import _PROVIDER_URLS
    hp_base_url = config.llm_base_url_hp or _PROVIDER_URLS.get(config.llm_provider_hp)
    if hp_base_url:
        # Docker containers can't reach localhost — rewrite for Docker networking
        hp_base_url = hp_base_url.replace("localhost", "host.docker.internal")
        hp_base_url = hp_base_url.replace("127.0.0.1", "host.docker.internal")
        # Split into host + path for Cowrie's LLMClient config
        if "/v1" in hp_base_url:
            host_part = hp_base_url.split("/v1")[0]
            cfg.set("hybrid_llm", "host", host_part)
            cfg.set("hybrid_llm", "path", "/v1/chat/completions")
        else:
            cfg.set("hybrid_llm", "host", hp_base_url)

    # Resolve honeypot API key: explicit config → provider-specific env var → OPENAI_API_KEY
    from Utils.llm_client import _PROVIDER_ENV_KEYS
    hp_api_key = config.llm_api_key_hp or os.getenv(
        _PROVIDER_ENV_KEYS.get(config.llm_provider_hp, "OPENAI_API_KEY"), ""
    )
    if hp_api_key:
        cfg.set("hybrid_llm", "api_key", hp_api_key)

    cfg_path = cowrie_base / "etc" / "cowrie.cfg"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cfg_path, "w") as f:
        cfg.write(f)


def apply_cheat_defenses(profile: dict) -> tuple[dict, dict]:
    """Apply all enabled CHeaT defenses to a profile.

    Returns (modified_profile, cheat_defenses_metadata).
    The metadata dict is saved as cheat_defenses.json for the detector.
    """
    defenses = {"unicode_tokens": [], "canary_urls": [], "prompt_traps": []}

    if config.cheat_unicode_honeytokens:
        profile, planted = apply_honeytokens_to_profile(profile)
        defenses["unicode_tokens"] = planted

    if config.cheat_canary_urls:
        profile, planted = apply_canary_urls_to_profile(profile)
        defenses["canary_urls"] = planted

    if config.cheat_prompt_traps:
        profile, planted = apply_prompt_traps_to_profile(profile)
        defenses["prompt_traps"] = planted

    return profile, defenses


def _flatten_per_hop_defenses(per_hop: dict[str, dict]) -> dict:
    """Flatten per-hop CHeaT defenses into a single dict for the detector.

    Input:  {"hop_1": {"unicode_tokens": [...], ...}, "hop_2": {...}}
    Output: {"unicode_tokens": [all_tokens], "canary_urls": [all_urls], ...}
    """
    flat: dict[str, list] = {
        "unicode_tokens": [],
        "canary_urls": [],
        "prompt_traps": [],
        "tool_traps": [],
    }
    for hop_key, defenses in per_hop.items():
        for defense_type, items in defenses.items():
            if defense_type in flat and isinstance(items, list):
                flat[defense_type].extend(items)
    return flat


def main():
    if config.honeynet_enabled:
        main_honeynet()
    else:
        main_single()


def main_honeynet():
    """Run a multi-hop HoneyNet experiment."""
    base_path = Path(create_experiment_folder(experiment_name=config.experiment_name))

    # 1. Build chain manifest
    manifest = build_chain_manifest(config.run_id, config.chain_profiles)

    # 2. For each hop: load profile -> enrich_lures() -> inject breadcrumbs -> deploy
    hop_profiles = []
    cheat_defenses: dict[str, dict] = {}  # per-hop: {"hop_1": {...}, "hop_2": {...}}
    for i, hop in enumerate(manifest.hops):
        profile_path = PROJECT_ROOT / hop.profile_path
        with open(profile_path) as f:
            profile = json.load(f)

        profile, lure_chains = enrich_lures(profile)

        # CHeaT: apply all defenses to EVERY hop
        hop_cheat = None
        if config.cheat_enabled:
            profile, hop_cheat = apply_cheat_defenses(profile)

        # Inject next-hop breadcrumbs (all but last hop)
        if i < len(manifest.hops) - 1:
            tiers = getattr(config, "credential_tiers", [])
            tier = tiers[i] if i < len(tiers) else CredentialTier.PLAINTEXT
            next_hop = manifest.hops[i + 1]

            # For non-plaintext tiers, lock down the next hop so only the
            # tier-specific password works (prevents star-topology bypass)
            if tier != CredentialTier.PLAINTEXT:
                next_profile_path = PROJECT_ROOT / next_hop.profile_path
                with open(next_profile_path) as nf:
                    next_profile = json.load(nf)

                if tier == CredentialTier.SHADOW_HASH:
                    cracked_pw = ensure_crackable_password(next_profile, next_hop.username)
                    next_hop.password = cracked_pw
                else:
                    # T2/T3: replace guessable password + remove all other credentials
                    new_pw = lock_down_hop_passwords(next_profile, next_hop.username, next_hop.password)
                    next_hop.password = new_pw

                with open(next_profile_path, "w") as nf:
                    json.dump(next_profile, nf, indent=2)

            inject_next_hop_breadcrumbs(profile, hop, next_hop, credential_tier=tier)

        result = deploy_cowrie_config(profile, hop_index=i)

        # CHeaT: apply tool traps after deploy (every hop)
        if config.cheat_enabled and config.cheat_tool_traps:
            txtcmds_path = result.get("txtcmds_path")
            tool_trap_planted = apply_tool_traps_to_txtcmds(txtcmds_path, profile)
            if hop_cheat is not None:
                hop_cheat["tool_traps"] = tool_trap_planted

        if hop_cheat is not None:
            cheat_defenses[f"hop_{i + 1}"] = hop_cheat

        hop_profiles.append((profile, lure_chains))

    # 3. Generate docker-compose
    generate_honeynet_compose(manifest)

    # 4. Start all containers
    if not config.simulate_command_line:
        start_dockers()
        clear_hp_logs()
        log_extractor.reset_offset()
        wait_for_all_cowrie(len(manifest.hops))
        wait_for_honeynet_dbs(config.chain_db_enabled)

    # 5. Save experiment metadata
    config_path = base_path / "hp_config_1"
    full_logs_path = config_path / "full_logs"
    os.makedirs(full_logs_path, exist_ok=True)

    if not config.simulate_command_line:
        for i, (profile, lure_chains) in enumerate(hop_profiles):
            save_json_to_file(profile, config_path / f"honeypot_config_hop{i + 1}.json")
            if lure_chains:
                save_json_to_file(lure_chains, config_path / f"lure_chains_hop{i + 1}.json")
        if cheat_defenses:
            save_json_to_file(cheat_defenses, config_path / "cheat_defenses.json")

    # Flatten per-hop defenses for the CHeaT detector (it expects a flat dict)
    flat_cheat_defenses = _flatten_per_hop_defenses(cheat_defenses) if cheat_defenses else None

    # Use pot1's profile for the attacker prompt (organic discovery)
    pot1_profile = hop_profiles[0][0]

    display.print_honeynet_start(len(manifest.hops))

    reconfigurator = select_reconfigurator()
    reconfigurator.reset()
    cheat_detector = CheaTDetector() if config.cheat_enabled else None
    config_counter = 1
    config_attack_counter = 0

    aborted = False
    for i in range(config.num_of_sessions):
        config_attack_counter += 1
        display.print_attack_banner(config_attack_counter, config.num_of_sessions, config_counter)

        if config.confirm_before_session:
            answer = input("Press Enter to start session (or 'q' to abort): ").strip().lower()
            if answer == 'q':
                print("Experiment aborted by user.")
                stop_dockers()
                return

        logs_path = full_logs_path / f"attack_{config_attack_counter}.json"

        messages = [
            {'role': 'system', 'content': attacker_prompt.get_prompt(pot1_profile)},
            {"role": "user", "content": "What is your next move?"}
        ]

        logs, tokens_used, aborted = run_single_attack(messages, config.max_session_length, logs_path, config_attack_counter - 1, config_counter)

        # Collect honeypot defender LLM token usage
        if not config.simulate_command_line:
            hp_tokens = read_and_reset_hp_tokens()
            tokens_used["honeypot_prompt_tokens"] = hp_tokens["prompt_tokens"]
            tokens_used["honeypot_completion_tokens"] = hp_tokens["completion_tokens"]
            tokens_used["honeypot_cached_tokens"] = hp_tokens["cached_tokens"]
            tokens_used["honeypot_cost_usd"] = hp_tokens["estimated_cost_usd"]
            tokens_used["total_cost_usd"] = tokens_used["estimated_cost_usd"] + hp_tokens["estimated_cost_usd"]
            display.print_honeypot_cost(hp_tokens)
            display.print_total_cost(tokens_used["estimated_cost_usd"], hp_tokens["estimated_cost_usd"])
        else:
            tokens_used["honeypot_prompt_tokens"] = 0
            tokens_used["honeypot_completion_tokens"] = 0
            tokens_used["honeypot_cached_tokens"] = 0
            tokens_used["honeypot_cost_usd"] = 0.0
            tokens_used["total_cost_usd"] = tokens_used["estimated_cost_usd"]

        # Load full (untrimmed) logs from file for extraction — the
        # in-memory messages list is truncated by the history window.
        full_logs = load_json(logs_path)
        session = extract_session(full_logs)
        reconfigurator.update(session)

        # CHeaT: run detection analysis
        cheat_results = None
        if cheat_detector and flat_cheat_defenses:
            cowrie_logs = []
            if not config.simulate_command_line:
                cowrie_logs = log_extractor.get_new_hp_logs()
            cheat_results = cheat_detector.analyze_session(session, cowrie_logs, flat_cheat_defenses)
            append_json_to_file(cheat_results, config_path / "cheat_results.json", False)

        append_json_to_file(tokens_used, config_path / "tokens_used.json", False)
        append_json_to_file(session, config_path / "sessions.json", False)

        report_path = full_logs_path / f"attack_{config_attack_counter}.md"
        format_session_report(full_logs, session, tokens_used, report_path, cheat_results)

        if aborted:
            break

        # Per-hop reconfiguration (credential-stable)
        if reconfigurator.should_reconfigure() and (i + 1) < config.num_of_sessions:
            display.print_reconfig_notice("honeynet hops (credential-stable)")
            cheat_defenses = {}
            for hop_idx, hop in enumerate(manifest.hops):
                if not config.simulate_command_line:
                    stop_single_hop(hop_idx)

                profile_path = PROJECT_ROOT / hop.profile_path
                with open(profile_path) as f:
                    new_profile = json.load(f)

                new_profile, new_lure_chains = enrich_lures(new_profile)

                # CHeaT: re-apply defenses to every hop
                hop_cheat = None
                if config.cheat_enabled:
                    new_profile, hop_cheat = apply_cheat_defenses(new_profile)

                # Re-inject same breadcrumbs (credentials unchanged, same tier)
                if hop_idx < len(manifest.hops) - 1:
                    tiers = getattr(config, "credential_tiers", [])
                    tier = tiers[hop_idx] if hop_idx < len(tiers) else CredentialTier.PLAINTEXT
                    inject_next_hop_breadcrumbs(
                        new_profile, hop, manifest.hops[hop_idx + 1],
                        credential_tier=tier,
                    )

                result = deploy_cowrie_config(new_profile, hop_index=hop_idx)

                # CHeaT: re-apply tool traps after deploy
                if config.cheat_enabled and config.cheat_tool_traps:
                    txtcmds_path = result.get("txtcmds_path")
                    tool_trap_planted = apply_tool_traps_to_txtcmds(txtcmds_path, new_profile)
                    if hop_cheat is not None:
                        hop_cheat["tool_traps"] = tool_trap_planted

                if hop_cheat is not None:
                    cheat_defenses[f"hop_{hop_idx + 1}"] = hop_cheat

                hop_profiles[hop_idx] = (new_profile, new_lure_chains)

                if not config.simulate_command_line:
                    start_single_hop(hop_idx)

            flat_cheat_defenses = _flatten_per_hop_defenses(cheat_defenses) if cheat_defenses else None
            pot1_profile = hop_profiles[0][0]
            reconfigurator.reset()
            config_counter += 1
            config_attack_counter = 0
            config_path = base_path / f"hp_config_{config_counter}"
            full_logs_path = config_path / "full_logs"
            os.makedirs(full_logs_path, exist_ok=True)

            if not config.simulate_command_line:
                save_json_to_file(cheat_defenses, config_path / "cheat_defenses.json")
                clear_hp_logs()
                log_extractor.reset_offset()

        print("\n\n")

    # Post-experiment: correlate sessions across hops
    if not config.simulate_command_line:
        journeys = correlate_sessions(manifest)
        print_correlation_report(journeys)
        save_json_to_file(
            [j.summary() for j in journeys],
            base_path / "session_correlation.json",
        )

    stop_dockers()


def main_single():
    base_path = create_experiment_folder(experiment_name=config.experiment_name)
    base_path = Path(base_path)

    # Load and deploy the initial filesystem profile
    profile_path = PROJECT_ROOT / config.initial_profile
    with open(profile_path) as f:
        profile = json.load(f)

    profile, lure_chains = enrich_lures(profile)

    # CHeaT: apply all enabled defenses to the profile
    cheat_defenses = None
    if config.cheat_enabled:
        profile, cheat_defenses = apply_cheat_defenses(profile)

    result = deploy_cowrie_config(profile)

    # CHeaT: apply tool output traps to txtcmds (must happen after deploy)
    if config.cheat_enabled and config.cheat_tool_traps:
        txtcmds_path = result.get("txtcmds_path")
        tool_trap_planted = apply_tool_traps_to_txtcmds(txtcmds_path, profile)
        if cheat_defenses is not None:
            cheat_defenses["tool_traps"] = tool_trap_planted

    config_counter = 1
    config_attack_counter = 0
    total_attack_counter = 0
    tokens_used_list = []
    cheat_detector = CheaTDetector() if config.cheat_enabled else None

    display.print_new_config_banner(config_counter)

    reconfigurator = select_reconfigurator()
    reconfigurator.reset()

    if not config.simulate_command_line:
        start_dockers()
        clear_hp_logs()
        log_extractor.reset_offset()
        wait_for_cowrie()
        wait_for_db()

    config_path = base_path / f"hp_config_{config_counter}"
    full_logs_path = config_path / "full_logs"
    os.makedirs(full_logs_path, exist_ok=True)

    if not config.simulate_command_line:
        save_json_to_file(profile, config_path / "honeypot_config.json")
        if lure_chains:
            save_json_to_file(lure_chains, config_path / "lure_chains.json")
        if cheat_defenses:
            save_json_to_file(cheat_defenses, config_path / "cheat_defenses.json")

    for i in range(config.num_of_sessions):
        config_attack_counter += 1
        total_attack_counter += 1
        os.makedirs(config_path, exist_ok=True)
        display.print_attack_banner(config_attack_counter, config.num_of_sessions, config_counter)

        if config.confirm_before_session:
            answer = input("Press Enter to start session (or 'q' to abort): ").strip().lower()
            if answer == 'q':
                print("Experiment aborted by user.")
                stop_dockers()
                return

        logs_path = full_logs_path / f"attack_{config_attack_counter}.json"

        messages = [
            {'role': 'system', 'content': attacker_prompt.get_prompt(profile)},
            {"role": "user", "content": "What is your next move?"}
        ]

        logs, tokens_used, aborted = run_single_attack(messages, config.max_session_length, logs_path, config_attack_counter-1, config_counter)

        # Collect honeypot defender LLM token usage
        if not config.simulate_command_line:
            hp_tokens = read_and_reset_hp_tokens()
            tokens_used["honeypot_prompt_tokens"] = hp_tokens["prompt_tokens"]
            tokens_used["honeypot_completion_tokens"] = hp_tokens["completion_tokens"]
            tokens_used["honeypot_cached_tokens"] = hp_tokens["cached_tokens"]
            tokens_used["honeypot_cost_usd"] = hp_tokens["estimated_cost_usd"]
            tokens_used["total_cost_usd"] = tokens_used["estimated_cost_usd"] + hp_tokens["estimated_cost_usd"]
            display.print_honeypot_cost(hp_tokens)
            display.print_total_cost(tokens_used["estimated_cost_usd"], hp_tokens["estimated_cost_usd"])
        else:
            tokens_used["honeypot_prompt_tokens"] = 0
            tokens_used["honeypot_completion_tokens"] = 0
            tokens_used["honeypot_cached_tokens"] = 0
            tokens_used["honeypot_cost_usd"] = 0.0
            tokens_used["total_cost_usd"] = tokens_used["estimated_cost_usd"]

        # Load full (untrimmed) logs from file for extraction — the
        # in-memory messages list is truncated by the history window.
        full_logs = load_json(logs_path)
        session = extract_session(full_logs)
        reconfigurator.update(session)

        # CHeaT: run detection analysis
        cheat_results = None
        if cheat_detector and cheat_defenses:
            cowrie_logs = []
            if not config.simulate_command_line:
                cowrie_logs = log_extractor.get_new_hp_logs()
            cheat_results = cheat_detector.analyze_session(session, cowrie_logs, cheat_defenses)
            append_json_to_file(cheat_results, config_path / "cheat_results.json", False)

        append_json_to_file(tokens_used, config_path / "tokens_used.json", False)
        tokens_used_list.append(tokens_used)
        append_json_to_file(session, config_path / "sessions.json", False)

        report_path = full_logs_path / f"attack_{config_attack_counter}.md"
        format_session_report(full_logs, session, tokens_used, report_path, cheat_results)

        if aborted:
            break

        if reconfigurator.should_reconfigure() and total_attack_counter < config.num_of_sessions:
            display.print_reconfig_notice(config.reconfig_method)

            if not config.simulate_command_line:
                stop_dockers()

            # Generate new profile and deploy to Cowrie
            profile = generate_new_profile(base_path)
            if profile is not None:
                profile, lure_chains = enrich_lures(profile)

                # CHeaT: re-apply all defenses to new profile
                if config.cheat_enabled:
                    profile, cheat_defenses = apply_cheat_defenses(profile)

                result = deploy_cowrie_config(profile)

                # CHeaT: re-apply tool traps after deploy
                if config.cheat_enabled and config.cheat_tool_traps:
                    txtcmds_path = result.get("txtcmds_path")
                    tool_trap_planted = apply_tool_traps_to_txtcmds(txtcmds_path, profile)
                    if cheat_defenses is not None:
                        cheat_defenses["tool_traps"] = tool_trap_planted

                config_counter += 1
                config_attack_counter = 0
                config_path = base_path / f"hp_config_{config_counter}"
                full_logs_path = config_path / "full_logs"
                os.makedirs(full_logs_path, exist_ok=True)
                save_json_to_file(profile, config_path / "honeypot_config.json")
                if lure_chains:
                    save_json_to_file(lure_chains, config_path / "lure_chains.json")
                if cheat_defenses:
                    save_json_to_file(cheat_defenses, config_path / "cheat_defenses.json")
            else:
                print("Profile generation failed, continuing with current profile.")

            reconfigurator.reset()

            if not config.simulate_command_line:
                start_dockers()
                clear_hp_logs()
                log_extractor.reset_offset()
                wait_for_cowrie()
                wait_for_db()

        print("\n\n")
    stop_dockers()

if __name__ == "__main__":
    main()
