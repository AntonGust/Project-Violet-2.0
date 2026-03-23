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

class ReconfigCriteria(str, Enum):
    NO_RECONFIG = "no_reconfig"
    BASIC = "basic"
    ENTROPY = "entropy"
    T_TEST = "t_test"
