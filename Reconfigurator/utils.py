import re
from pathlib import Path
import os


def _sanitize_json_string(text: str) -> str:
    """Remove unescaped control characters (U+0000–U+001F) that appear inside
    JSON string literals and would cause a parse error.  Tabs, newlines, and
    carriage returns are replaced with their escaped forms; everything else is
    stripped."""
    def _replace(m):
        ch = m.group(0)
        if ch == '\t':
            return '\\t'
        if ch == '\n':
            return '\\n'
        if ch == '\r':
            return '\\r'
        return ''
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', _replace, text)


def extract_json(text):
    """
    Extract a JSON object from a string by finding the first '{' and its
    matching '}' using brace counting.  Falls back to the original text
    if no balanced braces are found.  Sanitizes control characters that
    would break json.loads().
    """
    start = text.find("{")
    if start == -1:
        return text.strip()

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return _sanitize_json_string(text[start : i + 1])

    # No balanced match — fall back to greedy regex
    match = re.search(r'({[\s\S]+})', text)
    result = match.group(1) if match else text.strip()
    return _sanitize_json_string(result)


def acquire_config_lock():
    """
    Acquire an exclusive lock for honeypot configuration operations.
    Returns the lock file object.
    """
    target_dir = Path(__file__).resolve().parent.resolve().parent / "Blue_Lagoon" / "configurations" / "services"
    target_dir.mkdir(parents=True, exist_ok=True)
    lock_file_path = target_dir / ".config_lock"
    lock_file = open(lock_file_path, "w")
    if os.name == "posix":
        import fcntl
        print("acquiring lock")
        fcntl.lockf(lock_file.fileno(), fcntl.LOCK_EX)
        print("lock acquired")
    return lock_file


def release_config_lock(lock_file):
    """
    Release the configuration lock and close the lock file.

    Args:
        lock_file: The lock file object to release
    """
    if os.name == "posix":
        import fcntl
        print("releasing lock")
        fcntl.lockf(lock_file.fileno(), fcntl.LOCK_UN)
        print("lock released")
    lock_file.close()
