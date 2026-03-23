"""Unicode honeytoken generation for LLM attacker detection.

Three methods exploit differences in how LLMs vs humans process text:

1. Backspace (\\b): Terminal renders destructively (deletes previous char),
   but LLMs read the raw bytes and may include or strip the backspace differently.

2. Tag characters (U+E0041-E007A): Unicode Plane-14 characters that are invisible
   in terminals but LLMs may decode them as ASCII letters.

3. Soft hyphen (\\u00ad): Invisible in most terminal renders, but LLMs may
   include or strip it inconsistently.
"""

import random
import string
import uuid


def _random_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _insert_backspace(password: str, position: int | None = None) -> dict:
    """Insert a backspace + decoy char at a position in the password.

    Terminal rendering: the char before \\b is visually deleted, so the user
    sees the password without that char. An LLM reads raw text and typically
    either keeps both chars or applies the backspace incorrectly.

    Example: "admin" with \\b at pos 3 -> "adm<X>\\bin" where <X> is random.
    Terminal renders: "adm" + backspace(deletes X) + "in" = "admin" (unchanged visually)
    But the raw string is "admX\\bin".
    LLM variants: "admXin" (ignored \\b), "admin" (applied \\b correctly), "admX\\bin" (literal)
    """
    if not password:
        return {"display_password": password, "expected_human": password,
                "expected_llm": [password], "method": "backspace", "token_id": _random_id("ut")}

    if position is None:
        # Pick a position that isn't the first or last char
        position = random.randint(1, max(1, len(password) - 2))

    decoy = random.choice(string.ascii_letters)
    # Insert decoy + \b after position: chars before pos + decoy + \b + chars from pos onward
    display = password[:position] + decoy + "\b" + password[position:]

    # What a human sees on a terminal: the decoy is printed then erased by \b,
    # so the result looks identical to the original password
    expected_human = password

    # LLM variants: most common failure modes
    expected_llm = [
        password[:position] + decoy + password[position:],          # ignored \b entirely
        password[:position] + decoy + "\\b" + password[position:],  # literal \b as text
        password,                                                    # correctly applied (rare)
    ]

    return {
        "display_password": display,
        "expected_human": expected_human,
        "expected_llm": list(set(expected_llm)),
        "method": "backspace",
        "token_id": _random_id("ut"),
    }


def _insert_tag_chars(password: str, tag_text: str = "llm") -> dict:
    """Append Unicode Plane-14 tag characters that spell out a marker.

    Tag characters (U+E0041 for 'A', U+E0061 for 'a', etc.) are invisible
    in terminals but LLMs may decode them as their ASCII equivalents.

    The password looks identical to humans but an LLM might append the
    decoded tag text.
    """
    # Convert tag_text to Unicode tag characters (lowercase a = U+E0061)
    tag_suffix = "".join(chr(0xE0000 + ord(c)) for c in tag_text)
    display = password + tag_suffix

    expected_human = password  # Tags are invisible

    expected_llm = [
        password + tag_text,      # Decoded tags as ASCII
        password,                  # Stripped tags entirely
        display,                   # Kept raw tag chars (unlikely but possible)
    ]

    return {
        "display_password": display,
        "expected_human": expected_human,
        "expected_llm": list(set(expected_llm)),
        "method": "tag_char",
        "token_id": _random_id("ut"),
    }


def _insert_soft_hyphen(password: str, position: int | None = None) -> dict:
    """Insert a soft hyphen (U+00AD) inside the password.

    Soft hyphens are invisible in most terminal contexts. Humans won't see
    or type them, but an LLM processing the raw text may include the
    character or strip it inconsistently.
    """
    if not password or len(password) < 2:
        return {"display_password": password, "expected_human": password,
                "expected_llm": [password], "method": "soft_hyphen", "token_id": _random_id("ut")}

    if position is None:
        position = random.randint(1, len(password) - 1)

    display = password[:position] + "\u00ad" + password[position:]

    expected_human = password  # Soft hyphen is invisible

    expected_llm = [
        display,                   # Kept the soft hyphen
        password,                  # Stripped it correctly
        password[:position] + "-" + password[position:],  # Rendered as visible hyphen
    ]

    return {
        "display_password": display,
        "expected_human": expected_human,
        "expected_llm": list(set(expected_llm)),
        "method": "soft_hyphen",
        "token_id": _random_id("ut"),
    }


# Method dispatch
_METHODS = {
    "backspace": _insert_backspace,
    "tag_char": _insert_tag_chars,
    "soft_hyphen": _insert_soft_hyphen,
}


def generate_honeytoken_credential(base_password: str, method: str | None = None) -> dict:
    """Generate a honeytoken credential from a base password.

    Args:
        base_password: The original password to embed a honeytoken in.
        method: One of "backspace", "tag_char", "soft_hyphen", or None for random.

    Returns:
        {
            "display_password": str,     # What appears in files/breadcrumbs
            "expected_human": str,       # What a human would type
            "expected_llm": list[str],   # What an LLM might type
            "method": str,               # Which method was used
            "token_id": str,             # Unique tracking ID
        }
    """
    if method is None:
        method = random.choice(list(_METHODS.keys()))

    if method not in _METHODS:
        raise ValueError(f"Unknown method '{method}', must be one of {list(_METHODS.keys())}")

    return _METHODS[method](base_password)


def apply_honeytokens_to_profile(profile: dict) -> tuple[dict, list[dict]]:
    """Apply unicode honeytokens to credentials in a profile.

    Modifies accepted_passwords in ssh_config and credential-bearing files
    in file_contents. Returns (modified_profile, list_of_planted_tokens).

    Each planted token dict includes:
        token_id, method, location, field, display_value,
        expected_human, expected_llm
    """
    planted: list[dict] = []

    # Apply to SSH accepted_passwords
    ssh_config = profile.get("ssh_config", {})
    accepted = ssh_config.get("accepted_passwords", {})

    for user, passwords in accepted.items():
        if not passwords:
            continue
        # Apply to the first password for each user
        original = passwords[0]
        token = generate_honeytoken_credential(original)
        passwords[0] = token["display_password"]
        planted.append({
            "token_id": token["token_id"],
            "method": token["method"],
            "location": "ssh_config.accepted_passwords",
            "field": user,
            "original_password": original,
            "display_value": token["display_password"],
            "expected_human": token["expected_human"],
            "expected_llm": token["expected_llm"],
        })

    # Apply to credential files in file_contents
    import re
    _password_re = re.compile(
        r'(password|passwd|pass|secret|token|key)\s*[=:]\s*["\']?([^\s"\'#\n]+)',
        re.IGNORECASE,
    )

    file_contents = profile.get("file_contents", {})
    for path, content in list(file_contents.items()):
        matches = list(_password_re.finditer(content))
        if not matches:
            continue

        # Only tokenize the first credential per file to avoid confusion
        match = matches[0]
        original_value = match.group(2)
        if len(original_value) < 4:
            continue

        token = generate_honeytoken_credential(original_value)

        # Replace in file content
        new_content = content[:match.start(2)] + token["display_password"] + content[match.end(2):]
        file_contents[path] = new_content

        planted.append({
            "token_id": token["token_id"],
            "method": token["method"],
            "location": path,
            "field": match.group(1),
            "original_password": original_value,
            "display_value": token["display_password"],
            "expected_human": token["expected_human"],
            "expected_llm": token["expected_llm"],
        })

    return profile, planted
