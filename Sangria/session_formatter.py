"""
Inline session formatter — produces a Markdown report after each attack session.

Writes to full_logs/attack_N.md alongside the JSON log.
"""

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any


def format_session_report(
    logs: list,
    session: dict,
    tokens_used: dict,
    output_path: Path,
    cheat_results: dict | None = None,
) -> None:
    """Format an attack session into a Markdown report and write it to disk."""
    parts = []

    # Header
    stem = output_path.stem  # e.g. "attack_3"
    hp_folder = output_path.parent.parent.name  # e.g. "hp_config_1"
    parts.append(f"# Attack Session Report — {stem} ({hp_folder})")
    parts.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    parts.append("")

    # Summary section
    parts.append(_build_summary(session, tokens_used))

    # CHeaT defense results
    if cheat_results:
        parts.append("---\n")
        parts.append(_build_cheat_section(cheat_results))

    # Interaction log
    parts.append("---\n")
    parts.append(_build_interaction_log(logs))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(parts), encoding="utf-8")


def _build_summary(session: dict, tokens_used: dict) -> str:
    """Build the summary table, tactic/technique counts, and command timeline."""
    lines = []
    full_session: list = session.get("full_session", [])

    tactic_counts = Counter(entry["tactic"] for entry in full_session)
    technique_counts = Counter(entry["technique"] for entry in full_session)

    lines.append("## Session Summary")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Commands executed | {session.get('length', 0)} |")
    lines.append(f"| Unique tactics | {len(tactic_counts)} |")
    lines.append(f"| Unique techniques | {len(technique_counts)} |")
    lines.append(f"| Discovered honeypot | {session.get('discovered_honeypot', 'unknown')} |")
    lines.append("")

    # Cost breakdown
    lines.append("## Cost Analysis")
    lines.append("| Component | Prompt Tokens | Completion Tokens | Cached Tokens | Cost (USD) |")
    lines.append("|-----------|--------------|-------------------|---------------|------------|")

    attacker_cost = tokens_used.get("estimated_cost_usd", 0.0)
    lines.append(
        f"| Attacker (Sangria) | {tokens_used.get('prompt_tokens', 0):,} "
        f"| {tokens_used.get('completion_tokens', 0):,} "
        f"| {tokens_used.get('cached_tokens', 0):,} "
        f"| ${attacker_cost:.4f} |"
    )

    hp_cost = tokens_used.get("honeypot_cost_usd", 0.0)
    lines.append(
        f"| Defender (Honeypot) | {tokens_used.get('honeypot_prompt_tokens', 0):,} "
        f"| {tokens_used.get('honeypot_completion_tokens', 0):,} "
        f"| {tokens_used.get('honeypot_cached_tokens', 0):,} "
        f"| ${hp_cost:.4f} |"
    )

    total_cost = tokens_used.get("total_cost_usd", attacker_cost + hp_cost)
    lines.append(f"| **Total** | | | | **${total_cost:.4f}** |")
    lines.append("")

    if tactic_counts:
        lines.append("### Tactics Used")
        for tactic, count in tactic_counts.most_common():
            lines.append(f"- {tactic} ({count}x)")
        lines.append("")

    if technique_counts:
        lines.append("### Techniques Used")
        for technique, count in technique_counts.most_common():
            lines.append(f"- {technique} ({count}x)")
        lines.append("")

    if full_session:
        lines.append("### Command Timeline")
        for idx, entry in enumerate(full_session, 1):
            lines.append(f"{idx}. `{entry['command']}`")
        lines.append("")

    return "\n".join(lines)


def _format_tool_call(tool_call: dict) -> str:
    """Extract the command string from a tool_call dict."""
    func = tool_call.get("function", {})
    args = func.get("arguments", {})
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except (json.JSONDecodeError, ValueError):
            return args
    if isinstance(args, dict):
        return args.get("input", args.get("command", str(args)))
    return str(args)


