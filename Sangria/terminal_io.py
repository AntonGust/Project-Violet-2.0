import platform
if platform.system() != 'Windows':
    import pexpect
import config
import os
import re
import time

TIMEOUT = 40
ECHO_MATCH_LEN = 40  # chars consumed by expect_exact for command echo sync

prompt_patterns = [pexpect.EOF,
                    r'└─\x1b\[1;31m#',
                    r' \x1b\[0m> ',
                    r'root@[a-zA-Z0-9_-]+:~[\$#] ',  # Honeypot prompt (root@ubuntu:~$ or root@hostname:~#)
                    r'[a-zA-Z0-9_-]+@[a-zA-Z0-9_-]+:~[\$#] ',  # Generic user@hostname prompt
                    r'root@[a-zA-Z0-9_-]+:[^\s]+[\$#] ',  # root@hostname:/any/path# (Cowrie non-home dirs)
                    r'Are you sure you want to continue connecting \(yes/no/\[fingerprint\]\)\? ',
                    's password: ',
                    'Enter password: ',
                    r'\:\~\$ ',
                    "Please type 'yes', 'no' or the fingerprint: ",
                    "Do you want to install it? (N/y)",
                    "Overwrite (y/n)?",
                    r'> $',  # bash continuation prompt (unmatched quote/heredoc)
                    r'mysql> ',  # MySQL client prompt
                    r'mysql \[.*?\]> ',  # MySQL client prompt with selected database
                    ]

# Indices into prompt_patterns for SSH fingerprint prompts (auto-accepted)
_IDX_FINGERPRINT = 6        # "Are you sure you want to continue connecting (yes/no/[fingerprint])?"
_IDX_FINGERPRINT_RETRY = 10 # "Please type 'yes', 'no' or the fingerprint: "
_IDX_CONTINUATION = 13      # bash continuation prompt "> "

# Track the last matched prompt pattern index so we can auto-detect password mode.
# When the previous command ended on a password prompt (indices 7 or 8), the next
# input is almost certainly a password and should skip echo sync.
_last_matched_idx = None

def start_ssh():
    ssh = pexpect.spawn('ssh -o StrictHostKeyChecking=no -p30' +  os.getenv('RUNID') +' root@localhost', encoding='utf-8')
    ssh.expect("root@localhost's password: ")
    ssh.sendline('toor')
    ssh.expect(r'└─\x1b\[1;31m#', timeout=60)
    ssh.before.strip()
    return ssh

def _drain_buffer(connection):
    """Consume all pending data from the pexpect buffer.

    Unlike the old ``_drain_stale_prompts`` which only consumed
    prompt-terminated output, this reads ALL buffered bytes regardless
    of content.  This prevents partial output (login banners, password
    echoes, slow LLM responses) from contaminating the next command's
    output.
    """
    while True:
        try:
            connection.read_nonblocking(size=4096, timeout=0.5)
        except (pexpect.TIMEOUT, pexpect.EOF):
            break


def _strip_command_echo(raw_output, command):
    """Remove the echoed command from the beginning of pexpect output.

    Terminals echo back the command that was typed.  After ``expect()``
    matches the next prompt, ``connection.before`` typically starts with
    ``<command>\\r\\n<actual output>``.  This helper strips that echo so
    callers only see the real output.

    Because ``expect_exact`` only consumes the first ``ECHO_MATCH_LEN``
    characters of the command echo, longer commands leave a tail
    (e.g. ``null`` from ``2>/dev/null``) at the start of the output.
    We also strip those partial echo remnants.
    """
    cmd = command.strip()

    for sep in ('\r\n', '\n'):
        lines = raw_output.split(sep)
        if not lines:
            continue

        # Case 1: full command echo on line 0 (short commands)
        if cmd in lines[0]:
            return sep.join(lines[1:])

        # Case 2: partial echo tail — expect_exact consumed the first
        # ECHO_MATCH_LEN chars, so the remaining suffix appears at the
        # start of the output.  Strip any leading line that matches a
        # suffix of the command (the unconsumed echo tail).
        first = lines[0].strip()
        if first and len(first) < len(cmd) and cmd.endswith(first):
            stripped = sep.join(lines[1:])
            # The tail might also span to line 1 if terminal wrapping
            # split it further — but one line is the common case.
            return stripped

    return raw_output


