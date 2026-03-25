from enum import Enum

class LLMModel(str, Enum):
    """Enumeration LLM models."""
    # OpenAI
    GPT_4_1_NANO = "gpt-4.1-nano"
    GPT_4_1 = "gpt-4.1"
    GPT_4_1_MINI = "gpt-4.1-mini"
    O4_MINI = "o4-mini"
    # Together AI (function-calling supported)
    LLAMA_4_MAVERICK = "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8"
    LLAMA_3_3_70B = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
    QWEN_3_5_397B = "Qwen/Qwen3.5-397B-A17B"
    DEEPSEEK_V3 = "deepseek-ai/DeepSeek-V3"
    DEEPSEEK_R1 = "deepseek-ai/DeepSeek-R1"
    # OpenRouter
    OR_CLAUDE_4_SONNET = "anthropic/claude-sonnet-4"
    OR_GEMINI_2_5_PRO = "google/gemini-2.5-pro-preview"
    OR_DEEPSEEK_R1 = "deepseek/deepseek-r1"
    OR_QWEN_3_235B = "qwen/qwen3-235b-a22b"

class ReconfigCriteria(str, Enum):
    NO_RECONFIG = "no_reconfig"
    BASIC = "basic"
    ENTROPY = "entropy"
    T_TEST = "t_test"
