#!/usr/bin/env python3
"""
Interactive menu system for Project Violet.

Provides a user-friendly interface to:
1. Start new experiments with configurable parameters
2. Adjust settings (models, providers, profiles, sessions, etc.)
3. Prepare experiment data (extract and combine sessions)
4. Run Purple analysis on existing logs
"""

import questionary
import subprocess
import sys
import re
import os
import json
from pathlib import Path
from Sangria.model import LLMModel, ReconfigCriteria
from Sangria.extraction import extract_session, extract_everything_session
from Utils.jsun import load_json, save_json_to_file, append_json_to_file

PROJECT_ROOT = Path(__file__).parent
PROFILES_DIR = PROJECT_ROOT / "Reconfigurator" / "profiles"
CONFIG_PATH = PROJECT_ROOT / "config.py"

MENU_STYLE = questionary.Style([
    ('question', 'bold'),
    ('pointer', 'fg:cyan bold'),
    ('highlighted', 'fg:cyan bold'),
])

# Known provider base URLs (mirrors Utils/llm_client.py)
_PROVIDER_URLS = {
    "openai": "(default OpenAI endpoint)",
    "togetherai": "https://api.together.xyz/v1",
    "ollama": "http://localhost:11434/v1",
    "vllm": "http://localhost:8000/v1",
    "lmstudio": "http://localhost:1234/v1",
    "custom": "(user-defined)",
}


# ============================================================
# Main menu
# ============================================================

def main():
    """Main entry point for the interactive menu."""
    print("\n" + "=" * 60)
    print(" " * 15 + "PROJECT VIOLET")
    print("=" * 60 + "\n")

    while True:
        choice = show_main_menu()

        if choice == "Start New Experiment":
            configure_experiment()
        elif choice == "Demo Mode":
            run_demo_mode()
        elif choice == "Settings":
            show_settings_menu()
        elif choice == "Prepare Experiment Data":
            prepare_experiment_data()
        elif choice == "Run Purple Analysis":
            run_purple_analysis()
        elif choice == "Exit":
            print("\nGoodbye!")
            break


def show_main_menu():
    """Display main menu and return user choice."""
    return questionary.select(
        "What would you like to do?",
        choices=[
            "Start New Experiment",
            "Demo Mode",
            "Settings",
            "Prepare Experiment Data",
            "Run Purple Analysis",
            "Exit"
        ],
        style=MENU_STYLE,
    ).ask()


# ============================================================
# Demo mode
# ============================================================

def run_demo_mode():
    """Launch an interactive demo showcasing honeypot capabilities."""
    from demo import DemoRunner, HoneyNetDemoRunner

    print("\n" + "-" * 60)
    print(" " * 20 + "DEMO MODE")
    print("-" * 60 + "\n")

    # Choose demo type
    demo_type = questionary.select(
        "Select demo type:",
        choices=[
            questionary.Choice(title="Single Honeypot — one Cowrie instance", value="single"),
            questionary.Choice(title="HoneyNet — multi-hop chain with lateral movement", value="honeynet"),
        ],
        style=MENU_STYLE,
    ).ask()

    if not demo_type:
        return

    if demo_type == "honeynet":
        _run_honeynet_demo(HoneyNetDemoRunner)
    else:
        _run_single_demo(DemoRunner)


def _run_single_demo(DemoRunner):
    """Launch a single-pot demo."""
    profiles = _discover_profiles()
    if not profiles:
        print("No profiles found in Reconfigurator/profiles/\n")
        return

    choices = [
        questionary.Choice(title=_summarize_profile(name, data), value=str(path))
        for name, path, data in profiles
        if not name.endswith("_lure_chains") and "backup" not in name
    ]
    if not choices:
        print("No valid profiles found.\n")
        return

    profile_path = questionary.select(
        "Select a profile for the demo:",
        choices=choices,
        style=MENU_STYLE,
    ).ask()

    if not profile_path:
        return

    speed = _select_speed()
    if not speed:
        return

    print()
    runner = DemoRunner(profile_path, speed)
    try:
        runner.run()
    except KeyboardInterrupt:
        print(f"\n\n\033[33mDemo interrupted.\033[0m")
        runner.teardown()


def _run_honeynet_demo(HoneyNetDemoRunner):
    """Launch a multi-hop HoneyNet demo."""
    profiles = _discover_profiles()
    if not profiles:
        print("No profiles found in Reconfigurator/profiles/\n")
        return

    valid = [
        (name, path, data) for name, path, data in profiles
        if not name.endswith("_lure_chains") and "backup" not in name
    ]
    if len(valid) < 2:
        print("Need at least 2 profiles for a HoneyNet demo.\n")
        return

    # Preset chains or custom selection
    preset_choices = []

    # Build presets from profiles that exist
    profile_map = {name: str(path) for name, path, _ in valid}
    if all(p in profile_map for p in ("wordpress_server", "database_server", "cicd_runner")):
        preset_choices.append(questionary.Choice(
            title="WordPress -> Database -> CI/CD (3 hops)",
            value=[profile_map["wordpress_server"], profile_map["database_server"], profile_map["cicd_runner"]],
        ))
    if all(p in profile_map for p in ("wordpress_server", "database_server")):
        preset_choices.append(questionary.Choice(
            title="WordPress -> Database (2 hops)",
            value=[profile_map["wordpress_server"], profile_map["database_server"]],
        ))
    if all(p in profile_map for p in ("mail_server", "file_server", "backup_server")):
        preset_choices.append(questionary.Choice(
            title="Mail -> File Server -> Backup (3 hops)",
            value=[profile_map["mail_server"], profile_map["file_server"], profile_map["backup_server"]],
        ))

    preset_choices.append(questionary.Choice(
        title="Custom — pick profiles manually",
        value="custom",
    ))

    chain = questionary.select(
        "Select HoneyNet chain:",
        choices=preset_choices,
        style=MENU_STYLE,
    ).ask()

    if not chain:
        return

    if chain == "custom":
        # Multi-select profiles
        profile_choices = [
            questionary.Choice(title=_summarize_profile(name, data), value=str(path))
            for name, path, data in valid
        ]
        selected = questionary.checkbox(
            "Select profiles for the chain (in order, min 2):",
            choices=profile_choices,
            style=MENU_STYLE,
        ).ask()

        if not selected or len(selected) < 2:
            print("Need at least 2 profiles for a HoneyNet chain.\n")
            return
        chain = selected

    speed = _select_speed()
    if not speed:
        return

    print()
    runner = HoneyNetDemoRunner(chain, speed)
    try:
        runner.run()
    except KeyboardInterrupt:
        print(f"\n\n\033[33mDemo interrupted.\033[0m")
        runner.teardown()


def _select_speed() -> str | None:
    """Prompt user for demo speed selection."""
    return questionary.select(
        "Demo speed:",
        choices=[
            questionary.Choice(title="Normal — typewriter effect with pauses", value="normal"),
            questionary.Choice(title="Fast — quick typewriter, short pauses", value="fast"),
            questionary.Choice(title="Interactive — pause between sections", value="interactive"),
        ],
        style=MENU_STYLE,
    ).ask()


# ============================================================
# Settings menu
# ============================================================

