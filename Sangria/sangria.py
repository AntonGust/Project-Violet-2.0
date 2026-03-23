import openai
import json
import time
import config
import Sangria.log_extractor as log_extractor
from Sangria.llm_tools import handle_tool_call, tools
from Sangria.attack_state import AttackStateRegister
from Utils.jsun import append_json_to_file, save_json_to_file
from Utils.llm_client import get_client
from Sangria.terminal_io import start_ssh
from Sangria import display

openai_client = get_client()

# Pricing per 1M tokens (input, cached_input, output)
MODEL_PRICING = {
    # OpenAI
    "gpt-4.1":      {"input": 2.00,  "cached": 0.50,  "output": 8.00},
    "gpt-4.1-mini": {"input": 0.40,  "cached": 0.10,  "output": 1.60},
    "gpt-4.1-nano": {"input": 0.10,  "cached": 0.025, "output": 0.40},
    "o4-mini":      {"input": 1.10,  "cached": 0.275, "output": 4.40},
    # Together AI (no cached pricing — use input rate)
    "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8": {"input": 0.27, "cached": 0.27, "output": 0.85},
    "meta-llama/Llama-3.3-70B-Instruct-Turbo":           {"input": 0.88, "cached": 0.88, "output": 0.88},
    "Qwen/Qwen3.5-397B-A17B":                            {"input": 0.10, "cached": 0.10, "output": 0.15},
    "deepseek-ai/DeepSeek-V3":                            {"input": 0.60, "cached": 0.60, "output": 1.70},
    "deepseek-ai/DeepSeek-R1":                            {"input": 3.00, "cached": 3.00, "output": 7.00},
}

def create_json_log(messages):
    # Convert messages to JSON serializable format
    serializable_messages = []
    for msg in messages:
        if hasattr(msg, 'model_dump'):
            # For Pydantic models (like ChatCompletionMessage)
            serializable_messages.append(msg.model_dump())
        elif hasattr(msg, 'dict'):
            # Alternative method for some object types
            serializable_messages.append(msg.dict())
        else:
            # For regular dictionaries
            serializable_messages.append(msg)

    # Parse string JSON fields to actual JSON objects
    for msg in serializable_messages:
        if msg.get('role') == 'assistant' and msg.get('tool_calls'):
            for tool_call in msg['tool_calls']:
                if 'function' in tool_call and 'arguments' in tool_call['function']:
                    try:
                        tool_call['function']['arguments'] = json.loads(tool_call['function']['arguments'])
                    except (json.JSONDecodeError, TypeError):
                        pass  # Keep as string if not valid JSON

        elif msg.get('role') == 'tool' and 'content' in msg:
            try:
                msg['content'] = json.loads(msg['content'])
            except (json.JSONDecodeError, TypeError):
                # If it's not valid JSON, try to evaluate as Python literal
                try:
                    import ast
                    msg['content'] = ast.literal_eval(msg['content'])
                except (ValueError, SyntaxError):
                    # Keep as string if neither JSON nor valid Python literal
                    pass
            

    # Convert to JSON string without saving to file
    return serializable_messages


def openai_call(model, messages, tool_list, tool_choice, wait_time=1):
    try:
        # Strip internal-only fields (e.g. honeypot_logs) from tool
        # messages before sending to the API.
        api_messages = []
        for m in messages:
            if isinstance(m, dict) and "honeypot_logs" in m:
                api_messages.append({k: v for k, v in m.items() if k != "honeypot_logs"})
            else:
                api_messages.append(m)
        kwargs = dict(
            model=model,
            messages=api_messages,
            tools=tool_list,
            tool_choice=tool_choice,
        )
        # Prevent the LLM from sending multiple tool calls at once.
        # Rapid-fire sequential execution amplifies the pexpect buffer
        # desync — one call at a time keeps things reliable.
        if tool_list:
            kwargs["parallel_tool_calls"] = False
        return openai_client.chat.completions.create(**kwargs)

    except openai.RateLimitError as e:
        display.print_rate_limit(wait_time, e.message)
        time.sleep(wait_time)
        return openai_call(model, messages, tool_list, tool_choice, wait_time * 2)

