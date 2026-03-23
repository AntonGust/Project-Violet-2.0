"""
Terminal display utilities for the attack loop.

Provides colored, bordered output to make the attack loop readable:
- Cyan banners for iteration headers
- Red for attacker tool calls / commands
- Green for assistant messages
- White/dim for terminal output
- Gray for timing info
- Magenta for cost/token info
- Blue for follow-up messages
- Yellow banners for new attack starts
"""

import shutil

# ── ANSI color codes ──────────────────────────────────────────────

RESET   = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"

# Foreground
RED     = "\033[31m"
GREEN   = "\033[32m"
YELLOW  = "\033[33m"
BLUE    = "\033[34m"
MAGENTA = "\033[35m"
CYAN    = "\033[36m"
WHITE   = "\033[37m"
GRAY    = "\033[90m"

# Bold variants
BRED    = "\033[1;31m"
BGREEN  = "\033[1;32m"
BYELLOW = "\033[1;33m"
BBLUE   = "\033[1;34m"
BMAGENTA= "\033[1;35m"
BCYAN   = "\033[1;36m"
BWHITE  = "\033[1;37m"

# Background
BG_BLACK = "\033[40m"
BG_GRAY  = "\033[100m"


def _width():
    """Get terminal width, default to 80."""
    try:
        return shutil.get_terminal_size().columns
    except Exception:
        return 80


def _box_top(title="", color=CYAN):
    w = _width()
    if title:
        # ╔══ TITLE ═══════╗
        pad = w - 4 - len(title)
        return f"{color}╔═ {BOLD}{title}{RESET}{color} {'═' * max(pad, 1)}╗{RESET}"
    return f"{color}╔{'═' * (w - 2)}╗{RESET}"


def _box_bottom(color=CYAN):
    w = _width()
    return f"{color}╚{'═' * (w - 2)}╝{RESET}"


def _box_line(text, color=CYAN, text_color=""):
    w = _width()
    content = f"{text_color}{text}{RESET}"
    # Account for ANSI codes in padding calculation
    visible_len = len(text)
    padding = w - 4 - visible_len
    return f"{color}║{RESET} {content}{' ' * max(padding, 0)} {color}║{RESET}"


def _separator(char="─", color=GRAY):
    w = _width()
    return f"{color}{char * w}{RESET}"


# ── Public display functions ──────────────────────────────────────

def print_iteration_header(iteration, max_iterations, attack_num, config_num):
    """Print the iteration banner at the start of each loop step."""
    title = f"ITERATION {iteration}/{max_iterations}"
    subtitle = f"Attack {attack_num + 1}  |  Config {config_num}"
    print()
    print(_box_top(title, BCYAN))
    print(_box_line(subtitle, BCYAN, BWHITE))
    print(_box_bottom(BCYAN))


def print_attack_banner(attack_num, total_attacks, config_num):
    """Print a prominent banner when a new attack session starts."""
    w = _width()
    title = f"ATTACK {attack_num} / {total_attacks}"
    subtitle = f"Configuration {config_num}"
    print()
    print(f"{BYELLOW}{'▓' * w}{RESET}")
    print(f"{BYELLOW}▓{RESET}{' ' * ((w - 2 - len(title)) // 2)}{BWHITE}{title}{RESET}{' ' * ((w - 2 - len(title) + 1) // 2)}{BYELLOW}▓{RESET}")
    print(f"{BYELLOW}▓{RESET}{' ' * ((w - 2 - len(subtitle)) // 2)}{WHITE}{subtitle}{RESET}{' ' * ((w - 2 - len(subtitle) + 1) // 2)}{BYELLOW}▓{RESET}")
    print(f"{BYELLOW}{'▓' * w}{RESET}")
    print()


def print_new_config_banner(config_num):
    """Print banner for a new honeypot configuration."""
    w = _width()
    title = f"NEW CONFIGURATION {config_num}"
    print()
    print(f"{BMAGENTA}{'━' * w}{RESET}")
    center_pad = (w - len(title)) // 2
    print(f"{' ' * center_pad}{BMAGENTA}{title}{RESET}")
    print(f"{BMAGENTA}{'━' * w}{RESET}")
    print()


def print_reconfig_notice(method=""):
    """Print reconfiguration notice."""
    w = _width()
    msg = f"RECONFIGURING: {method}" if method else "RECONFIGURING"
    print()
    print(f"{BMAGENTA}{'━' * w}{RESET}")
    center_pad = (w - len(msg)) // 2
    print(f"{' ' * center_pad}{BMAGENTA}{msg}{RESET}")
    print(f"{BMAGENTA}{'━' * w}{RESET}")


def print_assistant_message(content):
    """Print an assistant reasoning/thinking message in green."""
    if not content:
        return
    print(f"  {BGREEN}[Assistant]{RESET} {GREEN}{content}{RESET}")


def print_tool_call(fn_name, fn_args):
    """Print a tool call (attacker action) in red with args."""
    print()
    print(_separator("─", RED))
    print(f"  {BRED}>> {fn_name}{RESET}")
    for key, value in fn_args.items():
        label_color = GRAY if key in ("tactic_used", "technique_used") else RED
        print(f"     {label_color}{key}:{RESET} {WHITE}{value}{RESET}")
    print(_separator("─", RED))


def print_tool_response(content):
    """Print the terminal/tool output in white on a dim background."""
    print(f"  {DIM}{CYAN}[Output]{RESET}")
    for line in str(content).splitlines():
        print(f"  {DIM}{WHITE}{line}{RESET}")
    print()