def show_settings_menu():
    """Settings submenu loop."""
    while True:
        print("\n" + "-" * 60)
        print(" " * 20 + "SETTINGS")
        print("-" * 60 + "\n")

        choice = questionary.select(
            "What would you like to configure?",
            choices=[
                "View Current Settings",
                "Honeypot Profile",
                "Models & Providers",
                "Session Parameters",
                "Reconfiguration",
                "Attacker Options",
                "HoneyNet",
                "CHeaT Defenses",
                "Restore Lure Secrets",
                "Back to Main Menu",
            ],
            style=MENU_STYLE,
        ).ask()

        if choice == "View Current Settings":
            view_current_settings()
        elif choice == "Honeypot Profile":
            settings_profile()
        elif choice == "Models & Providers":
            settings_models()
        elif choice == "Session Parameters":
            settings_sessions()
        elif choice == "Reconfiguration":
            settings_reconfig()
        elif choice == "Attacker Options":
            settings_attacker()
        elif choice == "HoneyNet":
            settings_honeynet()
        elif choice == "CHeaT Defenses":
            settings_cheat()
        elif choice == "Restore Lure Secrets":
            restore_lure_secrets()
        elif choice == "Back to Main Menu":
            break


def view_current_settings():
    """Print all current config values in a formatted table."""
    import config

    print("\n" + "=" * 60)
    print(" " * 15 + "CURRENT SETTINGS")
    print("=" * 60)

    print("\nExperiment:")
    print(f"  Name                    : {config.experiment_name}")
    print(f"  Run ID                  : {config.run_id}")

    print("\nLLM Provider:")
    print(f"  Provider                : {config.llm_provider}")
    base_url_display = config.llm_base_url or _PROVIDER_URLS.get(config.llm_provider, "")
    print(f"  Base URL                : {base_url_display}")
    _env_key = {"togetherai": "TOGETHER_AI_SECRET_KEY"}.get(config.llm_provider, "OPENAI_API_KEY")
    print(f"  API Key                 : {'(custom)' if config.llm_api_key else f'({_env_key} env var)'}")

    print("\nModels:")
    _fmt = lambda m: getattr(m, "value", m) or "(not set)"
    print(f"  Sangria (Attacker)      : {_fmt(config.llm_model_sangria)}")
    print(f"  Honeypot LLM            : {_fmt(config.llm_model_honeypot)}")
    print(f"  Reconfigurator          : {_fmt(config.llm_model_reconfig)}")

    print("\nHoneypot LLM Provider (Docker):")
    print(f"  Provider                : {config.llm_provider_hp}")
    hp_url_display = config.llm_base_url_hp or _PROVIDER_URLS.get(config.llm_provider_hp, "")
    print(f"  Base URL                : {hp_url_display}")
    print(f"  API Key                 : {'(custom)' if config.llm_api_key_hp else '(OPENAI_API_KEY env var)'}")

    print("\nHoneypot Profile:")
    print(f"  Initial Profile         : {config.initial_profile}")
    print(f"  Novelty Threshold       : {config.profile_novelty_threshold}")

    print("\nSession Parameters:")
    print(f"  Number of Sessions      : {config.num_of_sessions}")
    print(f"  Max Session Length      : {config.max_session_length} turns")
    print(f"  Confirm Before Session  : {config.confirm_before_session}")

    print("\nReconfiguration:")
    print(f"  Method                  : {config.reconfig_method}")
    if str(config.reconfig_method) == "basic":
        print(f"  Interval                : {config.ba_interval} sessions")
    elif str(config.reconfig_method) == "entropy":
        print(f"  Variable                : {config.en_variable}")
        print(f"  Tolerance               : {config.en_tolerance}")
        print(f"  Window Size             : {config.en_window_size}")
    elif str(config.reconfig_method) == "t_test":
        print(f"  Variable                : {config.tt_variable}")
        print(f"  Tolerance               : {config.tt_tolerance}")
        print(f"  Confidence              : {config.tt_confidence}")

    print("\nAttacker Options:")
    print(f"  Simulate CLI            : {config.simulate_command_line}")
    print(f"  Provide Credentials     : {config.provide_honeypot_credentials}")

    honeynet_status = "ENABLED" if config.honeynet_enabled else "DISABLED"
    print(f"\nHoneyNet ({honeynet_status}):")
    if config.honeynet_enabled:
        for i, p in enumerate(config.chain_profiles, 1):
            db_flag = " [DB]" if config.chain_db_enabled[i - 1] else ""
            print(f"  Hop {i}                   : {Path(p).stem}{db_flag}")

    cheat_status = "ENABLED" if config.cheat_enabled else "DISABLED"
    print(f"\nCHeaT Defenses ({cheat_status}):")
    if config.cheat_enabled:
        print(f"  Unicode Honeytokens     : {config.cheat_unicode_honeytokens}")
        print(f"  Canary URLs             : {config.cheat_canary_urls}")
        print(f"  Prompt Traps            : {config.cheat_prompt_traps}")
        print(f"  Tool Output Traps       : {config.cheat_tool_traps}")
        print(f"  Overwhelm               : {config.cheat_overwhelm}")

    print("=" * 60 + "\n")


# ============================================================
# Honeypot Profile settings
# ============================================================

def settings_profile():
    """Profile submenu loop."""
    while True:
        import config
        current_name = Path(config.initial_profile).stem

        print(f"\n--- Honeypot Profile (current: {current_name}) ---\n")

        choice = questionary.select(
            "Profile options:",
            choices=[
                "Browse & Select Profile",
                "Preview Current Profile",
                "Back to Settings",
            ],
            style=MENU_STYLE,
        ).ask()

        if choice == "Browse & Select Profile":
            browse_profiles()
        elif choice == "Preview Current Profile":
            preview_profile(PROJECT_ROOT / config.initial_profile)
        elif choice == "Back to Settings":
            break


def _discover_profiles():
    """Return (name, path, profile_dict) for each .json in profiles/."""
    profiles = []
    if not PROFILES_DIR.exists():
        return profiles
    for p in sorted(PROFILES_DIR.glob("*.json")):
        try:
            with open(p) as f:
                data = json.load(f)
            if not isinstance(data, dict):
                continue
            profiles.append((p.stem, p, data))
        except (json.JSONDecodeError, OSError):
            continue
    return profiles


def _summarize_profile(name, profile):
    """One-line summary from a profile dict."""
    sys_info = profile.get("system", {})
    os_name = sys_info.get("os", "Unknown OS")
    hostname = sys_info.get("hostname", "unknown")
    services = ", ".join(s.get("name", "?") for s in profile.get("services", []))
    return f"{name} -- {os_name} | {hostname} | {services}"


def browse_profiles():
    """Scan profiles directory, show summaries, prompt selection."""
    profiles = _discover_profiles()
    if not profiles:
        print("\nNo profiles found in Reconfigurator/profiles/\n")
        return

    import config
    current_name = Path(config.initial_profile).stem

    choices = []
    for name, path, data in profiles:
        summary = _summarize_profile(name, data)
        marker = " (current)" if name == current_name else ""
        choices.append(questionary.Choice(title=f"{summary}{marker}", value=name))

    selected = questionary.select(
        "Select a honeypot profile:",
        choices=choices,
        style=MENU_STYLE,
    ).ask()

    if selected and selected != current_name:
        new_path = f"Reconfigurator/profiles/{selected}.json"
        apply_partial_config({"initial_profile": new_path})
        print(f"\n  Profile changed to: {selected}\n")
    elif selected == current_name:
        print(f"\n  Already using: {selected}\n")


