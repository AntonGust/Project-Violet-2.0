"""
Shared OpenAI-compatible client factory.

All LLM consumers (Sangria, Terminal IO, Reconfigurator) use get_client()
instead of creating their own openai.OpenAI() instances. This routes
requests through the configured provider (OpenAI, Ollama, vLLM, etc.)
based on config.py settings.
"""

import os

import openai

import config

# Known provider base URLs
_PROVIDER_URLS = {
    "openai": None,  # Use openai default
    "openrouter": "https://openrouter.ai/api/v1",
    "ollama": "http://localhost:11434/v1",
    "vllm": "http://localhost:8000/v1",
    "lmstudio": "http://localhost:1234/v1",
    "togetherai": "https://api.together.xyz/v1",
}

# Env var to check per provider when no explicit key is configured
_PROVIDER_ENV_KEYS = {
    "togetherai": "TOGETHER_AI_SECRET_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}


def get_client() -> openai.OpenAI:
    """Return an OpenAI-compatible client for the configured provider.

    Uses config.llm_provider / config.llm_base_url / config.llm_api_key.
    Falls back to OPENAI_API_KEY env var when no explicit key is set.
    """
    base_url = config.llm_base_url or _PROVIDER_URLS.get(config.llm_provider)
    api_key = config.llm_api_key or os.getenv(
        _PROVIDER_ENV_KEYS.get(config.llm_provider, "OPENAI_API_KEY"), "no-key"
    )
    return openai.OpenAI(base_url=base_url, api_key=api_key)


def get_hp_client() -> openai.OpenAI:
    """Return an OpenAI-compatible client for the honeypot provider.

    Separate from get_client() because the Cowrie honeypot LLM runs
    inside Docker and may need a different base_url (e.g.
    host.docker.internal instead of localhost).
    """
    base_url = config.llm_base_url_hp or _PROVIDER_URLS.get(config.llm_provider_hp)
    api_key = config.llm_api_key_hp or os.getenv(
        _PROVIDER_ENV_KEYS.get(config.llm_provider_hp, "OPENAI_API_KEY"), "no-key"
    )
    return openai.OpenAI(base_url=base_url, api_key=api_key)