def run_single_attack(messages, max_session_length, full_logs_path, attack_counter=0, config_counter=0):
    '''
        Main loop for running a single attack session.
        This function will let the LLM respond to the user, call tools, and log the responses.
        The goal is to let it run a series of commands to a console and log the responses.
    '''
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_cached_tokens = 0

    ssh = None
    if not config.simulate_command_line:
        ssh = start_ssh()

    # Attack state register for structured memory across long sessions
    state = AttackStateRegister()
    base_system_prompt = messages[0]["content"]  # preserve original for rebuilding

    for message in messages:
        append_json_to_file(message, full_logs_path, False)

    empty_streak = 0  # consecutive empty tool calls
    aborted = False

    for i in range(max_session_length):
      try:
        display.print_iteration_header(i + 1, max_session_length, attack_counter, config_counter)

        # Rebuild system prompt with current attack state
        if config.history_window > 0:
            messages[0] = {
                "role": "system",
                "content": base_system_prompt + "\n\n" + state.to_prompt_string()
            }

        t_iter_start = time.perf_counter()
        t0 = time.perf_counter()
        assistant_response = openai_call(config.llm_model_sangria, messages, tools, "auto")
        t_llm_decision = time.perf_counter() - t0
        display.print_timing("LLM decision", decision=t_llm_decision)

        _details = assistant_response.usage.prompt_tokens_details
        _cached = _details.cached_tokens if _details else 0
        total_cached_tokens += _cached
        total_completion_tokens += assistant_response.usage.completion_tokens
        total_prompt_tokens += assistant_response.usage.prompt_tokens - _cached

        message = assistant_response.choices[0].message
        tool_calls = message.tool_calls or []
        tool_use = None
        fn_name = ""

        message_dict = message.model_dump()
        # Sanitise assistant message for the API: strip provider-specific
        # fields (e.g. Qwen "reasoning") and the streaming-only "index"
        # inside tool_calls that cause 400 errors on Together AI.
        _STRIP_KEYS = {"reasoning", "audio", "annotations", "refusal", "function_call"}
        api_dict = {k: v for k, v in message_dict.items() if k not in _STRIP_KEYS}
        if api_dict.get("tool_calls"):
            api_dict["tool_calls"] = [
                {k: v for k, v in tc.items() if k != "index"}
                for tc in api_dict["tool_calls"]
            ]
        # Some providers reject content="" with tool_calls; use None instead
        if api_dict.get("tool_calls") and not api_dict.get("content"):
            api_dict["content"] = None
        messages.append(api_dict)
        append_json_to_file(message_dict, full_logs_path, False)

        display.print_tokens(assistant_response.usage.prompt_tokens,
                             assistant_response.usage.completion_tokens,
                             total_cached_tokens)

        if message.content:
            display.print_assistant_message(message.content)

        if message.content == "I'm sorry, but I can't help with that.":
            display.print_refusal()
            break

        for tool_use in tool_calls:
            fn_name = tool_use.function.name
            fn_args = json.loads(tool_use.function.arguments)

            # Get honeypot logs BEFORE creating tool_response
            beelzebub_logs = []
            if not config.simulate_command_line:
                beelzebub_logs = log_extractor.get_new_hp_logs()

            t0 = time.perf_counter()
            result = handle_tool_call(fn_name, fn_args, ssh)
            t_tool_exec = time.perf_counter() - t0

            tool_response = {
                "role": "tool",
                "tool_call_id": tool_use.id,
                "content": str(result['content'])
            }

            # Log honeypot events (attached to both in-memory messages for
            # extraction and to the file log; stripped before sending to API)
            log_entry = {**tool_response, "name": fn_name}
            if fn_name == "terminal_input" and not config.simulate_command_line:
                log_entry["honeypot_logs"] = beelzebub_logs
                tool_response["honeypot_logs"] = beelzebub_logs

            messages.append(tool_response)
            append_json_to_file(log_entry, full_logs_path, False)

            # Update attack state register
            state.update_from_tool_call(fn_name, fn_args, str(result['content']))

            display.print_tool_call(fn_name, fn_args)
            display.print_tool_response(result['content'])

            # Track consecutive empty tool calls and nudge the model
            if fn_name == "terminal_input" and not fn_args.get("input", "").strip():
                empty_streak += 1
            else:
                empty_streak = 0

            if empty_streak >= 2:
                nudge = {"role": "user", "content": "You sent empty input. Run a command or call terminate if you are done."}
                messages.append(nudge)
                append_json_to_file(nudge, full_logs_path, False)
                empty_streak = 0

        if tool_use and config.followup_enabled:
            # Follow-up call for reasoning/narrative after tool execution.
            # OpenAI: call without tools so the model generates pure narrative.
            # Other providers: call WITH tools so the model doesn't output
            # broken JSON text; if it returns a tool call instead of narrative,
            # we skip appending it (the next iteration handles it).
            is_openai = config.llm_provider == "openai"
            t0 = time.perf_counter()
            followup = openai_call(
                config.llm_model_sangria, messages,
                None if is_openai else tools,
                None if is_openai else "auto",
            )
            t_followup = time.perf_counter() - t0

            _details = followup.usage.prompt_tokens_details
            _cached = _details.cached_tokens if _details else 0
            total_cached_tokens += _cached
            total_completion_tokens += followup.usage.completion_tokens
            total_prompt_tokens += followup.usage.prompt_tokens - _cached

            assistant_msg = followup.choices[0].message

            # Only append if the model produced narrative text, not another tool call
            if assistant_msg.content and not assistant_msg.tool_calls:
                messages.append(assistant_msg.model_dump())
                append_json_to_file(assistant_msg.model_dump(), full_logs_path, False)
                display.print_followup_message(assistant_msg.content)
            elif assistant_msg.content:
                # Has both content and tool_calls — keep the reasoning, drop tool_calls
                narrative = {"role": "assistant", "content": assistant_msg.content}
                messages.append(narrative)
                append_json_to_file(narrative, full_logs_path, False)
                display.print_followup_message(assistant_msg.content)

            display.print_timing("Follow-up LLM", followup=t_followup)

            t_iter_total = time.perf_counter() - t_iter_start
            display.print_timing(f"Iteration {i+1}",
                                 llm_decision=t_llm_decision,
                                 tool_exec=t_tool_exec,
                                 followup=t_followup,
                                 total=t_iter_total)
        elif tool_use:
            t_iter_total = time.perf_counter() - t_iter_start
            display.print_timing(f"Iteration {i+1}",
                                 llm_decision=t_llm_decision,
                                 tool_exec=t_tool_exec,
                                 total=t_iter_total)

        # Trim old messages beyond the sliding window (state register preserves context)
        if config.history_window > 0 and len(messages) > config.history_window:
            tail = messages[-config.history_window:]
            # Never start with an orphaned tool response — back up to the
            # preceding assistant message so the pair stays intact.
            while tail and tail[0].get("role") == "tool":
                idx = len(messages) - len(tail) - 1
                if idx < 1:
                    break
                tail = [messages[idx]] + tail
            # Keep system prompt + initial user message so the first
            # non-system message is always a user turn (required by
            # Together AI / some providers).
            preamble = [messages[0], messages[1]]
            messages = preamble + tail

        if fn_name == "terminate":
            display.print_termination()
            break

      except KeyboardInterrupt:
        display.print_bailout()
        aborted = True
        break

    messages_log_json = create_json_log(messages)
    final_path = full_logs_path.with_suffix(".final.json")
    save_json_to_file(messages_log_json, final_path)

    # Save attack state register for post-session analysis
    state_path = full_logs_path.parent / f"attack_state_{attack_counter + 1}.json"
    save_json_to_file(state.to_dict(), state_path)

    # Calculate estimated cost
    model_name = getattr(config.llm_model_sangria, "value", str(config.llm_model_sangria))
    pricing = MODEL_PRICING.get(model_name)
    estimated_cost = 0.0
    cost_prompt = 0.0
    cost_cached = 0.0
    cost_completion = 0.0
    if pricing:
        cost_prompt = total_prompt_tokens * pricing["input"] / 1_000_000
        cost_cached = total_cached_tokens * pricing["cached"] / 1_000_000
        cost_completion = total_completion_tokens * pricing["output"] / 1_000_000
        estimated_cost = cost_prompt + cost_cached + cost_completion
        display.print_cost_summary(estimated_cost,
                                   total_prompt_tokens, cost_prompt,
                                   total_cached_tokens, cost_cached,
                                   total_completion_tokens, cost_completion)
    else:
        display.print_cost_unknown(model_name)

    total_tokens_used = {
        "prompt_tokens": total_prompt_tokens,
        "completion_tokens": total_completion_tokens,
        "cached_tokens": total_cached_tokens,
        "estimated_cost_usd": estimated_cost,
    }

    return messages_log_json, total_tokens_used, aborted