def preview_profile(profile_path):
    """Load and pretty-print a profile card."""
    try:
        with open(profile_path) as f:
            profile = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"\n  Could not load profile: {e}\n")
        return

    name = Path(profile_path).stem
    sys_info = profile.get("system", {})

    print("\n" + "=" * 55)
    print(f"  PROFILE: {name}")
    print("=" * 55)

    print(f"  OS         : {sys_info.get('os', 'N/A')}")
    print(f"  Hostname   : {sys_info.get('hostname', 'N/A')}")
    print(f"  Kernel     : {sys_info.get('kernel_version', 'N/A')}")
    print(f"  Arch       : {sys_info.get('arch', 'N/A')}")

    print("-" * 55)
    print("  Users:")
    for u in profile.get("users", []):
        sudo = ""
        if u.get("sudo_rules"):
            sudo = "  sudo: NOPASSWD" if "NOPASSWD" in u.get("sudo_rules", "") else "  sudo: yes"
        elif u.get("uid") == 0:
            sudo = "  sudo: root"
        print(f"    {u['name']} (uid={u['uid']})  {u.get('shell', '')}  {sudo}")

    print("-" * 55)
    print("  Services:")
    for s in profile.get("services", []):
        ports = ", ".join(str(p) for p in s.get("ports", []))
        print(f"    {s['name']}  ports: {ports}")

    ssh_cfg = profile.get("ssh_config", {})
    if ssh_cfg:
        print("-" * 55)
        print("  SSH Config:")
        print(f"    Port: {ssh_cfg.get('port', 22)}"
              f" | Root login: {'yes' if ssh_cfg.get('permit_root_login', True) else 'no'}"
              f" | Password auth: {'yes' if ssh_cfg.get('password_auth', True) else 'no'}")
        accepted = ssh_cfg.get("accepted_passwords", {})
        if accepted:
            creds = ", ".join(f"{user}/{pw}" for user, pws in accepted.items() for pw in pws[:2])
            print(f"    Accepted: {creds}")

    desc = profile.get("description", "")
    if desc:
        print("-" * 55)
        print(f"  Description: {desc}")

    print("=" * 55 + "\n")


# ============================================================
# Models & Providers settings
# ============================================================

def settings_models():
    """Edit provider + model selections."""
    import config

    print("\n--- Models & Providers ---\n")

    # Provider selection
    current_provider = config.llm_provider
    provider = questionary.select(
        f"LLM Provider (current: {current_provider}):",
        choices=[
            questionary.Choice("OpenAI API", value="openai"),
            questionary.Choice("Together AI", value="togetherai"),
            questionary.Choice("Ollama (local)", value="ollama"),
            questionary.Choice("vLLM (local)", value="vllm"),
            questionary.Choice("LM Studio (local)", value="lmstudio"),
            questionary.Choice("Custom endpoint", value="custom"),
        ],
        style=MENU_STYLE,
    ).ask()

    _CLOUD_PROVIDERS = {"openai", "togetherai"}
    updates = {"llm_provider": provider}

    # Custom base URL
    if provider == "custom":
        base_url = questionary.text(
            "Enter base URL (e.g. http://localhost:8000/v1):",
            default=config.llm_base_url or "",
        ).ask()
        updates["llm_base_url"] = base_url
    elif provider not in _CLOUD_PROVIDERS:
        # Show the auto-filled URL, allow override
        default_url = _PROVIDER_URLS.get(provider, "")
        print(f"  Base URL: {default_url}")
        override = questionary.confirm("Override default base URL?", default=False).ask()
        if override:
            base_url = questionary.text("Enter base URL:", default=default_url).ask()
            updates["llm_base_url"] = base_url
        else:
            updates["llm_base_url"] = ""
    else:
        updates["llm_base_url"] = ""

    # API key
    _ENV_KEY_NAMES = {"openai": "OPENAI_API_KEY", "togetherai": "TOGETHER_AI_SECRET_KEY"}
    if provider not in _CLOUD_PROVIDERS:
        custom_key = questionary.confirm(
            "Set a custom API key? (default: OPENAI_API_KEY env var)",
            default=False,
        ).ask()
        if custom_key:
            key = questionary.text("Enter API key:").ask()
            updates["llm_api_key"] = key
        else:
            updates["llm_api_key"] = ""
    else:
        env_name = _ENV_KEY_NAMES.get(provider, "OPENAI_API_KEY")
        print(f"  Using {env_name} from environment.")
        updates["llm_api_key"] = ""

    # Tool calling warning for local providers
    if provider not in _CLOUD_PROVIDERS:
        print("\n  Note: Sangria (attacker) requires tool calling support.")
        print("  Ensure your model supports OpenAI-compatible function calling.")
        print("  Recommended: Qwen2.5-32B+, Llama3.1-70B+, Mistral-Nemo\n")

    # Model selections
    is_local = provider not in _CLOUD_PROVIDERS

    print("\n--- Model Selection ---")
    for field, label in [
        ("llm_model_sangria", "Sangria (Attacker)"),
        ("llm_model_honeypot", "Honeypot LLM"),
        ("llm_model_reconfig", "Reconfigurator"),
    ]:
        result = _prompt_model(label, getattr(config, field), is_local, provider)
        if result is not None:
            updates[field] = result

    # Honeypot provider (separate for Docker)
    print("\n--- Honeypot Provider (Docker) ---")
    print("  The Cowrie honeypot LLM runs inside Docker.")
    print("  It can use a different provider/endpoint.\n")

    same_provider = questionary.confirm(
        "Use same provider for honeypot?",
        default=True,
    ).ask()

    if same_provider:
        updates["llm_provider_hp"] = provider
        if provider not in _CLOUD_PROVIDERS and not updates.get("llm_base_url"):
            # Auto-rewrite for Docker: localhost -> host.docker.internal
            default_url = _PROVIDER_URLS.get(provider, "")
            docker_url = default_url.replace("localhost", "host.docker.internal")
            updates["llm_base_url_hp"] = docker_url
        else:
            hp_url = updates.get("llm_base_url", "")
            if hp_url:
                hp_url = hp_url.replace("localhost", "host.docker.internal")
                hp_url = hp_url.replace("127.0.0.1", "host.docker.internal")
            updates["llm_base_url_hp"] = hp_url
        updates["llm_api_key_hp"] = updates.get("llm_api_key", "")
    else:
        hp_provider = questionary.select(
            "Honeypot LLM Provider:",
            choices=[
                questionary.Choice("OpenAI API", value="openai"),
                questionary.Choice("Together AI", value="togetherai"),
                questionary.Choice("Ollama (local)", value="ollama"),
                questionary.Choice("vLLM (local)", value="vllm"),
                questionary.Choice("LM Studio (local)", value="lmstudio"),
                questionary.Choice("Custom endpoint", value="custom"),
            ],
            style=MENU_STYLE,
        ).ask()
        updates["llm_provider_hp"] = hp_provider

        if hp_provider == "custom":
            hp_url = questionary.text("Enter honeypot base URL:").ask()
        elif hp_provider not in {"openai", "togetherai"}:
            default_url = _PROVIDER_URLS.get(hp_provider, "")
            hp_url = default_url.replace("localhost", "host.docker.internal")
            print(f"  Docker base URL: {hp_url}")
        else:
            hp_url = ""
        updates["llm_base_url_hp"] = hp_url
        updates["llm_api_key_hp"] = ""

    apply_partial_config(updates)
    print("\n  Models & Providers updated.\n")


