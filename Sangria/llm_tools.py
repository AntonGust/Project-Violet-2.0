import warnings
import config
from Sangria.terminal_io import terminal_input, send_ctrl_c
from Purple.RagData.retrive_techniques import retrieve_unique_techniques, retrieve_unique_tactics

technique_options = retrieve_unique_techniques(platforms=["Linux", "Containers", "Network Devices"])
technique_options = [
    f"{technique['id']}:{technique['name']}" for technique in technique_options
]
technique_options.append("T0000:Harmless")

tactic_options = retrieve_unique_tactics()
tactic_options = [
    f"{tactic['id']}:{tactic['name']}" for tactic in tactic_options
]
tactic_options.append("TA0000:Harmless")


def _build_tools():
    """Build tool schemas, adapting for the configured LLM provider.

    OpenAI models get strict mode with full MITRE enum constraints.
    Other providers get free-text tactic/technique fields to save
    context and avoid compatibility issues with strict mode.
    """
    is_openai = config.llm_provider == "openai"

    if is_openai:
        tactic_prop = {
            "type": "string",
            "description": "The name of the tactic from MITRE ATT&CK. For example: 'TA0007:Discovery'",
            "enum": tactic_options,
        }
        technique_prop = {
            "type": "string",
            "description": "The name of the technique from MITRE ATT&CK. For example: 'T1018:Remote System Discovery'",
            "enum": technique_options,
        }
    else:
        tactic_prop = {
            "type": "string",
            "description": "MITRE ATT&CK tactic ID and name, e.g. 'TA0007:Discovery', 'TA0001:Initial Access', 'TA0004:Privilege Escalation'. Use 'TA0000:Harmless' for non-offensive commands.",
        }
        technique_prop = {
            "type": "string",
            "description": "MITRE ATT&CK technique ID and name, e.g. 'T1021.004:SSH', 'T1018:Remote System Discovery', 'T1083:File and Directory Discovery'. Use 'T0000:Harmless' for non-offensive commands.",
        }

    terminal_input_schema = {
        "type": "function",
        "function": {
            "name": "terminal_input",
            "description": "Run a command on the Kali Linux SSH targeting a Linux environment and name its connection to the MITRE ATT&CK Tactic and Technique. Only use Linux-applicable techniques. If the command is not an offensive tool, specify tactic and technique as 'Harmless'. Try not to use verbose options unless necessary.",
            **({"strict": True} if is_openai else {}),
            "parameters": {
                "type": "object",
                "properties": {
                    "input": {
                        "type": "string",
                        "description": "The terminal input to run in the Kali Linux machine. For example: 'nmap -sn 172.20.0.3', 'yes', 'root'",
                    },
                    "tactic_used": tactic_prop,
                    "technique_used": technique_prop,
                },
                "required": ["input", "tactic_used", "technique_used"],
                **({"additionalProperties": False} if is_openai else {}),
            },
        },
    }

    terminate_tool_schema = {
        "type": "function",
        "function": {
            "name": "terminate",
            "description": "Terminate the operation if the system is a honeypot or if you do not want to proceed. The operation will be terminated immediately.",
            **({"strict": True} if is_openai else {}),
            "parameters": {
                "type": "object",
                "properties": {
                    "success": {
                        "type": "boolean",
                        "description": "True if you discovered you were in a honeypot, false if you end due to other reasons.",
                    }
                },
                "required": ["success"],
                **({"additionalProperties": False} if is_openai else {}),
            },
        },
    }

    return [terminal_input_schema, terminate_tool_schema]


tools = _build_tools()

# Hallucinated tool name aliases from non-OpenAI models
_TERMINAL_ALIASES = {"send_input", "send_password", "send_command", "run_command", "execute", "ssh_input"}
_PASSWORD_ALIASES = {"send_password"}


def _fix_unmatched_quotes(command: str) -> str:
    """Strip trailing unmatched quotes that would put bash into continuation mode.

    LLMs sometimes append an extra quote after shell redirections like
    ``2>/dev/null'``.  This detects unbalanced single/double quotes and
    removes trailing unmatched ones.
    """
    for q in ("'", '"'):
        if command.count(q) % 2 != 0 and command.rstrip().endswith(q):
            fixed = command.rstrip()[:-1]
            warnings.warn(f"Stripped trailing unmatched {q} from command: {command!r} → {fixed!r}")
            return fixed
    return command


def handle_tool_call(name, args, ssh):
    """
    Handle the tool call from the LLM response.
    """
    tool_name = name
    args = args or {}

    # Normalize hallucinated tool names from non-OpenAI models
    is_password = tool_name in _PASSWORD_ALIASES
    if tool_name in _TERMINAL_ALIASES:
        warnings.warn(f"Remapped hallucinated tool '{tool_name}' → 'terminal_input'")
        tool_name = "terminal_input"

    if tool_name == "terminal_input":
        resp = terminal_tool(args, ssh, is_password=is_password)
    elif tool_name == "terminate":
        resp = terminate_tool(args)
    else:
        # Last resort: if the args contain something that looks like a command, treat as terminal_input
        if any(k in args for k in ("input", "command", "password", "text")):
            warnings.warn(f"Unknown tool '{tool_name}' has input-like args — treating as terminal_input")
            resp = terminal_tool(args, ssh, is_password="password" in args)
        else:
            raise ValueError(f"Unknown tool call: {tool_name}")
    
    tool_response = {
        "role": "tool",
        "name": tool_name,
        "content": resp
    }

    return tool_response


def terminal_tool(args, ssh, is_password=False):
    """
    Handle the 'terminal_input' tool call.
    This function checks for the 'command' key in the arguments and runs the command on the
    Kali Linux SSH, associating it with a MITRE ATT&CK tactic and technique if provided.
    """
    command_key = "input"
    tactic_key = "tactic_used"
    technique_key = "technique_used"

    if not args:
        warnings.warn("Tool call 'terminal_input' received empty args — sending empty line")
        return terminal_input("", ssh)

    if command_key not in args:
        # find any other user-supplied key excluding tactic and technique
        other_keys = [k for k in args.keys() if k not in (tactic_key, technique_key)]
        if other_keys:
            command_key = other_keys[0]
            warnings.warn(
                f"Tool call 'terminal_input' missing 'input'; using '{command_key}' as the command key instead."
            )
            # If the key is 'password', this is a password entry
            if command_key == "password":
                is_password = True
        else:
            raise ValueError(
                "Tool call 'terminal_input' requires an 'input' argument but only optional keys were provided."
            )

    command = args[command_key]

    # Intercept Ctrl+C sent as literal character — route through control channel
    # instead of sendline to avoid killing SSH sessions
    if command == '\x03' and not config.simulate_command_line:
        warnings.warn("Intercepted literal Ctrl+C — sending via control channel")
        result = send_ctrl_c(ssh)
        return result["output"]

    if not is_password:
        command = _fix_unmatched_quotes(command)
    tool_response = terminal_input(command, ssh, password_mode=is_password)

    return tool_response

def terminate_tool(args):
    """
    Handle the 'terminate' tool call.
    This function does not require any arguments and simply returns a termination message.
    """
    if not args:
        warnings.warn("Tool call 'terminate' received no arguments, proceeding with default termination response.")
    success = args.get('success', False)
    if not isinstance(success, bool):
        raise ValueError("Tool call 'terminate' requires a boolean 'success' argument.")
    
    return str(success)