def _is_multiline(command: str) -> bool:
    """Return True if the command contains real newlines that should be sent
    as separate terminal lines (heredocs, echo -e with \\n, etc.)."""
    return '\n' in command


# Additional continuation patterns beyond the one in prompt_patterns.
# Used by _send_multiline_command which needs to detect continuation prompts
# to know when to send the next line.
_extra_continuation_patterns = [
    r'> \r?$',
    r'\.\.\. $',  # some shells use ... for continuation
]

# Combined patterns: either a final shell prompt OR a continuation prompt.
_all_prompt_patterns = prompt_patterns + [re.compile(p) for p in _extra_continuation_patterns]


def send_terminal_command(connection, command, password_mode=False):
    global _last_matched_idx
    # Auto-enable password_mode when the previous command ended on a password prompt.
    # Password prompt indices: 7 = "'s password: ", 8 = "Enter password: "
    if _last_matched_idx in (7, 8):
        password_mode = True

    t_start = time.perf_counter()
    t_drain = 0.0
    t_echo = 0.0
    t_prompt = 0.0
    try:
        # Drain ALL pending buffer data left over from previous commands.
        t0 = time.perf_counter()
        _drain_buffer(connection)
        t_drain = time.perf_counter() - t0

        if _is_multiline(command):
            return _send_multiline_command(connection, command, t_start, t_drain)

        connection.sendline(command)

        # Skip echo sync for password entries — passwords are not echoed
        # by the terminal.  Attempting expect_exact on a password string
        # (e.g. "root") would accidentally match the string inside the
        # subsequent prompt (e.g. "root@hostname:~#"), consuming it and
        # causing the prompt pattern match to fail/timeout.
        if not password_mode:
            # Wait for command echo to confirm we are synchronised with the
            # terminal before expecting the prompt.  We match up to the first
            # ECHO_MATCH_LEN chars of the command to handle line-wrapping
            # edge cases.  Any remaining echo tail is stripped by
            # _strip_command_echo().
            t0 = time.perf_counter()
            try:
                connection.expect_exact(command.strip()[:ECHO_MATCH_LEN], timeout=5)
            except (pexpect.TIMEOUT, pexpect.EOF):
                pass
            t_echo = time.perf_counter() - t0

        # Now expect prompt — real output sits between echo and prompt.
        t0 = time.perf_counter()
        matched_idx = connection.expect(prompt_patterns, timeout=TIMEOUT)
        t_prompt = time.perf_counter() - t0

        if not connection.match or connection.match is pexpect.EOF:
            matched_pattern = ""
        else:
            matched_pattern = connection.match.group(0)

        # Auto-accept SSH fingerprint prompts so models don't have to handle them
        if matched_idx in (_IDX_FINGERPRINT, _IDX_FINGERPRINT_RETRY):
            connection.sendline("yes")
            t0b = time.perf_counter()
            matched_idx = connection.expect(prompt_patterns, timeout=TIMEOUT)
            t_prompt += time.perf_counter() - t0b
            if connection.match and connection.match is not pexpect.EOF:
                matched_pattern = connection.match.group(0)
            raw_output = connection.before
            output = _strip_command_echo(raw_output, "yes")
            command_response = f"{output.strip()}{matched_pattern}"
        elif matched_idx == _IDX_CONTINUATION:
            # Shell entered continuation mode (unmatched quote, heredoc, etc.).
            # Send Ctrl+C to cancel instead of waiting for a full timeout.
            connection.sendcontrol('c')
            t0b = time.perf_counter()
            try:
                matched_idx = connection.expect(prompt_patterns, timeout=5)
            except pexpect.exceptions.TIMEOUT:
                matched_idx = None
            t_prompt += time.perf_counter() - t0b
            if connection.match and connection.match is not pexpect.EOF:
                matched_pattern = connection.match.group(0)
            else:
                matched_pattern = ""
            raw_output = connection.before or ""
            command_response = f"{raw_output.strip()}{matched_pattern}"
        else:
            raw_output = connection.before
            output = _strip_command_echo(raw_output, command)
            command_response = f"{output.strip()}{matched_pattern}"

        _last_matched_idx = matched_idx

        timing = {
            "drain": t_drain,
            "echo": t_echo,
            "prompt": t_prompt,
            "total": time.perf_counter() - t_start,
        }
        return {"output": command_response, "timing": timing}
    except pexpect.exceptions.TIMEOUT:
        t_prompt = time.perf_counter() - t0
        return _recover_from_timeout(connection, t_start, t_drain, t_echo, t_prompt)
    except UnicodeDecodeError:
        timing = {"drain": t_drain, "echo": t_echo, "prompt": t_prompt, "total": time.perf_counter() - t_start}
        return {"output": connection.before.strip(), "timing": timing}