_MODEL_MENUS = {
    "openai": {
        "GPT_4_1_NANO": "gpt-4.1-nano",
        "GPT_4_1": "gpt-4.1",
        "GPT_4_1_MINI": "gpt-4.1-mini (Recommended)",
        "O4_MINI": "o4-mini",
    },
    "togetherai": {
        "LLAMA_3_3_70B": "Llama 3.3 70B Instruct Turbo (Recommended)",
        "LLAMA_4_MAVERICK": "Llama 4 Maverick 17B-128E FP8",
        "QWEN_3_5_397B": "Qwen 3.5 397B-A17B",
        "DEEPSEEK_V3": "DeepSeek V3",
        "DEEPSEEK_R1": "DeepSeek R1",
    },
}


def _prompt_model(component_name, current_value, is_local, provider="openai"):
    """Prompt for model selection — dropdown for cloud providers, free text for local."""
    if is_local:
        return questionary.text(
            f"Model for {component_name}:",
            default=str(current_value),
        ).ask()
    else:
        model_descriptions = _MODEL_MENUS.get(provider, _MODEL_MENUS["openai"])
        choices = [
            questionary.Choice(title=desc, value=model)
            for model, desc in model_descriptions.items()
        ]

        return questionary.select(
            f"Select model for {component_name}:",
            choices=choices,
        ).ask()


# ============================================================
# Session Parameters settings
# ============================================================

def settings_sessions():
    """Edit session count and max length."""
    import config

    print("\n--- Session Parameters ---\n")

    num = questionary.text(
        "Number of sessions:",
        default=str(config.num_of_sessions),
        validate=lambda x: (x.isdigit() and int(x) > 0) or "Must be a positive integer",
    ).ask()

    length = questionary.text(
        "Maximum session length (turns):",
        default=str(config.max_session_length),
        validate=lambda x: (x.isdigit() and int(x) > 0) or "Must be a positive integer",
    ).ask()

    confirm = questionary.confirm(
        "Confirm before executing each attack session?",
        default=config.confirm_before_session,
    ).ask()

    apply_partial_config({
        "num_of_sessions": int(num),
        "max_session_length": int(length),
        "confirm_before_session": confirm,
    })
    print("\n  Session parameters updated.\n")


# ============================================================
# Reconfiguration settings
# ============================================================

def settings_reconfig():
    """Edit reconfiguration method and parameters."""
    print("\n--- Reconfiguration Settings ---\n")

    reconfig_method, reconfig_params = prompt_reconfig_method()
    updates = {"reconfig_method": reconfig_method}
    updates.update(reconfig_params)
    apply_partial_config(updates)
    print("\n  Reconfiguration settings updated.\n")


# ============================================================
# Attacker Options settings
# ============================================================

def settings_attacker():
    """Edit attacker-related options."""
    import config

    print("\n--- Attacker Options ---\n")

    simulate = questionary.confirm(
        "Simulate command line outputs?",
        default=config.simulate_command_line,
    ).ask()

    creds = questionary.confirm(
        "Provide target credentials to attacker? (Skips reconnaissance, saves tokens)",
        default=config.provide_honeypot_credentials,
    ).ask()

    apply_partial_config({
        "simulate_command_line": simulate,
        "provide_honeypot_credentials": creds,
    })
    print("\n  Attacker options updated.\n")


# ============================================================
# HoneyNet settings
# ============================================================

def settings_honeynet():
    """HoneyNet multi-hop chain settings submenu."""
    import config

    while True:
        print("\n--- HoneyNet Settings ---\n")

        status = "ENABLED" if config.honeynet_enabled else "DISABLED"
        print(f"  Status: {status}")
        if config.honeynet_enabled:
            for i, p in enumerate(config.chain_profiles, 1):
                db_flag = " [DB]" if config.chain_db_enabled[i - 1] else ""
                print(f"  Hop {i}: {Path(p).stem}{db_flag}")
        print()

        choice = questionary.select(
            "HoneyNet options:",
            choices=[
                questionary.Choice(
                    title=f"{'Disable' if config.honeynet_enabled else 'Enable'} HoneyNet",
                    value="toggle",
                ),
                questionary.Choice(title="Configure chain profiles", value="profiles"),
                questionary.Choice(title="Back", value="back"),
            ],
            style=MENU_STYLE,
        ).ask()

        if choice == "back":
            break

        elif choice == "toggle":
            new_val = not config.honeynet_enabled
            apply_partial_config({"honeynet_enabled": new_val})
            config.honeynet_enabled = new_val
            print(f"\n  HoneyNet {'enabled' if new_val else 'disabled'}.\n")

        elif choice == "profiles":
            _configure_chain_profiles()


def _configure_chain_profiles():
    """Interactive editor for chain_profiles and chain_db_enabled."""
    import config

    # Discover available profiles
    available = sorted(
        [p.stem for p in PROFILES_DIR.glob("*.json") if "lure_chains" not in p.name]
    )

    if not available:
        print("\n  No profiles found in Reconfigurator/profiles/\n")
        return

    # Ask how many hops
    num_hops = questionary.text(
        "Number of hops in the chain:",
        default=str(len(config.chain_profiles)),
        validate=lambda x: (x.isdigit() and 1 <= int(x) <= 10) or "Enter 1-10",
    ).ask()
    num_hops = int(num_hops)

    chain = []
    db_flags = []

    for i in range(num_hops):
        # Default to existing profile if available
        current = Path(config.chain_profiles[i]).stem if i < len(config.chain_profiles) else available[0]
        default_idx = available.index(current) if current in available else 0

        profile_name = questionary.select(
            f"Hop {i + 1} profile:",
            choices=available,
            default=available[default_idx],
            style=MENU_STYLE,
        ).ask()

        db_default = config.chain_db_enabled[i] if i < len(config.chain_db_enabled) else False
        db_enabled = questionary.confirm(
            f"  Enable database honeypot for hop {i + 1}?",
            default=db_default,
        ).ask()

        chain.append(f"Reconfigurator/profiles/{profile_name}.json")
        db_flags.append(db_enabled)

    # Write to config
    _write_chain_config(chain, db_flags)

    # Update runtime config
    config.chain_profiles = chain
    config.chain_db_enabled = db_flags

    print(f"\n  Chain configured with {num_hops} hop(s).\n")


def _write_chain_config(chain_profiles: list[str], chain_db_enabled: list[bool]):
    """Write chain_profiles and chain_db_enabled lists to config.py."""
    with open(CONFIG_PATH, "r") as f:
        content = f.read()

    # Replace chain_profiles list
    profiles_str = ",\n".join(f'    "{p}"' for p in chain_profiles)
    content = re.sub(
        r"chain_profiles = \[.*?\]",
        f"chain_profiles = [\n{profiles_str},\n]",
        content,
        flags=re.DOTALL,
    )

    # Replace chain_db_enabled list
    db_str = ", ".join(str(v) for v in chain_db_enabled)
    content = re.sub(
        r"chain_db_enabled = \[.*?\]",
        f"chain_db_enabled = [{db_str}]",
        content,
    )

    with open(CONFIG_PATH, "w") as f:
        f.write(content)


# ============================================================
# CHeaT Defense settings
# ============================================================

