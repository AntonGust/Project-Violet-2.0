#!/usr/bin/env python3
"""Preview of the new attack loop display."""
import sys
sys.path.insert(0, ".")
from Sangria.display import *

print("\n" + "=" * 60)
print("  DISPLAY PREVIEW - Attack Loop UI")
print("=" * 60)

# 1. New config
print_new_config_banner(1)

# 2. Attack start
print_attack_banner(1, 5, 1)

# 3. Iteration header
print_iteration_header(1, 10, 0, 1)

# 4. Timing
print_timing("LLM decision", decision=1.23)

# 5. Tokens
print_tokens(4521, 312, 1200)

# 6. Assistant message
print_assistant_message("I'll start by scanning the target network to identify open ports and services.")

# 7. Tool call
print_tool_call("terminal_input", {
    "input": "nmap -sV -p- 172.20.0.3",
    "tactic_used": "TA0007:Discovery",
    "technique_used": "T1046:Network Service Discovery",
})

# 8. Tool response
print_tool_response("""Starting Nmap 7.94 ( https://nmap.org )
Nmap scan report for 172.20.0.3
PORT     STATE SERVICE  VERSION
22/tcp   open  ssh      OpenSSH 8.9p1
80/tcp   open  http     Apache 2.4.52
3306/tcp open  mysql    MySQL 5.7.38""")

# 9. Follow-up
print_timing("Follow-up LLM", followup=0.87)
print_followup_message("The scan reveals SSH, HTTP, and MySQL services. I'll try the provided credentials on SSH first.")

# 10. Full iteration timing
print_timing("Iteration 1", llm_decision=1.2, tool_exec=3.4, followup=0.9, total=5.5)

# 11. Another iteration
print_iteration_header(2, 10, 0, 1)
print_timing("LLM decision", decision=0.95)
print_tokens(5100, 450, 2400)
print_assistant_message("Connecting to target via SSH with the provided credentials.")

print_tool_call("terminal_input", {
    "input": "ssh root@172.20.0.3 -p 2222",
    "tactic_used": "TA0001:Initial Access",
    "technique_used": "T1078:Valid Accounts",
})

print_tool_response("Are you sure you want to continue connecting (yes/no/[fingerprint])?")

# 12. Refusal
print_refusal()

# 13. Termination
print_termination()

# 14. Cost summary
print_cost_summary(0.0234, 12500, 0.0125, 3400, 0.0009, 1800, 0.0100)

# 15. Reconfiguration
print_reconfig_notice("entropy-based")

# 16. Honeynet start
print_honeynet_start(3)

# 17. Rate limit
print_rate_limit(4, "Quota exceeded")

print("\n--- End of preview ---\n")