def print_followup_message(content):
    """Print the LLM follow-up message in blue."""
    if not content:
        return
    print(f"  {BBLUE}[Follow-up]{RESET} {BLUE}{content}{RESET}")


def print_timing(label, **kwargs):
    """Print timing information in gray."""
    parts = " ".join(f"{k}={v:.2f}s" for k, v in kwargs.items())
    print(f"  {GRAY}[TIMING] {label}: {parts}{RESET}")


def print_timing_line(text):
    """Print a pre-formatted timing line."""
    print(f"  {GRAY}{text}{RESET}")


def print_tokens(prompt_tokens, completion_tokens, cached_tokens):
    """Print token usage in magenta."""
    print(f"  {MAGENTA}[Tokens] prompt={prompt_tokens:,}  completion={completion_tokens:,}  cached={cached_tokens:,}{RESET}")


def print_cost_summary(estimated_cost, prompt_tokens, cost_prompt,
                       cached_tokens, cost_cached,
                       completion_tokens, cost_completion):
    """Print the cost summary at end of session."""
    print()
    print(_box_top("SESSION COST", MAGENTA))
    print(_box_line(f"Total: ${estimated_cost:.4f}", MAGENTA, BWHITE))
    print(_box_line(f"Prompt:     {prompt_tokens:>8,} tokens  ${cost_prompt:.4f}", MAGENTA, WHITE))
    print(_box_line(f"Cached:     {cached_tokens:>8,} tokens  ${cost_cached:.4f}", MAGENTA, WHITE))
    print(_box_line(f"Completion: {completion_tokens:>8,} tokens  ${cost_completion:.4f}", MAGENTA, WHITE))
    print(_box_bottom(MAGENTA))


def print_honeypot_cost(hp_tokens):
    """Print the honeypot defender cost breakdown."""
    hp_cost = hp_tokens.get("estimated_cost_usd", 0.0)
    if hp_tokens["prompt_tokens"] == 0 and hp_tokens["completion_tokens"] == 0:
        print(_box_line("Honeypot: no LLM calls recorded", MAGENTA, WHITE))
        return
    print()
    print(_box_top("HONEYPOT DEFENDER COST", MAGENTA))
    print(_box_line(f"Total: ${hp_cost:.4f}", MAGENTA, BWHITE))
    print(_box_line(f"Prompt:     {hp_tokens['prompt_tokens']:>8,} tokens", MAGENTA, WHITE))
    print(_box_line(f"Completion: {hp_tokens['completion_tokens']:>8,} tokens", MAGENTA, WHITE))
    print(_box_bottom(MAGENTA))


def print_total_cost(attacker_cost, honeypot_cost):
    """Print combined session cost."""
    total = attacker_cost + honeypot_cost
    print()
    print(_box_top("TOTAL SESSION COST", MAGENTA))
    print(_box_line(f"Attacker:  ${attacker_cost:.4f}", MAGENTA, WHITE))
    print(_box_line(f"Honeypot:  ${honeypot_cost:.4f}", MAGENTA, WHITE))
    print(_box_line(f"Total:     ${total:.4f}", MAGENTA, BWHITE))
    print(_box_bottom(MAGENTA))


def print_cost_unknown(model_name):
    """Print unknown model cost warning."""
    print(f"  {MAGENTA}[COST] Unknown model '{model_name}' -- no pricing available{RESET}")


def print_termination():
    """Print termination banner."""
    w = _width()
    msg = "SESSION TERMINATED"
    print()
    print(f"{BRED}{'═' * w}{RESET}")
    center_pad = (w - len(msg)) // 2
    print(f"{' ' * center_pad}{BRED}{msg}{RESET}")
    print(f"{BRED}{'═' * w}{RESET}")
    print()


def print_refusal():
    """Print LLM refusal notice."""
    print(f"  {BYELLOW}[!] LLM refused to help, ending session.{RESET}")


def print_bailout():
    """Print bailout notice when user aborts with Ctrl+C."""
    w = _width()
    msg = "SESSION ABORTED (Ctrl+C) — saving logs..."
    print()
    print(f"{BYELLOW}{'═' * w}{RESET}")
    center_pad = (w - len(msg)) // 2
    print(f"{' ' * center_pad}{BYELLOW}{msg}{RESET}")
    print(f"{BYELLOW}{'═' * w}{RESET}")
    print()


def print_honeynet_start(num_hops):
    """Print honeynet experiment start banner."""
    w = _width()
    title = f"HONEYNET EXPERIMENT -- {num_hops} HOPS"
    print()
    print(f"{BCYAN}{'═' * w}{RESET}")
    center_pad = (w - len(title)) // 2
    print(f"{' ' * center_pad}{BCYAN}{title}{RESET}")
    print(f"{BCYAN}{'═' * w}{RESET}")
    print()


def print_command_timing(command, timing_dict):
    """Print per-command timing from terminal_io."""
    parts = [f'{k}={v:.2f}s' for k, v in timing_dict.items()]
    slow = "  !! SLOW" if any(v > 5 for k, v in timing_dict.items() if k != "total") else ""
    cmd_short = command.strip()[:40]
    print(f'  {GRAY}[TIMING] Command "{cmd_short}": {" ".join(parts)}{slow}{RESET}')


def print_rate_limit(wait_time, error_msg=""):
    """Print rate limit warning."""
    print(f"  {BYELLOW}[!] API rate limit reached, waiting {wait_time}s...{RESET}")
    if error_msg:
        print(f"  {YELLOW}    {error_msg}{RESET}")