_CHEAT_TECHNIQUES = [
    ("cheat_unicode_honeytokens", "Unicode Honeytokens",
     "Inject unicode chars (backspace, tag, soft-hyphen) into credentials.\n"
     "  LLMs process these differently from humans, revealing their nature."),
    ("cheat_canary_urls", "Canary URLs",
     "Plant honey URLs in .bash_history, READMEs, and configs.\n"
     "  If the attacker fetches them, it confirms automated behavior."),
    ("cheat_prompt_traps", "Prompt Traps",
     "Embed prompt injection payloads in file contents (HTML comments, logs, /etc/motd).\n"
     "  These can convince an LLM to stop attacking or change behavior."),
    ("cheat_tool_traps", "Tool Output Traps",
     "Inject trap payloads into txtcmd outputs (cat, ls, systemctl, etc.).\n"
     "  Adds fake vulnerability info or 'test ended' messages to command output."),
    ("cheat_overwhelm", "Overwhelm",
     "Flood attacker with fake CVEs, fake open ports, and expensive commands.\n"
     "  Wastes LLM tokens and time on non-existent vulnerabilities."),
]


def settings_cheat():
    """CHeaT defense settings submenu."""
    import config

    while True:
        print("\n--- CHeaT Defenses (Proactive LLM Attacker Detection) ---\n")

        master_status = "ENABLED" if config.cheat_enabled else "DISABLED"
        print(f"  Master toggle: {master_status}\n")

        if config.cheat_enabled:
            for key, name, _ in _CHEAT_TECHNIQUES:
                val = getattr(config, key)
                mark = "[x]" if val else "[ ]"
                print(f"  {mark} {name}")
            print()

        choice = questionary.select(
            "CHeaT options:",
            choices=[
                f"{'Disable' if config.cheat_enabled else 'Enable'} CHeaT (master toggle)",
                "Toggle Individual Techniques",
                "Enable All Techniques",
                "Disable All Techniques",
                "Technique Descriptions",
                "Back to Settings",
            ],
            style=MENU_STYLE,
        ).ask()

        if choice and "master toggle" in choice:
            new_val = not config.cheat_enabled
            apply_partial_config({"cheat_enabled": new_val})
            config.cheat_enabled = new_val
            print(f"\n  CHeaT {'enabled' if new_val else 'disabled'}.\n")

        elif choice == "Toggle Individual Techniques":
            if not config.cheat_enabled:
                print("\n  Enable the master toggle first.\n")
                continue
            _cheat_toggle_techniques()

        elif choice == "Enable All Techniques":
            updates = {key: True for key, _, _ in _CHEAT_TECHNIQUES}
            updates["cheat_enabled"] = True
            apply_partial_config(updates)
            for key, _, _ in _CHEAT_TECHNIQUES:
                setattr(config, key, True)
            config.cheat_enabled = True
            print("\n  All CHeaT techniques enabled.\n")

        elif choice == "Disable All Techniques":
            updates = {key: False for key, _, _ in _CHEAT_TECHNIQUES}
            apply_partial_config(updates)
            for key, _, _ in _CHEAT_TECHNIQUES:
                setattr(config, key, False)
            print("\n  All CHeaT techniques disabled.\n")

        elif choice == "Technique Descriptions":
            _cheat_show_descriptions()

        elif choice == "Back to Settings":
            break


def restore_lure_secrets():
    """Run the lure secrets restore/sanitize script."""
    script = PROJECT_ROOT / "scripts" / "restore_lure_secrets.sh"
    if not script.exists():
        print("\n  Script not found: scripts/restore_lure_secrets.sh\n")
        return

    choice = questionary.select(
        "Lure secrets action:",
        choices=[
            "Restore (deploy realistic lure values)",
            "Sanitize (replace with safe placeholders for git)",
            "Back to Settings",
        ],
        style=MENU_STYLE,
    ).ask()

    if choice and "Restore" in choice:
        result = subprocess.run(["bash", str(script)], capture_output=True, text=True)
        print(f"\n{result.stdout}")
        if result.returncode != 0:
            print(f"  Error: {result.stderr}\n")
    elif choice and "Sanitize" in choice:
        result = subprocess.run(
            ["bash", str(script), "--sanitize"], capture_output=True, text=True
        )
        print(f"\n{result.stdout}")
        if result.returncode != 0:
            print(f"  Error: {result.stderr}\n")


def _cheat_toggle_techniques():
    """Let user toggle individual CHeaT techniques via checkboxes."""
    import config

    selected = questionary.checkbox(
        "Select active techniques:",
        choices=[
            questionary.Choice(name, checked=getattr(config, key))
            for key, name, _ in _CHEAT_TECHNIQUES
        ],
        style=MENU_STYLE,
    ).ask()

    if selected is None:
        return

    selected_set = set(selected)
    updates = {}
    for key, name, _ in _CHEAT_TECHNIQUES:
        val = name in selected_set
        updates[key] = val
        setattr(config, key, val)

    apply_partial_config(updates)
    print("\n  CHeaT techniques updated.\n")


def _cheat_show_descriptions():
    """Print detailed descriptions of each CHeaT technique."""
    print("\n" + "=" * 60)
    print(" " * 12 + "CHeaT TECHNIQUE DESCRIPTIONS")
    print("=" * 60)
    for key, name, desc in _CHEAT_TECHNIQUES:
        print(f"\n  {name}:")
        print(f"  {desc}")
    print("\n" + "=" * 60 + "\n")


# ============================================================
# Config file writing (apply_partial_config)
# ============================================================

