# Local Model Recommendations — L4 GPUs (24GB VRAM each)

## Hardware Context
- NVIDIA L4: 24GB VRAM each
- 16 CPU cores
- Attack sessions run sequentially (one at a time)

---

## GPU Scaling — How Many L4s?

The attack loop is sequential: Sangria sends a command, waits for the honeypot LLM response, thinks, sends the next command. Only one LLM is active at a time. The Reconfigurator only runs between session batches. This means multiple GPUs don't help with parallelism — they only help by fitting a larger model via tensor parallelism.

| Setup | Best model | Justification |
|-------|-----------|---------------|
| **1x L4** (24GB) | Qwen2.5-32B-Q4_K_M | Fits in ~20GB. Good tool calling. Test this first. |
| **2x L4** (48GB) | Qwen2.5-72B-GPTQ-Int4 | Best tool calling quality. Sweet spot for cost/performance. |
| **4x L4** (96GB) | Same 72B model | No advantage over 2x L4 for sequential sessions. 2 GPUs idle. Not worth the cost. |

**Recommendation: start with 1x L4, scale to 2x L4 only if 32B tool calling quality is insufficient for research results.**

---

## Model Recommendations by Component

### Sangria (attacker) — needs tool calling

This is the quality bottleneck. Tool calling accuracy drops fast with smaller models.

| Model | VRAM | Tool calling | Notes |
|-------|------|-------------|-------|
| **Qwen2.5-72B-GPTQ-Int4** | ~40GB (2x L4) | Excellent | Near GPT-4.1-mini for agentic tasks |
| **Qwen2.5-32B-Q4_K_M** | ~20GB (1x L4) | Good | Fits single L4, solid tool calling |
| **Llama3.1-70B-GPTQ-Int4** | ~40GB (2x L4) | Good | Strong but Qwen2.5 edges it on tool use |
| **Mistral-Nemo-12B** | ~8GB | Decent | Fast but noticeably weaker agentic behavior |

### Reconfigurator — needs JSON generation

Generates filesystem profile JSON. Easier task than tool calling. Runs infrequently (only between session batches). Can share the same GPU/model as Sangria since they never run concurrently.

- **Same model as Sangria** — simplest setup, no extra VRAM needed

### Honeypot LLM — needs fast terminal simulation

Runs inside Cowrie's Docker container. Shares GPU with Sangria since they alternate (Sangria waits while honeypot responds). Smaller models are fine here — the task is simulating terminal output, not complex reasoning.

- **Same model as Sangria** — simplest, one vLLM instance serves everything
- **Qwen2.5-7B** or **Llama3.1-8B** — alternative if you want a faster/cheaper dedicated model

---

## Recommended Setups

### Simplest: 1x L4, single model

```
GPU 0:  Qwen2.5-32B-Q4_K_M  →  all components (Sangria, Reconfigurator, Honeypot)
        served via single vLLM instance on port 8000
```

One model, one vLLM process, one endpoint. All three consumers point at the same `base_url`. Start here.

### Best quality: 2x L4, tensor parallel

```
GPU 0-1:  Qwen2.5-72B-GPTQ-Int4  →  all components
          served via single vLLM instance with --tensor-parallel-size 2
```

Same simplicity but with a 70B model for better tool calling. Only worth it if 32B quality is measurably worse in your experiments.

---

## Serving

Use **vLLM** over Ollama — it handles tensor parallelism natively, has better throughput, and provides an OpenAI-compatible endpoint out of the box.

```bash
# 1x L4 setup
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-32B-Instruct-GPTQ-Int4 \
  --port 8000 \
  --enable-auto-tool-choice \
  --tool-call-parser hermes

# 2x L4 setup
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-72B-Instruct-GPTQ-Int4 \
  --tensor-parallel-size 2 \
  --port 8000 \
  --enable-auto-tool-choice \
  --tool-call-parser hermes
```

Note: `--enable-auto-tool-choice` and `--tool-call-parser hermes` are required for Sangria's function calling to work.
