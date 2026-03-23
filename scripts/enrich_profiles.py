#!/usr/bin/env python3
"""Enrich honeypot profile JSON files with extended lure categories.

Usage:
    python scripts/enrich_profiles.py                          # all profiles
    python scripts/enrich_profiles.py Reconfigurator/profiles/cicd_runner.json  # specific file
"""

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Ensure project root is on sys.path and load .env
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from Reconfigurator.lure_agent import analyze_lure_gaps, enrich_lures, score_lure_realism


PROFILES_DIR = PROJECT_ROOT / "Reconfigurator" / "profiles"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"


def enrich_file(path: Path) -> bool:
    """Enrich a single profile file. Returns True if the file was modified."""
    print(f"\n{BOLD}=== {path.name} ==={RESET}")

    with open(path) as f:
        profile = json.load(f)

    # Show current gaps
    report = analyze_lure_gaps(profile)
    unsatisfied = {k: v for k, v in report.items() if not v["satisfied"]}
    satisfied_count = sum(1 for v in report.values() if v["satisfied"])

    if not unsatisfied:
        print(f"  {GREEN}All 10/10 lure categories satisfied — skipping.{RESET}")
        return False

    print(f"  Score: {satisfied_count}/10")
    for cat, info in unsatisfied.items():
        print(f"  {YELLOW}GAP:{RESET} {cat} (have {info['count']}, need {info['min']})")

    # Run enrichment
    print(f"\n  Calling LLM for enrichment...")
    enriched, chains = enrich_lures(profile)

    # Check improvement
    new_report = analyze_lure_gaps(enriched)
    new_satisfied = sum(1 for v in new_report.values() if v["satisfied"])
    new_unsatisfied = {k: v for k, v in new_report.items() if not v["satisfied"]}

    if new_satisfied <= satisfied_count and enriched is profile:
        print(f"  {RED}No improvement after enrichment.{RESET}")
        return False

    print(f"  {GREEN}Score: {satisfied_count}/10 → {new_satisfied}/10{RESET}")
    if new_unsatisfied:
        for cat in new_unsatisfied:
            print(f"  {YELLOW}Still missing:{RESET} {cat}")

    # Realism check
    issues = score_lure_realism(enriched)
    if issues:
        print(f"  Realism issues ({len(issues)}):")
        for i in issues:
            print(f"    [{i['severity']}] {i['issue']}")

    # Backup and write
    backup = path.with_suffix(f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    shutil.copy2(path, backup)
    print(f"  Backup: {backup.name}")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(enriched, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"  {GREEN}Written: {path.name}{RESET}")

    # Save chains alongside if present
    if chains:
        chains_path = path.with_name(path.stem + "_lure_chains.json")
        with open(chains_path, "w", encoding="utf-8") as f:
            json.dump(chains, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"  {GREEN}Chains: {chains_path.name}{RESET}")

    return True


def main():
    if len(sys.argv) > 1:
        # Specific files passed as arguments
        paths = [Path(a) for a in sys.argv[1:]]
    else:
        # All profiles in the default directory
        paths = sorted(PROFILES_DIR.glob("*.json"))
        if not paths:
            print(f"No profiles found in {PROFILES_DIR}")
            sys.exit(1)

    print(f"{BOLD}Lure Enrichment Agent{RESET}")
    print(f"Profiles: {len(paths)}")

    modified = 0
    for path in paths:
        if not path.exists():
            print(f"\n{RED}File not found: {path}{RESET}")
            continue
        if enrich_file(path):
            modified += 1

    print(f"\n{BOLD}Done.{RESET} {modified}/{len(paths)} profiles enriched.")


if __name__ == "__main__":
    main()