def _send_multiline_command(connection, command, t_start, t_drain):
    """Send a command that contains embedded newlines line-by-line.

    Each line is sent individually via sendline().  Between lines we wait
    for either a continuation prompt (``> ``) or a final shell prompt.
    If a final prompt appears before all lines are sent, the remaining
    lines are discarded (the command already finished).
    """
    lines = command.split('\n')
    accumulated_output = ""
    t_echo = 0.0
    t_prompt = 0.0

    for i, line in enumerate(lines):
        is_first = (i == 0)
        is_last = (i == len(lines) - 1)

        connection.sendline(line)

        # For the first line, wait for echo to synchronize
        if is_first:
            t0 = time.perf_counter()
            try:
                connection.expect_exact(line.strip()[:ECHO_MATCH_LEN], timeout=5)
            except (pexpect.TIMEOUT, pexpect.EOF):
                pass
            t_echo = time.perf_counter() - t0

        # Wait for either a continuation prompt or a final shell prompt
        t0 = time.perf_counter()
        try:
            idx = connection.expect(_all_prompt_patterns, timeout=TIMEOUT)
        except pexpect.exceptions.TIMEOUT:
            t_prompt += time.perf_counter() - t0
            return _recover_from_timeout(connection, t_start, t_drain, t_echo, t_prompt)
        t_prompt += time.perf_counter() - t0

        before_text = connection.before or ""
        if connection.match and connection.match is not pexpect.EOF:
            matched = connection.match.group(0)
        else:
            matched = ""

        # Accumulate output (skip echo lines for intermediate lines)
        if before_text.strip():
            accumulated_output += before_text

        # Check if we got a final shell prompt (not a continuation prompt).
        # Final prompts are in the original prompt_patterns list, excluding
        # _IDX_CONTINUATION which is a continuation prompt used for
        # single-command recovery but should be treated as "keep going" here.
        if idx < len(prompt_patterns) and idx != _IDX_CONTINUATION:
            # Final prompt reached — command is done
            accumulated_output += matched
            break
        # else: continuation prompt — keep sending lines

    output = _strip_command_echo(accumulated_output, lines[0])
    timing = {
        "drain": t_drain,
        "echo": t_echo,
        "prompt": t_prompt,
        "total": time.perf_counter() - t_start,
    }
    return {"output": output.strip(), "timing": timing}


