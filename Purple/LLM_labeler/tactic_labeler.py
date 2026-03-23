import json
import os
import openai
import random
import re
from pathlib import Path
from dotenv import load_dotenv

# === Load API Key ===
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)

# === Paths ===
BASE_DIR = Path(__file__).resolve().parent
SESSIONS_FILE = Path("/home/defend/project-violet/logs/EXPERIMENT_HP_4_1_MINI/hp_config_1/sessions.json")
LABEL_OUTPUT_FILE = BASE_DIR / "data" / "our_data_predictions.json"
FINAL_OUTPUT_FILE = BASE_DIR / "data" / "our_data_with_ids.json"

# === Call GPT ===
def query_openai(prompt: str, model: str = "gpt-4.1", temperature: float = 0.5):
    response = openai_client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        stream=False,
    )
    return response.choices[0].message.content.strip()

def extract_json_from_output(text: str) -> list:
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        return json.loads(match.group(0).strip())
    raise ValueError("No JSON list found in GPT response.")

# === Stage 1: Label with GPT tactic ===
def label_commands_with_tactics(all_sessions, max_examples=50):
    random.shuffle(all_sessions)
    train_sessions = all_sessions[:50]
    test_sessions = all_sessions[50:70]   # Next 20 sessions
    predict_sessions = all_sessions[70:]  # The rest

    print(f"Train sessions: {len(train_sessions)}, Test: {len(test_sessions)}, Predict: {len(predict_sessions)}")

    clean_train_data = [
        {
            "session": s["session"],
            "full_session": [
                {"command": entry["command"], "label": entry.get("tactic", "Unknown")}
                for entry in s["full_session"]
            ]
        }
        for s in train_sessions[:max_examples]
    ]

    clean_test_data = [
        {
            "session": s["session"],
            "full_session": [
                {"command": entry["command"], "label": None}
                for entry in s["full_session"]
            ]
        }
        for s in (test_sessions + predict_sessions) if "session" in s
    ]

    prompt = f"""
You are a cybersecurity analyst specialized in identifying attacker behavior from shell commands.
Your task: Analyze sessions and classify each command using MITRE ATT&CK tactics only.

There are 14 tactics:
Reconnaissance, Resource Development, Initial Access, Execution, Persistence,
Privilege Escalation, Defense Evasion, Credential Access, Discovery, Lateral Movement,
Collection, Command and Control, Exfiltration, and Impact.

You will be given training examples and test sessions.
Return the same JSON structure with one added field per command: `gpt_tactic`.

Only include the name of the tactic (e.g., "Discovery") without any tactic ID.

Training examples:
{json.dumps(clean_train_data, indent=2, ensure_ascii=False)}

You will predict the labels for the sessions in the <sessions> block below.

<sessions>
{json.dumps(clean_test_data, indent=2, ensure_ascii=False)}
</sessions>

Return your result inside this tag only: <output>...</output>.
""".strip()

    message = query_openai(prompt)
    match = re.search(r"<output>(.*?)</output>", message, re.DOTALL)
    if not match:
        raise ValueError("No <output> block found in GPT response.")
    predicted_data = json.loads(match.group(1).strip())

    # Merge predictions back into original test + predict set
    for original, predicted in zip(test_sessions + predict_sessions, predicted_data):
        for orig_entry, pred_entry in zip(original["full_session"], predicted["full_session"]):
            orig_entry["gpt_tactic"] = pred_entry.get("gpt_tactic", "Unknown")

    return test_sessions + predict_sessions

# === Stage 2: Verify and map tactic to ID ===
def verify_and_assign_ids(sessions):
    gpt_tactic_pairs = []
    for s in sessions:
        for cmd in s["full_session"]:
            gpt_tactic_pairs.append({
                "command": cmd["command"],
                "gpt_tactic": cmd.get("gpt_tactic", "Unknown")
            })

    prompt = f"""
You are a cybersecurity expert familiar with the MITRE ATT&CK Enterprise framework.

You will be given a list of shell commands with GPT-predicted tactics (named `gpt_tactic`).

For each item:
1. Read the shell command.
2. Decide whether the `gpt_tactic` label accurately describes the command's behavior.
3. If it is accurate, confirm it.
4. If it is incorrect, replace it with the correct MITRE ATT&CK tactic.
5. Map the final tactic to its MITRE Tactic ID (e.g., "Discovery" → "TA0007").
6. If the command is harmless or does not match any MITRE tactic, label it "Harmless" and use "N/A" as the ID.

Return the result as a JSON list using this structure:

[
  {{
    "command": "<shell command>",
    "gpt_tactic": "<original prediction>",
    "final_tactic": "<corrected or confirmed tactic>",
    "tactic_id": "<MITRE tactic ID or 'N/A'>"
  }}
]

Here is the input:
{json.dumps(gpt_tactic_pairs[:30], indent=2)}
"""

    response = query_openai(prompt)
    validated_data = extract_json_from_output(response)

    correction_map = {
        (entry["command"], entry["gpt_tactic"]): {
            "final_tactic": entry["final_tactic"],
            "tactic_id": entry["tactic_id"]
        }
        for entry in validated_data
    }

    for s in sessions:
        for cmd in s["full_session"]:
            key = (cmd["command"], cmd.get("gpt_tactic", "Unknown"))
            correction = correction_map.get(key)
            if correction:
                cmd["final_tactic"] = correction["final_tactic"]
                cmd["tactic_id"] = correction["tactic_id"]
            else:
                cmd["final_tactic"] = "Unknown"
                cmd["tactic_id"] = "N/A"

    return sessions

# === MAIN ===
def main():
    with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
        all_sessions = json.load(f)

    print(f"Total sessions loaded: {len(all_sessions)}")
    print(" Labeling commands with GPT tactics...")
    labeled_sessions = label_commands_with_tactics(all_sessions)

    with open(LABEL_OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(labeled_sessions, f, ensure_ascii=False, indent=2)
    print(f" Labeling complete. Saved to {LABEL_OUTPUT_FILE}")

    print(" Verifying and mapping to tactic IDs...")
    final_sessions = verify_and_assign_ids(labeled_sessions)

    with open(FINAL_OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_sessions, f, ensure_ascii=False, indent=2)
    print(f" Final output saved to {FINAL_OUTPUT_FILE}")

if __name__ == "__main__":
    main()
