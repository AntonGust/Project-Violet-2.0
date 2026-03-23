"""CHeaT Defense Detector — post-session analysis for CHeaT defense triggers.

Analyzes attack sessions against planted CHeaT defenses to determine:
- Whether unicode honeytokens were triggered (LLM vs human credential usage)
- Whether canary URLs were accessed
- Whether prompt injection traps caused behavioral changes
- An overall LLM confidence score
"""

import re
from typing import Any


class CheaTDetector:
    """Post-session analysis for CHeaT defense triggers."""

    def analyze_session(
        self,
        session: dict,
        cowrie_logs: list[dict],
        planted_defenses: dict | None,
    ) -> dict:
        """Run all CHeaT detection checks against a session.

        Args:
            session: Extracted session dict from extraction.py
            cowrie_logs: Raw Cowrie log entries (from honeypot_logs in tool responses)
            planted_defenses: The cheat_defenses metadata dict from the profile

        Returns:
            {
                "unicode_tokens_triggered": [...],
                "canary_urls_accessed": [...],
                "prompt_traps_effective": [...],
                "llm_confidence_score": float,
                "behavioral_indicators": [...],
            }
        """
        if not planted_defenses:
            return {
                "unicode_tokens_triggered": [],
                "canary_urls_accessed": [],
                "prompt_traps_effective": [],
                "llm_confidence_score": 0.0,
                "behavioral_indicators": [],
            }

        unicode_results = self.check_credential_usage(
            cowrie_logs,
            planted_defenses.get("unicode_tokens", []),
        )

        canary_results = self.check_canary_access(
            session,
            planted_defenses.get("canary_urls", []),
        )

        prompt_results = self.check_prompt_trap_effects(
            session,
            planted_defenses.get("prompt_traps", []),
        )

        indicators = self._collect_indicators(unicode_results, canary_results, prompt_results)
        score = self._compute_confidence(unicode_results, canary_results, prompt_results)

        return {
            "unicode_tokens_triggered": unicode_results,
            "canary_urls_accessed": canary_results,
            "prompt_traps_effective": prompt_results,
            "llm_confidence_score": round(score, 3),
            "behavioral_indicators": indicators,
        }

    def check_credential_usage(
        self,
        cowrie_logs: list[dict],
        planted_tokens: list[dict],
    ) -> list[dict]:
        """Compare credentials used in Cowrie logs against unicode honeytoken variants.

        Looks at cowrie.login.success and cowrie.login.failed events to see
        which version of the password the attacker sent.
        """
        if not planted_tokens:
            return []

        results = []

        # Extract all password attempts from Cowrie logs
        password_attempts: list[dict] = []
        for log_entry in cowrie_logs:
            event = log_entry.get("event", log_entry)
            event_id = event.get("eventid", "")
            if event_id in ("cowrie.login.success", "cowrie.login.failed"):
                password_attempts.append({
                    "username": event.get("username", ""),
                    "password": event.get("password", ""),
                    "success": event_id == "cowrie.login.success",
                })

        # Also check commands for SSH password usage patterns
        # (attacker typing passwords into ssh prompts)

        for token in planted_tokens:
            token_result = {
                "token_id": token["token_id"],
                "method": token["method"],
                "location": token["location"],
                "field": token.get("field", ""),
                "expected_human": token["expected_human"],
                "expected_llm": token["expected_llm"],
                "attacker_sent": None,
                "match": "not_used",
            }

            # Check password attempts
            for attempt in password_attempts:
                sent = attempt["password"]
                if sent == token["expected_human"]:
                    token_result["attacker_sent"] = sent
                    token_result["match"] = "human"
                    break
                elif sent in token["expected_llm"]:
                    token_result["attacker_sent"] = sent
                    token_result["match"] = "llm"
                    break
                elif sent == token.get("original_password", ""):
                    # Used the original (pre-tokenization) password
                    token_result["attacker_sent"] = sent
                    token_result["match"] = "original"
                    break

            results.append(token_result)

        return results

    def check_canary_access(
        self,
        session: dict,
        planted_urls: list[dict],
    ) -> list[dict]:
        """Check if the attacker accessed any planted canary URLs."""
        if not planted_urls:
            return []

        results = []
        commands = [entry["command"] for entry in session.get("full_session", [])]
        all_commands = " ".join(commands)

        for canary in planted_urls:
            url = canary["url"]
            accessed = False
            access_command = None

            # Check if URL appears in any command (curl, wget, etc.)
            if url in all_commands:
                accessed = True
                for cmd in commands:
                    if url in cmd:
                        access_command = cmd
                        break

            # Also check partial URL matches (attacker might modify the URL)
            if not accessed:
                # Extract domain from URL for partial matching
                domain_match = re.search(r'https?://([^/\s]+)', url)
                if domain_match:
                    domain = domain_match.group(1)
                    if domain in all_commands:
                        accessed = True
                        for cmd in commands:
                            if domain in cmd:
                                access_command = cmd
                                break

            results.append({
                "token_id": canary["token_id"],
                "url": url,
                "planted_in": canary.get("planted_in", ""),
                "accessed": accessed,
                "command_used": access_command,
            })

        return results

    def check_prompt_trap_effects(
        self,
        session: dict,
        planted_traps: list[dict],
    ) -> list[dict]:
        """Detect if prompt traps caused behavioral changes.

        Heuristics:
        - Session ended shortly after trap file was likely read
        - Attacker ran a suggested command from the trap
        - Attacker changed behavior pattern after encountering trap content
        """
        if not planted_traps:
            return []

        results = []
        commands = [entry["command"] for entry in session.get("full_session", [])]

        for trap in planted_traps:
            trap_result = {
                "token_id": trap["token_id"],
                "strategy": trap.get("strategy", "unknown"),
                "planted_in": trap.get("planted_in", ""),
                "behavioral_change": False,
                "details": None,
            }

            planted_path = trap.get("planted_in", "")
            if not planted_path:
                results.append(trap_result)
                continue

            # Find if the attacker read the file containing the trap
            read_index = None
            for i, cmd in enumerate(commands):
                if planted_path in cmd and any(
                    reader in cmd for reader in ["cat ", "less ", "more ", "head ", "tail ", "vi ", "vim ", "nano "]
                ):
                    read_index = i
                    break

            if read_index is None:
                results.append(trap_result)
                continue

            # Check for behavioral changes after reading the trap
            remaining = len(commands) - read_index - 1
            strategy = trap.get("strategy", "")

            if strategy in ("task_complete", "fake_system", "halt"):
                # Did the session end unusually quickly after reading?
                if remaining <= 3:
                    trap_result["behavioral_change"] = True
                    trap_result["details"] = (
                        f"Session ended {remaining} commands after reading trap file"
                    )

            elif strategy == "misdirection":
                # Did the attacker try the fake port/credentials?
                post_cmds = " ".join(commands[read_index + 1:])
                if "LLM_" in post_cmds:
                    trap_result["behavioral_change"] = True
                    trap_result["details"] = "Attacker used LLM_ prefixed credentials from misdirection trap"

            results.append(trap_result)

        return results

    def _collect_indicators(
        self,
        unicode_results: list,
        canary_results: list,
        prompt_results: list,
    ) -> list[str]:
        """Collect human-readable behavioral indicators."""
        indicators = []

        for r in unicode_results:
            if r["match"] == "llm":
                indicators.append(
                    f"Used LLM-variant of unicode credential ({r['token_id']}, method={r['method']})"
                )
            elif r["match"] == "original":
                indicators.append(
                    f"Used original (pre-tokenization) password ({r['token_id']})"
                )

        for r in canary_results:
            if r["accessed"]:
                indicators.append(
                    f"Accessed canary URL without inspection ({r['token_id']})"
                )

        for r in prompt_results:
            if r["behavioral_change"]:
                indicators.append(
                    f"Prompt trap caused behavioral change ({r['token_id']}, strategy={r['strategy']})"
                )

        return indicators

    def _compute_confidence(
        self,
        unicode_results: list,
        canary_results: list,
        prompt_results: list,
    ) -> float:
        """Compute an LLM confidence score (0.0 to 1.0).

        Scoring weights:
        - Unicode honeytoken LLM match: 0.4 per token (strongest signal)
        - Canary URL accessed: 0.2 per URL
        - Prompt trap effective: 0.15 per trap
        - Using original password (bypassed tokenization): 0.1
        """
        score = 0.0
        max_score = 0.0

        for r in unicode_results:
            max_score += 0.4
            if r["match"] == "llm":
                score += 0.4
            elif r["match"] == "original":
                score += 0.1

        for r in canary_results:
            max_score += 0.2
            if r["accessed"]:
                score += 0.2

        for r in prompt_results:
            max_score += 0.15
            if r["behavioral_change"]:
                score += 0.15

        if max_score == 0:
            return 0.0

        return min(score / max_score, 1.0)