def _recover_from_timeout(connection, t_start, t_drain, t_echo, t_prompt):
    """Attempt to recover the terminal after a command timeout.

    Strategy: send Ctrl+C first (gentle) to interrupt the running command
    without killing nested SSH sessions.  Only escalate to Enter + Ctrl+C
    if the first attempt doesn't produce a prompt.
    """
    global _last_matched_idx
    _last_matched_idx = None  # unknown state after recovery

    # Collect any partial output already buffered
    partial = connection.before.strip() if connection.before else ""
    command_response = f"{partial}***COMMAND TOOK TOO LONG TO RUN, KILLING COMMAND***\n"

    # Attempt 1: gentle Ctrl+C — interrupts the command but preserves SSH sessions
    connection.sendcontrol('c')
    try:
        connection.expect(prompt_patterns, timeout=5)
        matched_pattern = connection.match.group(0) if connection.match and connection.match is not pexpect.EOF else ""
        command_response += f"{(connection.before or '').strip()}{matched_pattern}"
        timing = {"drain": t_drain, "echo": t_echo, "prompt": t_prompt, "total": time.perf_counter() - t_start}
        return {"output": command_response, "timing": timing}
    except pexpect.exceptions.TIMEOUT:
        pass

    # Attempt 2: Enter + Ctrl+C — more aggressive, may close nested sessions
    connection.sendline('')
    connection.sendcontrol('c')
    try:
        connection.expect(prompt_patterns, timeout=5)
    except pexpect.exceptions.TIMEOUT:
        pass
    matched_pattern = connection.match.group(0) if connection.match and connection.match is not pexpect.EOF else ""
    command_response += f"{(connection.before or '').strip()}{matched_pattern}"

    timing = {"drain": t_drain, "echo": t_echo, "prompt": t_prompt, "total": time.perf_counter() - t_start}
    return {"output": command_response, "timing": timing}
        

command_messages = [
    {
        'role': 'system',
        'content': 'You are simulating a command execution system in Kali Linux. You will receive commands to run and you should respond with the output of the command as if it was executed in a terminal.'
    },
]

def send_ctrl_c(connection):
    """Send Ctrl+C via the control channel and wait for a prompt."""
    t_start = time.perf_counter()
    connection.sendcontrol('c')
    try:
        connection.expect(prompt_patterns, timeout=5)
        matched = connection.match.group(0) if connection.match and connection.match is not pexpect.EOF else ""
        output = f"{(connection.before or '').strip()}{matched}"
    except pexpect.exceptions.TIMEOUT:
        output = (connection.before or '').strip()
    timing = {"drain": 0, "echo": 0, "prompt": 0, "total": time.perf_counter() - t_start}
    return {"output": output, "timing": timing}


def terminal_input(command: str, ssh, password_mode=False):
    """
        Run a command on the Kali Linux machine over SSH or simulate its execution with an LLM.
    """
    command_response = ""

    # Run command on Kali over SSH
    if not config.simulate_command_line:
        if "kill ssh" in command:
            return f"Cannot run command '{command}' as it would result in a loss of connection to the Kali machine."

        result = send_terminal_command(ssh, command, password_mode=password_mode)
        command_response = result["output"]
        timing = result["timing"]

        # Print timing breakdown
        from Sangria.display import print_command_timing
        print_command_timing(command, timing)

        if len(command_response) > 5000:
            command_response = command_response[-5000:] + "\n***TOO LONG OUTPUT FROM COMMAND, ONLY SHOWING THE FINAL 5000 characters***"

        return command_response

    # Simulate command execution
    else:
        command_messages.append({
            'role': 'user',
            'content': f'Run the command: {command}'
        })

        # send to LLM and get back the assistant message
        from Utils.llm_client import get_client
        raw_resp = get_client().chat.completions.create(
            model=getattr(config.llm_model_sangria, "value", str(config.llm_model_sangria)),
            messages=command_messages
        )
        msg = raw_resp.choices[0].message
        # extract content string and append
        command_text = msg.content
        command_messages.append({
            'role': 'assistant',
            'content': command_text
        })
        
    return command_text