def apply_partial_config(updates):
    """Write a subset of config keys to config.py via regex replacement.

    Accepts a dict of {key: value} where key matches a config.py variable.
    Only writes the keys present in the dict.
    """
    with open(CONFIG_PATH, 'r') as f:
        content = f.read()

    # Model enum mapping
    model_mapping = {
        "GPT_4_1_NANO": "LLMModel.GPT_4_1_NANO",
        "GPT_4_1": "LLMModel.GPT_4_1",
        "GPT_4_1_MINI": "LLMModel.GPT_4_1_MINI",
        "O4_MINI": "LLMModel.O4_MINI",
        "LLAMA_4_MAVERICK": "LLMModel.LLAMA_4_MAVERICK",
        "LLAMA_3_3_70B": "LLMModel.LLAMA_3_3_70B",
        "QWEN_3_5_397B": "LLMModel.QWEN_3_5_397B",
        "DEEPSEEK_V3": "LLMModel.DEEPSEEK_V3",
        "DEEPSEEK_R1": "LLMModel.DEEPSEEK_R1",
    }

    reconfig_mapping = {
        "NO_RECONFIG": "ReconfigCriteria.NO_RECONFIG",
        "BASIC": "ReconfigCriteria.BASIC",
        "ENTROPY": "ReconfigCriteria.ENTROPY",
        "T_TEST": "ReconfigCriteria.T_TEST",
    }

    # String fields (quoted in config.py)
    string_fields = {
        "experiment_name", "run_id", "llm_provider", "llm_base_url", "llm_api_key",
        "llm_provider_hp", "llm_base_url_hp", "llm_api_key_hp", "initial_profile",
        "en_variable", "tt_variable",
    }

    # Bool fields
    bool_fields = {
        "simulate_command_line", "provide_honeypot_credentials",
        "honeynet_enabled",
        "cheat_enabled", "cheat_unicode_honeytokens", "cheat_canary_urls",
        "cheat_prompt_traps", "cheat_tool_traps", "cheat_overwhelm",
    }

    # Int fields
    int_fields = {"num_of_sessions", "max_session_length", "ba_interval", "en_window_size"}

    # Float fields (with type annotation)
    float_fields = {"en_tolerance", "tt_tolerance", "tt_confidence", "profile_novelty_threshold"}

    # Model fields — may be enum name (OpenAI) or plain string (local)
    model_fields = {"llm_model_sangria", "llm_model_honeypot", "llm_model_reconfig"}

    for key, value in updates.items():
        if key in string_fields:
            content = re.sub(
                rf'{key} = ".*?"',
                f'{key} = "{value}"',
                content,
            )

        elif key in bool_fields:
            content = re.sub(
                rf'{key} = (True|False)',
                f'{key} = {value}',
                content,
            )

        elif key in int_fields:
            # Handle both `name = N` and `name: int = N`
            content = re.sub(
                rf'{key}(: int)? = \d+',
                f'{key}\\1 = {value}',
                content,
            )

        elif key in float_fields:
            content = re.sub(
                rf'{key}: float = [\d.e\-+]+',
                f'{key}: float = {value}',
                content,
            )

        elif key in model_fields:
            if value in model_mapping:
                # OpenAI enum value
                content = re.sub(
                    rf'{key} = (?:LLMModel\.\w+|".*?")',
                    f'{key} = {model_mapping[value]}',
                    content,
                )
            else:
                # Local model — store as plain string
                content = re.sub(
                    rf'{key} = (?:LLMModel\.\w+|".*?")',
                    f'{key} = "{value}"',
                    content,
                )

        elif key == "reconfig_method":
            if value in reconfig_mapping:
                content = re.sub(
                    r'reconfig_method: ReconfigCriteria = ReconfigCriteria\.\w+',
                    f'reconfig_method: ReconfigCriteria = {reconfig_mapping[value]}',
                    content,
                )

    with open(CONFIG_PATH, 'w') as f:
        f.write(content)

    # Sync in-memory config module so changes take effect immediately
    # without needing a module reload (config is already cached in sys.modules).
    import config as _cfg
    for key, value in updates.items():
        if key in model_fields:
            from Sangria.model import LLMModel as _LLMModel
            if value in model_mapping:
                setattr(_cfg, key, _LLMModel[value])
            else:
                setattr(_cfg, key, value)
        elif key == "reconfig_method":
            from Sangria.model import ReconfigCriteria as _RC
            if value in reconfig_mapping:
                setattr(_cfg, key, _RC[value])
        elif key in int_fields:
            setattr(_cfg, key, int(value))
        elif key in float_fields:
            setattr(_cfg, key, float(value))
        elif key in bool_fields:
            setattr(_cfg, key, value if isinstance(value, bool) else value == "True")
        else:
            setattr(_cfg, key, value)


# ============================================================
# Configure experiment (full wizard — existing flow, updated)
# ============================================================

def configure_experiment():
    """Start a new experiment — only asks for the name, uses current settings for everything else."""
    import config as cfg

    print("\n" + "-" * 60)
    print("NEW EXPERIMENT")
    print("-" * 60 + "\n")

    name = prompt_experiment_name()
    if not name:
        return

    apply_partial_config({'experiment_name': name})

    # Show current settings so the user knows what will be used
    print("\nUsing current settings (change via Settings menu):")
    view_current_settings()

    run_experiment()


# ============================================================
# Wizard prompts (shared between wizard and settings)
# ============================================================

def prompt_experiment_name():
    """Prompt for experiment name."""
    return questionary.text(
        "Enter experiment name:",
        validate=lambda x: len(x.strip()) > 0 or "Experiment name cannot be empty"
    ).ask()


def prompt_run_id():
    """Prompt for run ID with validation."""
    return questionary.text(
        "Enter run ID (10-99, for parallel experiments):",
        default="10",
        validate=lambda x: (x.isdigit() and 10 <= int(x) <= 99) or "Run ID must be between 10 and 99"
    ).ask()


def prompt_reconfig_method():
    """Prompt for reconfiguration method and return (method, params)."""
    method_descriptions = {
        "NO_RECONFIG": "No reconfiguration (static honeypot)",
        "BASIC": "Basic - Reconfigure every N sessions",
        "ENTROPY": "Entropy - Entropy-based reconfiguration",
        "T_TEST": "T-Test - Statistical t-test based"
    }

    choices = [
        questionary.Choice(title=desc, value=method)
        for method, desc in method_descriptions.items()
    ]

    method = questionary.select(
        "Select reconfiguration method:",
        choices=choices
    ).ask()

    params = {}
    if method == "BASIC":
        params = prompt_basic_params()
    elif method == "ENTROPY":
        params = prompt_entropy_params()
    elif method == "T_TEST":
        params = prompt_ttest_params()

    return method, params


def prompt_basic_params():
    """Prompt for Basic reconfiguration parameters."""
    interval = questionary.text(
        "Reconfigure every N sessions:",
        default="100",
        validate=lambda x: (x.isdigit() and int(x) > 0) or "Must be a positive integer"
    ).ask()

    return {'ba_interval': int(interval)}


def prompt_entropy_params():
    """Prompt for Entropy reconfiguration parameters."""
    variable = questionary.select(
        "Variable to track:",
        choices=["techniques", "session_length"]
    ).ask()

    tolerance = questionary.text(
        "Entropy tolerance (0.0-1.0):",
        default="0.01",
        validate=lambda x: is_float(x) and 0.0 <= float(x) <= 1.0 or "Must be a float between 0.0 and 1.0"
    ).ask()

    window = questionary.text(
        "Window size:",
        default="1",
        validate=lambda x: (x.isdigit() and int(x) > 0) or "Must be a positive integer"
    ).ask()

    return {
        'en_variable': variable,
        'en_tolerance': float(tolerance),
        'en_window_size': int(window)
    }


def prompt_ttest_params():
    """Prompt for T-Test reconfiguration parameters."""
    variable = questionary.select(
        "Variable to track:",
        choices=["tactic_sequences", "session_length", "tactics"]
    ).ask()

    default_tolerance = {
        "session_length": "0.008",
        "tactics": "0.003",
        "tactic_sequences": "0.003"
    }.get(variable, "0.003")

    tolerance = questionary.text(
        f"Tolerance for {variable}:",
        default=default_tolerance,
        validate=lambda x: is_float(x) and float(x) > 0 or "Must be a positive float"
    ).ask()

    confidence = questionary.text(
        "Confidence level (0.0-1.0):",
        default="0.95",
        validate=lambda x: is_float(x) and 0.0 < float(x) < 1.0 or "Must be between 0.0 and 1.0"
    ).ask()

    return {
        'tt_variable': variable,
        'tt_tolerance': float(tolerance),
        'tt_confidence': float(confidence)
    }


def prompt_session_count():
    """Prompt for number of sessions."""
    return int(questionary.text(
        "Number of sessions:",
        default="2",
        validate=lambda x: (x.isdigit() and int(x) > 0) or "Must be a positive integer"
    ).ask())


def prompt_session_length():
    """Prompt for maximum session length."""
    return int(questionary.text(
        "Maximum session length (turns):",
        default="20",
        validate=lambda x: (x.isdigit() and int(x) > 0) or "Must be a positive integer"
    ).ask())


def prompt_simulate_cli():
    """Prompt for simulate command line option."""
    return questionary.confirm(
        "Simulate command line outputs?",
        default=False
    ).ask()