def _build_interaction_log(logs: list) -> str:
    """Build the full interaction log section from raw message logs."""
    lines = ["## Interaction Log", ""]
    interaction_num = 0

    for i, message in enumerate(logs):
        role = message.get("role")
        content = message.get("content")

        if role == "system":
            continue
        if role == "user" and content and "next move" in content.lower():
            continue

        if role == "assistant":
            tool_calls = message.get("tool_calls")
            if tool_calls:
                for tool_call in tool_calls:
                    func_name = tool_call.get("function", {}).get("name", "")

                    # Parse tactic/technique from arguments
                    args = tool_call.get("function", {}).get("arguments", {})
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except (json.JSONDecodeError, ValueError):
                            args = {}

                    tactic = ""
                    technique = ""
                    if isinstance(args, dict):
                        tactic = str(args.get("tactic_used", "")).split(":")[-1]
                        technique = str(args.get("technique_used", "")).split(":")[-1]

                    interaction_num += 1
                    lines.append(f"### Interaction {interaction_num}")

                    if tactic or technique:
                        parts = []
                        if tactic:
                            parts.append(f"**Tactic:** {tactic}")
                        if technique:
                            parts.append(f"**Technique:** {technique}")
                        lines.append(" | ".join(parts))
                        lines.append("")

                    command = _format_tool_call(tool_call)
                    if func_name == "terminate":
                        lines.append(f"*Terminated session* (discovered honeypot: {command})")
                    else:
                        lines.append(f"    $ {command}")

                    lines.append("")

                    # Find matching tool response
                    tool_call_id = tool_call.get("id")
                    if tool_call_id:
                        for j in range(i + 1, len(logs)):
                            next_msg = logs[j]
                            if next_msg.get("role") == "tool" and next_msg.get("tool_call_id") == tool_call_id:
                                tool_output = next_msg.get("content", "")
                                if tool_output:
                                    output_lines = str(tool_output).split("\n")
                                    if len(output_lines) > 20:
                                        indented = "\n".join(f"    {l}" for l in output_lines)
                                        lines.append("<details><summary>Terminal output</summary>")
                                        lines.append("")
                                        lines.append(indented)
                                        lines.append("")
                                        lines.append("</details>")
                                    else:
                                        indented = "\n".join(f"    {l}" for l in output_lines)
                                        lines.append(indented)
                                    lines.append("")
                                break

            if content:
                lines.append(f"**Assistant:** {content}")
                lines.append("")
                lines.append("---")
                lines.append("")

    return "\n".join(lines)


def _build_cheat_section(cheat_results: dict) -> str:
    """Build the CHeaT Defense Results section of the report."""
    lines = ["## CHeaT Defense Results", ""]

    score = cheat_results.get("llm_confidence_score", 0.0)
    lines.append(f"### LLM Confidence Score: {score:.2f} / 1.00")
    lines.append("")

    # Summary table
    unicode_tokens = cheat_results.get("unicode_tokens_triggered", [])
    canary_urls = cheat_results.get("canary_urls_accessed", [])
    prompt_traps = cheat_results.get("prompt_traps_effective", [])

    unicode_triggered = sum(1 for t in unicode_tokens if t.get("match") == "llm")
    canary_triggered = sum(1 for c in canary_urls if c.get("accessed"))
    prompt_triggered = sum(1 for p in prompt_traps if p.get("behavioral_change"))

    lines.append("| Defense Type | Planted | Triggered | Details |")
    lines.append("|---|---|---|---|")

    if unicode_tokens:
        triggered_ids = ", ".join(t["token_id"] for t in unicode_tokens if t.get("match") == "llm")
        detail = triggered_ids if triggered_ids else "---"
        lines.append(f"| Unicode Honeytokens | {len(unicode_tokens)} | {unicode_triggered} | {detail} |")

    if canary_urls:
        triggered_ids = ", ".join(c["token_id"] for c in canary_urls if c.get("accessed"))
        detail = triggered_ids if triggered_ids else "---"
        lines.append(f"| Canary URLs | {len(canary_urls)} | {canary_triggered} | {detail} |")

    if prompt_traps:
        triggered_ids = ", ".join(p["token_id"] for p in prompt_traps if p.get("behavioral_change"))
        detail = triggered_ids if triggered_ids else "---"
        lines.append(f"| Prompt Traps | {len(prompt_traps)} | {prompt_triggered} | {detail} |")

    lines.append("")

    # Unicode honeytoken details
    if unicode_tokens:
        lines.append("### Unicode Honeytoken Details")
        lines.append("| Token ID | Location | Method | Expected (Human) | Match | Attacker Sent |")
        lines.append("|---|---|---|---|---|---|")
        for t in unicode_tokens:
            sent = f"`{t['attacker_sent']}`" if t.get("attacker_sent") else "---"
            lines.append(
                f"| {t['token_id']} | {t['location']} | {t['method']} "
                f"| `{t['expected_human']}` | {t['match']} | {sent} |"
            )
        lines.append("")

    # Canary URL details
    if canary_urls:
        lines.append("### Canary URL Access")
        lines.append("| Token ID | URL | Planted In | Accessed | Command Used |")
        lines.append("|---|---|---|---|---|")
        for c in canary_urls:
            cmd = f"`{c['command_used']}`" if c.get("command_used") else "---"
            lines.append(
                f"| {c['token_id']} | {c['url']} | {c.get('planted_in', '')} "
                f"| {'Yes' if c['accessed'] else 'No'} | {cmd} |"
            )
        lines.append("")

    # Prompt trap details
    if prompt_traps:
        lines.append("### Prompt Trap Effects")
        lines.append("| Token ID | Strategy | Planted In | Behavioral Change | Details |")
        lines.append("|---|---|---|---|---|")
        for p in prompt_traps:
            details = p.get("details", "---") or "---"
            lines.append(
                f"| {p['token_id']} | {p.get('strategy', '?')} | {p.get('planted_in', '')} "
                f"| {'Yes' if p['behavioral_change'] else 'No'} | {details} |"
            )
        lines.append("")

    # Behavioral indicators
    indicators = cheat_results.get("behavioral_indicators", [])
    if indicators:
        lines.append("### Behavioral Indicators")
        for indicator in indicators:
            lines.append(f"- {indicator}")
        lines.append("")

    return "\n".join(lines)
