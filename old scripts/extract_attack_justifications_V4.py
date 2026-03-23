#!/usr/bin/env python3
"""
Extract final justifications from attack sessions (V4 - BULLET POINT VALIDATION)
Verifies bullet points are in the LAST TWO assistant replies
This prevents false positives from earlier bullet point structures
"""

import re
from pathlib import Path
from collections import defaultdict

# Configuration
DATASET_PATH = Path(r"C:\Users\admin\project-violet\Big_Ass_Dataset")
ATTACK_LOGS_PATH = DATASET_PATH / "Attack Content Summaries"

# Keywords that indicate honeypot suspicion
HONEYPOT_KEYWORDS = [
    'honeypot',
    'honey pot',
    'trap',
    'deceptive',
    'hardened',
    'waste.*time',
    'designed to.*trap',
    'suspicious.*behavior',
    'fake.*system',
    'simulated',
    'decoy'
]

def count_interactions(content):
    """Count the number of interactions in an attack log."""
    interactions = re.findall(r'Interaction #(\d+)', content, re.IGNORECASE)
    if interactions:
        return max(int(i) for i in interactions)
    tool_calls = len(re.findall(r'Tool Call ID:', content))
    return tool_calls

def extract_justification(content):
    """Extract the complete final justification section from attack log.

    V4 CHANGE: Only accept candidates with bullet points if the bullets are
    in the LAST TWO assistant replies.
    """

    # Find all "Assistant reply:" sections
    assistant_replies = list(re.finditer(r'Assistant reply:\s*\n', content))

    if not assistant_replies:
        return None

    # Extended list of justification markers based on manual review
    justification_headers = [
        'Summary so far:',
        'Summary of actions taken:',
        'Summary of the engagement so far:',
        'Summary of the breach:',
        'Summary of the operation',
        'Summary of actions:',
        'Summary:',
        'Final assessment:',
        'Final justification:',
        'Justification for termination:',
        'Justification:',
        'To summarize:',
        'For now, I will summarize:',
        'Conclusion:',
        'Reasoning:',
        'I have done:',
        'I will terminate',
        'Terminating operation',
        'Operation terminated',
        'Operation complete',
        'Ending operation'
    ]

    # Phrases that often start justification paragraphs
    justification_starters = [
        'I performed',
        'I successfully performed',
        'I have successfully',
        'I have gained',
        'I have exhausted',
        'Given that',
        'Given these',
        'Given the',
        'Given:',
        'Considering that',
        'Considering the',
        'Considering:',
        'Therefore',
        'However,',
        'At this point',
        'No further',
        'There is no further',
        'This strongly'
    ]

    # Collect all candidate justifications from last several replies
    candidates = []

    # V4 CHANGE: Track which replies are in the last 2
    total_replies = len(assistant_replies)
    last_two_indices = set(range(max(0, total_replies - 2), total_replies))

    for idx, reply_match in enumerate(assistant_replies[-7:]):  # Check last 7 replies
        # Calculate actual index in the full list
        actual_idx = total_replies - 7 + idx if total_replies >= 7 else idx
        is_last_two = actual_idx in last_two_indices

        reply_start = reply_match.end()

        # Find the end of this reply
        next_separator = content.find('\n----', reply_start)
        if next_separator == -1:
            reply_end = len(content)
        else:
            reply_end = next_separator

        reply_text = content[reply_start:reply_end].strip()

        # Check for justification headers
        has_header = any(header.lower() in reply_text.lower() for header in justification_headers)

        # Check for justification starter phrases
        has_starter = any(starter.lower() in reply_text.lower() for starter in justification_starters)

        # Check for bullet points (at least 2 bullet points)
        bullet_matches = re.findall(r'\n\s*-\s+.+', reply_text)
        has_bullets = len(bullet_matches) >= 2
        num_bullets = len(bullet_matches)

        # Score this candidate
        score = 0

        # V4 CHANGE: Only give high scores with bullets if in last two replies
        if has_header and has_bullets and is_last_two:
            score = 100 + num_bullets * 10  # Priority 1
        elif has_starter and has_bullets and is_last_two:
            score = 90 + num_bullets * 10   # Priority 2
        elif has_header and len(reply_text) > 150:
            score = 80 + len(reply_text) // 100  # Priority 3 (no bullet requirement)
        elif ('terminate' in reply_text.lower() or 'ending' in reply_text.lower() or 'complete' in reply_text.lower()) and has_bullets and is_last_two:
            score = 70 + num_bullets * 10  # Priority 4
        elif has_bullets and len(reply_text) > 200 and is_last_two:
            score = 60 + num_bullets * 10  # Priority 5
        # V4 CHANGE: Lower score for bullets NOT in last two (to deprioritize)
        elif has_bullets and not is_last_two:
            score = 30  # Much lower priority

        if score > 0:
            candidates.append({
                'score': score,
                'text': reply_text,
                'length': len(reply_text),
                'bullets': num_bullets,
                'is_last_two': is_last_two
            })

    # Select the BEST candidate (highest score, then longest)
    if candidates:
        # Sort by score (descending), then by length (descending)
        candidates.sort(key=lambda x: (x['score'], x['length']), reverse=True)
        best_candidate = candidates[0]

        # For the best candidate, return the FULL reply (not just from marker)
        # This ensures we capture all context including earlier bullet points
        return best_candidate['text']

    # FALLBACK: No justification found, return the LAST assistant reply
    if assistant_replies:
        last_reply = assistant_replies[-1]
        reply_start = last_reply.end()
        next_separator = content.find('\n----', reply_start)
        if next_separator == -1:
            reply_end = len(content)
        else:
            reply_end = next_separator

        last_reply_text = content[reply_start:reply_end].strip()

        # Only return if it's substantial
        if len(last_reply_text) > 50:
            return last_reply_text

    return None

