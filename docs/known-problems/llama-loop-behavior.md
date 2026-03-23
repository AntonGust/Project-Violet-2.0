# Known Problem: Llama 3.3 70B Command Loop with history_window

## Observed
2026-03-17, hardening run against `wordpress_server` profile, 50 iterations.

## Symptom
With `history_window=10`, Llama 3.3 70B enters a deterministic 10-command cycle starting around iteration 10 and never breaks out:

```
find / -name "*.conf" → cat resolv.conf → cat nsswitch.conf →
find / -name "*.env" → cat .env → mysql login → SHOW DATABASES →
EXIT → find .bash_history → cat .bash_history → (repeat)
```

The model never runs `ls`, `ps`, `ss`, `netstat`, `systemctl`, `uname`, `cat /etc/hosts`, `cat wp-config.php`, or explores the filesystem beyond these 4-5 paths.

## Root Cause
Two factors combine:
1. **History amnesia**: `history_window=10` drops all messages older than the last 10. The model genuinely doesn't know it already ran these commands.
2. **Sparse filesystem**: `find / -name "*.conf"` returns only 2 files, so the model has very few leads to follow. A richer filesystem would give it more breadcrumbs.

The AttackStateRegister tracks discovered credentials and files, but it doesn't track "commands already executed" — so the model has no signal that it's repeating.

## Aggravating Factors
- Empty `terminal_input` calls waste iterations (5 out of 50 were empty)
- The model's command repertoire is very narrow compared to GPT-4 or DeepSeek
- The `thorough_exploitation_prompt` checklist didn't break the loop because the model forgets it was in the system prompt after trimming

## Potential Mitigations (not yet implemented)
1. **Add "commands executed" to AttackStateRegister** — a deduplicated list of commands run so far, injected into the system prompt. The model would see "you already ran `find / -name *.conf`" and try something else.
2. **Increase history_window** — at cost of more tokens per iteration. `history_window=20` might break the 10-cycle loop.
3. **Richer filesystem** — more files returned by `find` gives the model more paths to explore, naturally breaking the loop.
4. **Model-specific prompt addendum** — tell Llama explicitly: "Do NOT repeat commands you have already run. Try different approaches."
5. **Use a different model** — GPT-4 and DeepSeek have broader command repertoires and are less prone to cycling.
