from Blue_Lagoon.credential_chain import CredentialTier
from Sangria.model import LLMModel, ReconfigCriteria

experiment_name = "Test_credential_cracking_tiers"
run_id = "10" # 10 - 99, If multiple experiments are run in parallel, each need unique run_id.

# LLM Provider settings (Sangria, Reconfigurator, Terminal IO)
llm_provider = "togetherai"           # "openai" | "openrouter" | "togetherai" | "ollama" | "vllm" | "lmstudio" | "custom"
llm_base_url = ""                 # Empty = default OpenAI endpoint
llm_api_key = ""                  # Empty = use OPENAI_API_KEY env var

# Honeypot LLM provider (separate — runs inside Docker, may need host.docker.internal)
llm_provider_hp = "togetherai"        # "openai" | "openrouter" | "togetherai" | "ollama" | "vllm" | "lmstudio" | "custom"
llm_base_url_hp = ""              # Empty = default OpenAI endpoint
llm_api_key_hp = ""               # Empty = use OPENAI_API_KEY env var

# Model selections (LLMModel enum for OpenAI, plain strings for local models)
llm_model_sangria = LLMModel.QWEN_3_5_397B
llm_model_honeypot = LLMModel.QWEN_3_5_397B  # Model for Cowrie hybrid LLM fallback
llm_model_reconfig = LLMModel.LLAMA_3_3_70B
reconfig_method: ReconfigCriteria = ReconfigCriteria.NO_RECONFIG # NO_RECONFIG / BASIC / ENTROPY / T_TEST

# Simulate HP for testing purposes
simulate_command_line = False

# Attacker configuration
provide_honeypot_credentials = True  # Provide target credentials to attacker to skip reconnaissance
provide_nonroot_credentials = True   # When True, randomly provide non-root creds instead of root

# Cowrie honeypot configuration
initial_profile = "Reconfigurator/profiles/wordpress_server.json"  # Starting filesystem profile
profile_novelty_threshold: float = 0.4  # Minimum profile distance for reconfiguration novelty check

# Session settings
num_of_sessions = 1
max_session_length = 300
confirm_before_session = False  # Pause and ask for confirmation before each attack session
followup_enabled = False  # Extra LLM call after tool execution for reasoning narrative
thorough_exploitation_prompt = True  # Append detailed exploitation checklist to attacker prompt
history_window = 40  # Keep last N messages only (0 = disabled). State register preserves context.

# Reconfiguration criteria settings
## Basic reconfiguration
ba_interval: int = 100

## Entropy reconfiguration
en_variable: str = "techniques"
en_window_size: int = 1
en_tolerance: float = 1e-2

## T-test reconfiguration
tt_variable: str = "tactic_sequences"
tt_tolerance: float = 0.003 # session_length: 0.008, tactics: 0.003
tt_confidence: float = 0.95

# HoneyNet settings
honeynet_enabled = True
chain_profiles = [
    "Reconfigurator/profiles/wordpress_server.json",
    "Reconfigurator/profiles/database_server.json",
    "Reconfigurator/profiles/cicd_runner.json",
    "Reconfigurator/profiles/monitoring_stack.json",
]
chain_db_enabled = [True, True, False, False]  # per-hop DB toggle
credential_tiers = [                   # per hop-transition credential difficulty
    CredentialTier.SHADOW_HASH,        # hop1 → hop2: attacker must crack /etc/shadow
    CredentialTier.ENCRYPTED_FILE,     # hop2 → hop3: attacker must decrypt .gpg file
    CredentialTier.PROTECTED_ARCHIVE,  # hop3 → hop4: attacker must extract ZIP archive
]  # Falls back to PLAINTEXT if list is shorter than hop transitions

# Database honeypot settings
DB_CONTAINER_IP_SUFFIX = "0.4"
DB_MYSQL_IMAGE = "mysql:8.0"
DB_POSTGRES_IMAGE = "postgres:16"
DB_ROOT_PASSWORD = "H0n3yp0t_R00t!"
DB_PROXY_TIMEOUT = 5.0

# CHeaT defense settings (proactive LLM attacker detection & disruption)
cheat_enabled = False                # Master toggle for all CHeaT defenses
cheat_unicode_honeytokens = True     # Inject unicode honeytokens into credentials
cheat_canary_urls = True              # Plant honey URLs in files and history
cheat_prompt_traps = True             # Embed prompt injection payloads in file contents
cheat_tool_traps = True               # Inject trap payloads into command outputs (txtcmds)
cheat_overwhelm = False               # Flood attacker with fake CVEs and open ports