def prompt_provide_credentials():
    """Prompt for providing honeypot credentials to attacker."""
    return questionary.confirm(
        "Provide target credentials to attacker? (Skips reconnaissance, saves tokens)",
        default=False
    ).ask()


def confirm_configuration(config_data):
    """Display configuration summary and ask for confirmation."""
    print("\n" + "=" * 60)
    print(" " * 15 + "CONFIGURATION SUMMARY")
    print("=" * 60)

    print("\nExperiment Details:")
    print(f"  Name                    : {config_data.get('experiment_name', 'N/A')}")
    print(f"  Run ID                  : {config_data.get('run_id', 'N/A')}")

    print("\nLLM Provider:")
    provider = config_data.get('llm_provider', 'openai')
    print(f"  Provider                : {provider}")
    if provider != "openai":
        print(f"  Base URL                : {config_data.get('llm_base_url') or _PROVIDER_URLS.get(provider, '')}")

    print("\nModel Configuration:")
    print(f"  Sangria (Attacker)      : {config_data.get('llm_model_sangria', 'N/A')}")
    print(f"  Honeypot LLM            : {config_data.get('llm_model_honeypot', 'N/A')}")
    print(f"  Reconfigurator          : {config_data.get('llm_model_reconfig', 'N/A')}")

    if config_data.get('initial_profile'):
        print(f"\nHoneypot Profile          : {Path(config_data['initial_profile']).stem}")

    print("\nReconfiguration:")
    print(f"  Method                  : {config_data.get('reconfig_method', 'N/A')}")
    if config_data.get('reconfig_method') == 'BASIC':
        print(f"  Interval                : {config_data.get('ba_interval', 'N/A')} sessions")
    elif config_data.get('reconfig_method') == 'ENTROPY':
        print(f"  Variable                : {config_data.get('en_variable', 'N/A')}")
        print(f"  Tolerance               : {config_data.get('en_tolerance', 'N/A')}")
        print(f"  Window Size             : {config_data.get('en_window_size', 'N/A')}")
    elif config_data.get('reconfig_method') == 'T_TEST':
        print(f"  Variable                : {config_data.get('tt_variable', 'N/A')}")
        print(f"  Tolerance               : {config_data.get('tt_tolerance', 'N/A')}")
        print(f"  Confidence              : {config_data.get('tt_confidence', 'N/A')}")

    print("\nSession Parameters:")
    print(f"  Number of Sessions      : {config_data.get('num_of_sessions', 'N/A')}")
    print(f"  Max Session Length      : {config_data.get('max_session_length', 'N/A')} turns")

    print("\nAdditional Options:")
    print(f"  Simulate CLI            : {config_data.get('simulate_command_line', False)}")
    print(f"  Provide Credentials     : {config_data.get('provide_honeypot_credentials', False)}")

    print("=" * 60 + "\n")

    return questionary.confirm(
        "Proceed with this configuration?",
        default=True
    ).ask()


# ============================================================
# Experiment execution
# ============================================================

def run_experiment():
    """Execute the experiment."""
    print("\n" + "=" * 60)
    print(" " * 15 + "STARTING EXPERIMENT")
    print("=" * 60 + "\n")

    proceed = questionary.confirm(
        "Ready to start?",
        default=True
    ).ask()

    if not proceed:
        print("\nExperiment cancelled. Returning to main menu...\n")
        return

    try:
        import main
        main.main()
    except Exception as e:
        print(f"\n  Error running experiment: {e}\n")
        import traceback
        traceback.print_exc()


# ============================================================
# Prepare experiment data
# ============================================================

def prepare_experiment_data():
    """Extract and combine session data from raw logs."""
    print("\n" + "=" * 60)
    print(" " * 10 + "PREPARE EXPERIMENT DATA")
    print("=" * 60 + "\n")

    print("This tool extracts sessions from raw experiment logs and")
    print("prepares them for analysis.\n")

    logs_path = PROJECT_ROOT / "logs"

    if not logs_path.exists():
        print(f"  Logs directory not found at: {logs_path}\n")
        return

    all_experiments = sorted([d for d in os.listdir(logs_path) if (logs_path / d).is_dir()])

    if not all_experiments:
        print("  No experiments found in logs directory.\n")
        return

    # Ask extraction mode
    extract_omni = select_extraction_mode()

    # Select experiments
    selected_experiments = questionary.checkbox(
        "Select experiments to process:",
        choices=all_experiments
    ).ask()

    if not selected_experiments:
        print("\nNo experiments selected. Returning to main menu...\n")
        return

    # Confirm before processing
    print(f"\n  Will process {len(selected_experiments)} experiment(s)")
    print(f"   Extraction mode: {'All commands (omni)' if extract_omni else 'Honeypot commands only'}")

    proceed = questionary.confirm(
        "Proceed with data preparation?",
        default=True
    ).ask()

    if not proceed:
        print("\nCancelled. Returning to main menu...\n")
        return

    # Run extraction and combination
    run_extraction_process(logs_path, selected_experiments, extract_omni)
    run_combination_process(logs_path, selected_experiments, extract_omni)

    print("\n" + "=" * 60)
    print("  DATA PREPARATION COMPLETE")
    print("=" * 60)
    print("\nYou can now run Purple Analysis to visualize the data.\n")


def select_extraction_mode():
    """Ask user which extraction mode to use."""
    print("Choose extraction mode:\n")
    print("  Honeypot commands only: Extract only commands that reached the honeypot")
    print("  All commands (omni): Extract all attacker commands including reconnaissance\n")

    extract_omni = questionary.confirm(
        "Extract all commands (omni mode)?",
        default=False
    ).ask()

    return extract_omni


def safe_listdir(p: Path):
    """Return listdir if p exists and is a dir, else empty list."""
    return os.listdir(p) if p.exists() and p.is_dir() else []


def run_extraction_process(logs_path: Path, selected_experiments: list, extract_omni: bool):
    """Extract sessions from raw logs."""
    print("\n" + "-" * 60)
    print("STEP 1: EXTRACTING SESSIONS")
    print("-" * 60 + "\n")

    session_file_name = "omni_sessions.json" if extract_omni else "sessions.json"

    for experiment in selected_experiments:
        experiment_path = logs_path / experiment
        print(f">> Processing: {experiment}")

        configs = filter(lambda name: name.startswith("hp_config"), safe_listdir(experiment_path))
        sorted_configs = sorted(
            configs,
            key=lambda fn: int(Path(fn).stem.split('_')[-1])
        )

        if not sorted_configs:
            print(f"   No hp_config directories found, skipping.\n")
            continue

        all_sessions = []
        all_sessions_path = experiment_path / session_file_name

        for config in sorted_configs:
            config_path = experiment_path / config
            full_logs_path = config_path / "full_logs"
            session_path = config_path / session_file_name

            if not full_logs_path.exists():
                print(f"   {config}: No full_logs directory, skipping.")
                continue

            # Remove existing sessions file
            if session_path.exists():
                session_path.unlink()
                print(f"   Removed existing: {config}/{session_file_name}")

            attack_files = safe_listdir(full_logs_path)
            sorted_attacks = sorted(
                [f for f in attack_files if f.endswith('.json')],
                key=lambda fn: int(Path(fn).stem.split('_')[-1]) if '_' in Path(fn).stem else 0
            )

            extracted_count = 0
            for attack in sorted_attacks:
                attack_path = full_logs_path / attack
                try:
                    logs = load_json(attack_path)
                    if extract_omni:
                        session = extract_everything_session(logs)
                    else:
                        session = extract_session(logs)
                    all_sessions.append(session)
                    append_json_to_file(session, session_path, False)
                    extracted_count += 1
                except Exception as e:
                    print(f"   Error extracting {attack}: {e}")
                    continue

            print(f"   {config}: Extracted {extracted_count} sessions")

        # Save combined sessions at experiment level
        if all_sessions:
            save_json_to_file(all_sessions, all_sessions_path, False)
            print(f"   Created {session_file_name} ({len(all_sessions)} total sessions)\n")
        else:
            print(f"   No sessions extracted\n")