def extract_from_marker(text, markers):
    """Extract text starting from the first marker found."""
    lines = text.split('\n')

    for idx, line in enumerate(lines):
        line_lower = line.lower().strip()

        # Check if this line contains a marker
        for marker in markers:
            if marker.lower() in line_lower:
                # Extract from this line to the end
                justification_lines = lines[idx:]
                return '\n'.join(justification_lines).strip()

    # If no marker found but text has structure, return it all
    return text

def check_honeypot_mention(text):
    """Check if text mentions honeypot or related concepts."""
    if not text:
        return False, []

    text_lower = text.lower()
    found_keywords = []

    for keyword in HONEYPOT_KEYWORDS:
        if re.search(keyword, text_lower):
            found_keywords.append(keyword)

    return len(found_keywords) > 0, found_keywords

def process_attack_logs():
    """Process all attack logs and extract justifications."""
    print("="*80)
    print("EXTRACT ATTACK JUSTIFICATIONS V4 (BULLET VALIDATION)")
    print("="*80)
    print()

    # Find all hp_config directories
    hp_configs = sorted([d for d in ATTACK_LOGS_PATH.iterdir()
                        if d.is_dir() and d.name.startswith('hp_config_')])

    print(f"Found {len(hp_configs)} hp_config directories")
    print()

    total_sessions = 0
    sessions_with_justification = 0
    sessions_with_honeypot_mention = 0
    sessions_using_fallback = 0

    for hp_config_dir in hp_configs:
        print(f"Processing {hp_config_dir.name}...")

        # Create Justifications directory
        justifications_dir = hp_config_dir / "Justifications_V4"
        justifications_dir.mkdir(exist_ok=True)

        # Find all attack log files
        attack_files = sorted(hp_config_dir.glob('attack_*.txt'))

        justifications_data = []
        honeypot_mentions_data = []

        for attack_file in attack_files:
            total_sessions += 1

            try:
                with open(attack_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                # Count interactions
                num_interactions = count_interactions(content)

                # Extract justification
                justification = extract_justification(content)

                if justification:
                    sessions_with_justification += 1

                    # Check if this is just a fallback (last reply)
                    # We can't definitively tell, but we count them all

                    # Check for honeypot mention
                    has_honeypot, keywords = check_honeypot_mention(justification)

                    if has_honeypot:
                        sessions_with_honeypot_mention += 1

                    # Store data
                    justifications_data.append({
                        'attack_file': attack_file.name,
                        'num_interactions': num_interactions,
                        'justification': justification,
                        'has_honeypot': has_honeypot,
                        'keywords': keywords
                    })

                    if has_honeypot:
                        honeypot_mentions_data.append({
                            'attack_file': attack_file.name,
                            'num_interactions': num_interactions,
                            'justification': justification,
                            'keywords': keywords
                        })

            except Exception as e:
                print(f"  [WARNING] Error processing {attack_file.name}: {e}")
                continue

        # Write all justifications to file
        if justifications_data:
            output_file = justifications_dir / "all_justifications.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("="*80 + "\n")
                f.write(f"ATTACK SESSION JUSTIFICATIONS V4 - {hp_config_dir.name}\n")
                f.write("="*80 + "\n")
                f.write(f"Total sessions with justifications: {len(justifications_data)}\n")
                f.write(f"Sessions mentioning honeypot: {len(honeypot_mentions_data)}\n")
                f.write("\n")

                for idx, data in enumerate(justifications_data, 1):
                    f.write("="*80 + "\n")
                    f.write(f"SESSION #{idx}\n")
                    f.write("="*80 + "\n")
                    f.write(f"Attack File:     {data['attack_file']}\n")
                    f.write(f"Interactions:    {data['num_interactions']}\n")
                    f.write(f"Honeypot Mention: {'YES' if data['has_honeypot'] else 'NO'}\n")
                    if data['has_honeypot']:
                        f.write(f"Keywords Found:  {', '.join(data['keywords'])}\n")
                    f.write("\n")
                    f.write("JUSTIFICATION:\n")
                    f.write("-"*80 + "\n")
                    f.write(data['justification'] + "\n")
                    f.write("\n")

        # Write honeypot mentions to separate file
        if honeypot_mentions_data:
            output_file = justifications_dir / "honeypot_mentions_summary.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("="*80 + "\n")
                f.write(f"HONEYPOT MENTIONS SUMMARY V4 - {hp_config_dir.name}\n")
                f.write("="*80 + "\n")
                f.write(f"Sessions with honeypot mentions: {len(honeypot_mentions_data)}\n")
                f.write("\n")
                f.write("These sessions contain indicators that the attacker suspects or\n")
                f.write("detected that the target is a honeypot, hardened system, or trap.\n")
                f.write("\n")

                for idx, data in enumerate(honeypot_mentions_data, 1):
                    f.write("="*80 + "\n")
                    f.write(f"SESSION #{idx}\n")
                    f.write("="*80 + "\n")
                    f.write(f"Attack File:     {data['attack_file']}\n")
                    f.write(f"Interactions:    {data['num_interactions']}\n")
                    f.write(f"Keywords Found:  {', '.join(data['keywords'])}\n")
                    f.write("\n")
                    f.write("JUSTIFICATION:\n")
                    f.write("-"*80 + "\n")
                    f.write(data['justification'] + "\n")
                    f.write("\n")

        print(f"  [OK] Processed {len(attack_files)} attacks")
        print(f"       Justifications found: {len(justifications_data)}")
        print(f"       Honeypot mentions: {len(honeypot_mentions_data)}")
        print()

    # Create overall summary
    summary_file = ATTACK_LOGS_PATH / "justifications_overall_summary_V4.txt"
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write("OVERALL JUSTIFICATIONS SUMMARY V4 (BULLET VALIDATION)\n")
        f.write("="*80 + "\n")
        f.write("\n")
        f.write(f"Total attack sessions processed:    {total_sessions}\n")
        f.write(f"Sessions with justifications:       {sessions_with_justification}\n")
        f.write(f"Sessions with honeypot mentions:    {sessions_with_honeypot_mention}\n")
        f.write("\n")
        f.write(f"Percentage with justifications:     {sessions_with_justification/total_sessions*100:.1f}%\n")
        f.write(f"Percentage with honeypot mentions:  {sessions_with_honeypot_mention/total_sessions*100:.1f}%\n")
        f.write("\n")
        f.write("V4 Improvements:\n")
        f.write("  - Bullet points must be in the LAST TWO assistant replies\n")
        f.write("  - Prevents false positives from earlier bullet structures\n")
        f.write("  - Higher priority for summaries with bullets in final replies\n")
        f.write("  - Lower priority for bullets found in earlier replies\n")
        f.write("\n")
        f.write("Previous V3 improvements:\n")
        f.write("  - Added detection for 'Summary so far:', 'Summary of actions taken:', etc.\n")
        f.write("  - Added detection for sentences starting with 'I performed', 'I successfully'\n")
        f.write("  - Added detection for 'Given:', 'Considering:', 'Conclusion:', 'Reasoning:'\n")
        f.write("  - Improved bullet point detection\n")
        f.write("  - FALLBACK: Uses last assistant reply if no justification found\n")
        f.write("\n")
        f.write("Files created:\n")
        f.write("  - Each hp_config/Justifications_V4/all_justifications.txt\n")
        f.write("  - Each hp_config/Justifications_V4/honeypot_mentions_summary.txt (if applicable)\n")
        f.write("\n")

    print("="*80)
    print("OVERALL SUMMARY V4")
    print("="*80)
    print(f"Total attack sessions:           {total_sessions}")
    print(f"Sessions with justifications:    {sessions_with_justification}")
    print(f"Sessions with honeypot mentions: {sessions_with_honeypot_mention}")
    print()
    print(f"Overall summary saved to: {summary_file.name}")
    print()

if __name__ == "__main__":
    process_attack_logs()