def run_combination_process(logs_path: Path, selected_experiments: list, extract_omni: bool):
    """Combine sessions across hp_configs."""
    print("-" * 60)
    print("STEP 2: COMBINING SESSIONS")
    print("-" * 60 + "\n")

    for experiment in selected_experiments:
        experiment_path = logs_path / experiment
        print(f">> Processing: {experiment}")

        configs = filter(lambda name: name.startswith("hp_config"), safe_listdir(experiment_path))
        sorted_configs = sorted(
            configs,
            key=lambda fn: int(Path(fn).stem.split('_')[-1])
        )

        if not sorted_configs:
            print(f"   No hp_config directories found, skipping.\n")
            continue

        # Combine regular sessions
        try:
            sessions_list = []
            for config in sorted_configs:
                session_file = experiment_path / config / "sessions.json"
                if session_file.exists():
                    sessions_list.append(load_json(session_file))

            if sessions_list:
                combined_sessions = sum(sessions_list, [])
                save_json_to_file(combined_sessions, experiment_path / "sessions.json")
                print(f"   Combined {len(combined_sessions)} regular sessions")
        except Exception as e:
            print(f"   Error combining sessions: {e}")

        # Combine omni sessions if requested
        if extract_omni:
            try:
                omni_sessions_list = []
                for config in sorted_configs:
                    omni_file = experiment_path / config / "omni_sessions.json"
                    if omni_file.exists():
                        omni_sessions_list.append(load_json(omni_file))

                if omni_sessions_list:
                    combined_omni_sessions = sum(omni_sessions_list, [])
                    save_json_to_file(combined_omni_sessions, experiment_path / "omni_sessions.json")
                    print(f"   Combined {len(combined_omni_sessions)} omni sessions")
            except Exception as e:
                print(f"   Error combining omni sessions: {e}")

        print()


# ============================================================
# Purple analysis
# ============================================================

def run_purple_analysis():
    """Launch Purple analysis tools with sub-menu."""
    print("\n" + "=" * 60)
    print(" " * 15 + "PURPLE ANALYSIS")
    print("=" * 60 + "\n")

    print("Purple Analysis provides multiple tools for analyzing your data:\n")
    print("  HP Comparison: Compare session lengths across experiments")
    print("  Meta Analysis: Analyze MITRE tactics, deceptiveness, patterns")
    print("  Advanced Visualizations: Create custom plots and charts\n")

    # Check if sessions exist
    logs_path = PROJECT_ROOT / "logs"
    if not check_sessions_exist(logs_path):
        print("  No processed session data found.\n")
        print("Please run 'Prepare Experiment Data' first to extract")
        print("sessions from your experiment logs.\n")

        should_prepare = questionary.confirm(
            "Go to Prepare Experiment Data now?",
            default=True
        ).ask()

        if should_prepare:
            prepare_experiment_data()
        return

    # Show Purple analysis sub-menu
    while True:
        choice = show_purple_menu()

        if choice == "HP Comparison Analysis":
            run_hp_comparison()
        elif choice == "Meta Analysis":
            run_meta_analysis()
        elif choice == "Advanced Visualizations":
            run_advanced_viz()
        elif choice == "Run All Analyses":
            run_all_purple_analyses()
        elif choice == "Back to Main Menu":
            break


def show_purple_menu():
    """Display Purple analysis sub-menu."""
    return questionary.select(
        "Select analysis to run:",
        choices=[
            "HP Comparison Analysis",
            "Meta Analysis",
            "Advanced Visualizations",
            "Run All Analyses",
            "Back to Main Menu"
        ],
        style=MENU_STYLE,
    ).ask()


def check_sessions_exist(logs_path: Path):
    """Check if any sessions.json files exist."""
    if not logs_path.exists():
        return False

    for exp_dir in logs_path.iterdir():
        if not exp_dir.is_dir():
            continue

        sessions_file = exp_dir / "sessions.json"
        omni_file = exp_dir / "omni_sessions.json"

        if sessions_file.exists() or omni_file.exists():
            return True

    return False


def run_hp_comparison():
    """Run HP comparison analysis."""
    print("\n" + "-" * 60)
    print("HP COMPARISON ANALYSIS")
    print("-" * 60 + "\n")

    hp_script = PROJECT_ROOT / "Purple" / "Data_analysis" / "hp_comparison_cli.py"

    if not hp_script.exists():
        print(f"  HP comparison script not found at: {hp_script}\n")
        return

    try:
        subprocess.run([sys.executable, str(hp_script)])
    except Exception as e:
        print(f"\n  Error running HP comparison: {e}\n")

    print()


def run_meta_analysis():
    """Run meta analysis."""
    print("\n" + "-" * 60)
    print("META ANALYSIS")
    print("-" * 60 + "\n")

    meta_script = PROJECT_ROOT / "Purple" / "Data_analysis" / "meta_analysis_cli.py"

    if not meta_script.exists():
        print(f"  Meta analysis script not found at: {meta_script}\n")
        return

    try:
        subprocess.run([sys.executable, str(meta_script)])
    except Exception as e:
        print(f"\n  Error running meta analysis: {e}\n")

    print()


def run_advanced_viz():
    """Run advanced visualization tool."""
    print("\n" + "-" * 60)
    print("ADVANCED VISUALIZATIONS")
    print("-" * 60 + "\n")

    viz_script = PROJECT_ROOT / "Purple" / "Data_analysis" / "run_analysis.py"

    if not viz_script.exists():
        print(f"  Visualization script not found at: {viz_script}\n")
        return

    try:
        subprocess.run([sys.executable, str(viz_script)])
    except Exception as e:
        print(f"\n  Error running visualizations: {e}\n")

    print()


def run_all_purple_analyses():
    """Run all Purple analyses in sequence."""
    print("\n" + "=" * 60)
    print("RUNNING ALL PURPLE ANALYSES")
    print("=" * 60 + "\n")

    proceed = questionary.confirm(
        "This will run HP Comparison, Meta Analysis, and Visualizations in sequence. Continue?",
        default=True
    ).ask()

    if not proceed:
        print("\nCancelled.\n")
        return

    print("\n[1/3] Running HP Comparison...")
    run_hp_comparison()

    print("\n[2/3] Running Meta Analysis...")
    run_meta_analysis()

    print("\n[3/3] Running Advanced Visualizations...")
    run_advanced_viz()

    print("\n" + "=" * 60)
    print("  ALL ANALYSES COMPLETE")
    print("=" * 60 + "\n")


# ============================================================
# Helpers
# ============================================================

def is_float(value):
    """Check if value can be converted to float."""
    try:
        float(value)
        return True
    except ValueError:
        return False


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n  Unexpected error: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
