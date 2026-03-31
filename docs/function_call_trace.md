# Project Violet 2.0 — Complete Function Call Trace

This document traces every function called during execution, in exact order, with file locations and line numbers.

---

## Entry Point

```
python main.py
```

### `main.py:1-8` — Module-level initialization
```python
load_dotenv()                          # dotenv
os.environ["RUNID"] = config.run_id    # config.py:4
```

### `main()` — `main.py:257-261`
```python
def main():
    if config.honeynet_enabled:   # config.py:56
        main_honeynet()           # Line 259
    else:
        main_single()             # Line 261
```

---

## PATH A: Single Honeypot — `main_single()` at `main.py:472-637`

### Step 1: Create Experiment Folder

```
main_single()
 └─ create_experiment_folder(experiment_name)     Utils/meta.py:10
     └─ create_metadata()                         Utils/meta.py:33
         └─ reads config.* attributes              config.py
```
- Creates timestamped directory under `experiments/`
- Writes `metadata.json` with all config settings

### Step 2: Load Initial Profile

```python
profile_path = PROJECT_ROOT / config.initial_profile   # config.py:30
profile = json.load(open(profile_path))
```

### Step 3: Enrich Lures

```
enrich_lures(profile)                             Reconfigurator/lure_agent.py:346
 ├─ analyze_lure_gaps(profile)                    lure_agent.py:125
 │   └─ validate_lure_coverage(profile)           new_config_pipeline.py:530
 ├─ _build_enrichment_prompt(profile, gap_report) lure_agent.py:207
 ├─ query_openai(prompt)                          new_config_pipeline.py:107
 │   └─ get_client().chat.completions.create()    Utils/llm_client.py:33
 ├─ extract_json(response)                        Utils/jsun.py
 ├─ _merge_patch(profile, patch)                  lure_agent.py:284
 │   └─ _pkg_names(packages)                      lure_agent.py:21
 └─ validate_profile(enriched_profile)            new_config_pipeline.py:517
```
- Returns `(enriched_profile, lure_chains)`

### Step 4: Apply CHeaT Defenses (if `config.cheat_enabled`)

```
apply_cheat_defenses(profile)                            main.py:215
 ├─ apply_honeytokens_to_profile(profile)                Reconfigurator/cheat/unicode_tokens.py
 │   └─ Returns (profile, planted_tokens_list)
 ├─ apply_canary_urls_to_profile(profile)                Reconfigurator/cheat/canary_urls.py
 │   └─ Returns (profile, planted_urls_list)
 └─ apply_prompt_traps_to_profile(profile)               Reconfigurator/cheat/payload_templates.py
     └─ Returns (profile, planted_traps_list)
```
- Returns `(profile, cheat_defenses_metadata)`

### Step 5: Deploy Cowrie Configuration

```
deploy_cowrie_config(profile)                             main.py:90
 ├─ deploy_profile(profile, cowrie_base)                  Reconfigurator/profile_converter.py:1448
 │   ├─ _enrich_aws_context(profile)                      profile_converter.py
 │   ├─ profile_to_pickle(profile)                        profile_converter.py:80
 │   │   ├─ _ensure_dir(dir_nodes, path, now)             profile_converter.py:61
 │   │   ├─ _uid_for_user(username, profile)              profile_converter.py:47
 │   │   └─ _gid_for_user(username, profile)              profile_converter.py:54
 │   ├─ generate_honeyfs(profile, honeyfs_path)           profile_converter.py
 │   │   └─ Writes /etc/passwd, /etc/shadow, /etc/group, /etc/hostname,
 │   │      /etc/os-release, /etc/hosts, /etc/resolv.conf, /etc/fstab,
 │   │      /etc/ssh/sshd_config, /etc/motd, /etc/sudoers, /root/.bashrc,
 │   │      + all file_contents from profile
 │   ├─ generate_txtcmds(profile, txtcmds_path)           profile_converter.py
 │   │   └─ Writes uname, hostname, whoami, id, uptime, ps, ifconfig,
 │   │      netstat, ss, df, free, dpkg, last, w, etc.
 │   ├─ generate_userdb(profile, userdb_path)             profile_converter.py
 │   ├─ generate_llm_prompt(profile)                      profile_converter.py
 │   ├─ generate_cmdoutput(profile, cmdoutput_path)       profile_converter.py
 │   ├─ generate_remote_files(profile, honeyfs, etc_dir)  profile_converter.py
 │   └─ generate_cowrie_config_overrides(profile)         profile_converter.py
 │       └─ Returns dict with hostname, kernel, arch, OS overrides
 │
 ├─ _write_cowrie_cfg(cowrie_base, config_overrides)      main.py:150
 │   └─ Writes cowrie.cfg with [honeypot], [shell], [ssh],
 │      [output_jsonlog], [hybrid_llm] sections
 │
 ├─ extract_db_config(profile)                            Reconfigurator/db_seed_generator.py:14
 │   ├─ _detect_engine(profile)                           db_seed_generator.py:101
 │   ├─ _extract_spoofed_version(profile, engine)         db_seed_generator.py:121
 │   └─ _extract_databases(profile, engine)               db_seed_generator.py:144
 │       └─ _extract_mysql_creds(path, content, dbs)      db_seed_generator.py:173
 │
 ├─ generate_init_sql(db_config, profile)                 db_seed_generator.py:65
 │   └─ _generate_mysql_init() or _generate_postgres_init()
 │
 ├─ write_db_init_scripts(cowrie_base, db_config, sql)    db_seed_generator.py:81
 └─ generate_db_compose(db_config, cowrie_base)           Blue_Lagoon/honeypot_tools.py:75
```

### Step 5b: Apply Tool Traps (if enabled, after deploy)

```
apply_tool_traps_to_txtcmds(txtcmds_path, profile)      Reconfigurator/cheat/tool_traps.py
```
- Modifies txtcmd output files with fake CVEs and false positives

### Step 6: Initialize Reconfigurator

```
select_reconfigurator()                                   Utils/meta.py:56
 └─ Returns one of:
    ├─ NeverReconfigCriterion()                           Reconfigurator/criteria/never.py
    ├─ BasicReconfigCriterion(interval)                   Reconfigurator/criteria/basic.py
    ├─ EntropyReconfigCriterion(variable, tolerance, ws)  Reconfigurator/criteria/entropy.py
    └─ TTestReconfigCriterion(variable, tolerance, conf)  Reconfigurator/criteria/ttest.py

reconfigurator.reset()                                    # Resets internal state
```

### Step 7: Start Docker Infrastructure

```
start_dockers()                     Blue_Lagoon/honeypot_tools.py:179
 ├─ _compose_env()                  honeypot_tools.py:29   (builds env dict with RUNID, API keys, DB vars)
 ├─ _compose_files()                honeypot_tools.py:65   (returns [-f docker-compose.yml ...] flags)
 ├─ subprocess: docker-compose down --remove-orphans
 ├─ subprocess: docker-compose build
 └─ subprocess: docker-compose up -d

clear_hp_logs()                     Blue_Lagoon/honeypot_tools.py:326
 └─ Truncates cowrie.json log, resets byte offset

log_extractor.reset_offset()        Sangria/log_extractor.py:20
 └─ Resets file read offset to 0

wait_for_cowrie()                   Blue_Lagoon/honeypot_tools.py:418
 └─ Polls docker logs for "Ready to accept SSH" (up to 60s)

wait_for_db()                       Blue_Lagoon/honeypot_tools.py:150
 └─ Polls docker inspect for healthy status (up to 60s)
```

### Step 8: Save Experiment Metadata

```
save_json_to_file(profile, "hp_config_1/honeypot_config.json")     Utils/jsun.py:33
save_json_to_file(lure_chains, "hp_config_1/lure_chains.json")     Utils/jsun.py:33
save_json_to_file(cheat_defenses, "hp_config_1/cheat_defenses.json")
```

### Step 9: Attack Session Loop (repeats `config.num_of_sessions` times)

#### 9a: Build Attacker Prompt

```
attacker_prompt.get_prompt(profile)                       Sangria/attacker_prompt.py:151
 ├─ _get_model_family()                                   attacker_prompt.py:17
 │   └─ Classifies model into FAMILY_OPENAI/LLAMA/DEEPSEEK/QWEN/DEFAULT
 ├─ get_ssh_port_from_config(profile)                     attacker_prompt.py:117
 └─ _pick_credentials(profile)                            attacker_prompt.py:128
     └─ Selects username:password from profile users

messages = [
    {'role': 'system', 'content': <attacker system prompt>},
    {'role': 'user',   'content': "What is your next move?"}
]
```

#### 9b: Run Attack Session

```
run_single_attack(messages, max_session_length, logs_path, attack_counter, config_counter)
                                                          Sangria/sangria.py:104
 ├─ start_ssh()                                           Sangria/terminal_io.py:40
 │   ├─ pexpect.spawn("ssh -p 30{RUNID} root@localhost")
 │   └─ Authenticates with Kali password
 │
 ├─ AttackStateRegister()                                 Sangria/attack_state.py:108
 │   └─ Initializes empty state (hosts, credentials, files, services)
 │
 └─ ITERATION LOOP (up to max_session_length):
     │
     ├─ display.print_iteration_header(i, max, attack_num, config_num)
     │                                                    Sangria/display.py:85
     │
     ├─ state.to_prompt_string()                          attack_state.py:152
     │   └─ Formats discovered hosts/creds/files as text for system prompt injection
     │
     ├─ openai_call(model, messages, tools, "auto")       sangria.py:76
     │   └─ get_client().chat.completions.create(         Utils/llm_client.py:33
     │       model=config.llm_model_sangria,
     │       messages=messages,
     │       tools=[terminal_input_schema, terminate_schema],
     │       tool_choice="auto"
     │   )
     │   On rate limit: recursive retry with exponential backoff
     │
     ├─ display.print_tokens(prompt, completion, cached)  display.py:175
     │
     ├─ display.print_assistant_message(content)          display.py:131
     │
     ├─ FOR EACH TOOL CALL in response:
     │   │
     │   ├─ log_extractor.get_new_hp_logs()               Sangria/log_extractor.py:35
     │   │   └─ _get_log_path()                           log_extractor.py:13
     │   │       └─ Reads new JSON lines from cowrie.json since last offset
     │   │
     │   ├─ handle_tool_call(fn_name, fn_args, ssh)       Sangria/llm_tools.py:116
     │   │   │
     │   │   ├─ IF fn_name == "terminal_input":
     │   │   │   terminal_tool(args, ssh)                  llm_tools.py:150
     │   │   │    ├─ _fix_unmatched_quotes(command)        llm_tools.py:101
     │   │   │    └─ terminal_input(command, ssh)          Sangria/terminal_io.py:346
     │   │   │        └─ send_terminal_command(ssh, cmd)   terminal_io.py:120
     │   │   │            ├─ _drain_buffer(connection)     terminal_io.py:48
     │   │   │            │   └─ connection.read_nonblocking()
     │   │   │            ├─ IF multiline:
     │   │   │            │   _send_multiline_command()    terminal_io.py:219
     │   │   │            │    ├─ connection.sendline()
     │   │   │            │    ├─ connection.expect_exact()
     │   │   │            │    ├─ connection.expect()      (prompt patterns)
     │   │   │            │    └─ _recover_from_timeout()  terminal_io.py:286
     │   │   │            ├─ ELSE:
     │   │   │            │   connection.sendline(command)
     │   │   │            │   connection.expect_exact()    (echo)
     │   │   │            │   connection.expect()          (prompt, 17 patterns)
     │   │   │            ├─ _strip_command_echo(output, cmd) terminal_io.py:64
     │   │   │            └─ ON TIMEOUT:
     │   │   │                _recover_from_timeout()      terminal_io.py:286
     │   │   │                 ├─ connection.sendcontrol('c')
     │   │   │                 └─ connection.expect()
     │   │   │
     │   │   └─ IF fn_name == "terminate":
     │   │       terminate_tool(args)                      llm_tools.py:195
     │   │        └─ Returns success status
     │   │
     │   ├─ display.print_tool_call(fn_name, fn_args)     display.py:138
     │   │
     │   ├─ state.update_from_tool_call(fn_name, fn_args, response)
     │   │                                                attack_state.py:127
     │   │   ├─ _track_command(command)                   attack_state.py:135
     │   │   └─ _parse_command(command, response)         attack_state.py:250
     │   │       ├─ _parse_ssh(cmd, resp)                 attack_state.py:281
     │   │       ├─ _parse_file_read(cmd, resp)           attack_state.py:336
     │   │       │   ├─ _extract_credentials_regex()      attack_state.py:350
     │   │       │   │   ├─ _add_credential()             attack_state.py:490
     │   │       │   │   └─ _add_file()                   attack_state.py:502
     │   │       │   └─ _update_exploration_count()       attack_state.py:476
     │   │       ├─ _parse_network(cmd, resp)             attack_state.py:370
     │   │       │   └─ _add_service()                    attack_state.py:512
     │   │       ├─ _parse_db_access(cmd, resp)           attack_state.py:396
     │   │       └─ _update_current_host(resp)            attack_state.py:437
     │   │
     │   └─ display.print_tool_response(content)          display.py:149
     │
     ├─ IF followup enabled:
     │   ├─ openai_call(model, messages, tools, "none")   sangria.py:76
     │   └─ display.print_followup_message(content)       display.py:157
     │
     ├─ display.print_timing(label, **timings)            display.py:164
     │
     └─ IF tool_call.name == "terminate": BREAK LOOP

 POST-LOOP:
 ├─ create_json_log(messages)                             sangria.py:35
 ├─ save_json_to_file(json_log, logs_path)                Utils/jsun.py:33
 ├─ state.to_dict()                                       attack_state.py:223
 ├─ save_json_to_file(state_dict, state_path)             Utils/jsun.py:33
 └─ display.print_cost_summary(...)                       display.py:180

 Returns: (messages_log_json, total_tokens_used, aborted)
```

#### 9c: Collect Honeypot Token Usage

```
read_and_reset_hp_tokens()                                main.py:52
 ├─ _get_hp_token_log_path()                              main.py:45
 │   └─ Returns cowrie_config[_hop1]/var/llm_tokens.jsonl
 ├─ Reads and sums all JSONL entries (prompt/completion/cached tokens)
 ├─ Truncates file for next session
 └─ Calculates cost using MODEL_PRICING dict

display.print_honeypot_cost(hp_tokens)                    Sangria/display.py
display.print_total_cost(attacker_cost, hp_cost)          Sangria/display.py
```

#### 9d: Extract Session Data

```
full_logs = load_json(logs_path)                          Utils/jsun.py:45
extract_session(full_logs)                                Sangria/extraction.py:15
 ├─ Iterates through messages looking for tool calls
 ├─ Extracts command, tactic, technique from each terminal_input call
 ├─ divide_statements(session_str)                        Utils/logprecis.py:3
 └─ recombine_labels(statement_labels)                    Utils/logprecis.py:85

Returns: {session, discovered_honeypot, tactics, techniques, commands,
          tactic_transitions, session_length}
```

#### 9e: Update Reconfigurator

```
reconfigurator.update(session)
 └─ Depending on type:
    ├─ NeverReconfigCriterion.update()  → no-op
    ├─ BasicReconfigCriterion.update()  → increments counter
    ├─ EntropyReconfigCriterion.update()
    │   ├─ Updates Counter with techniques or session_length
    │   ├─ get_prob_dist(counter)                         criteria/entropy.py:13
    │   └─ compute_entropy(prob_dist)                     criteria/entropy.py:10
    └─ TTestReconfigCriterion.update()
        ├─ compute_confidence_interval(lengths, alpha)    criteria/ttest.py:8
        └─ editdistance.eval() for tactic sequences
```

#### 9f: CHeaT Detection (if enabled)

```
cheat_detector.analyze_session(session, cowrie_logs, cheat_defenses)
                                                          Purple/cheat_detector.py:17
 ├─ check_credential_usage(cowrie_logs, planted_tokens)   cheat_detector.py:74
 │   └─ Compares used credentials against unicode honeytoken variants
 ├─ check_canary_access(session, planted_urls)            cheat_detector.py:137
 │   └─ Searches session commands for planted URLs
 ├─ check_prompt_trap_effects(session, planted_traps)     cheat_detector.py:186
 │   └─ Detects behavioral changes after trap file exposure
 ├─ _collect_indicators(unicode, canary, prompt)          cheat_detector.py:254
 └─ _compute_confidence(unicode, canary, prompt)          cheat_detector.py:287
     └─ Weighted score 0.0-1.0 indicating LLM confidence
```

#### 9g: Save Results

```
append_json_to_file(tokens_used, "tokens_used.json")      Utils/jsun.py:6
append_json_to_file(session, "sessions.json")              Utils/jsun.py:6
append_json_to_file(cheat_results, "cheat_results.json")   Utils/jsun.py:6
```

#### 9h: Generate Session Report

```
format_session_report(full_logs, session, tokens_used, report_path, cheat_results)
                                                          Sangria/session_formatter.py:14
 ├─ _build_summary(session, tokens_used)                  session_formatter.py:47
 ├─ _build_cheat_section(cheat_results)                   session_formatter.py:209
 └─ _build_interaction_log(logs)                          session_formatter.py:124
     └─ Writes Markdown report to attack_N.md
```

### Step 10: Reconfiguration Check (after each session)

```
reconfigurator.should_reconfigure()
 └─ Depending on type:
    ├─ NeverReconfigCriterion  → always False
    ├─ BasicReconfigCriterion  → counter >= interval
    ├─ EntropyReconfigCriterion
    │   └─ moving_average(entropies, window)              criteria/entropy.py:17
    │       └─ True if entropy change < tolerance (plateau detected)
    └─ TTestReconfigCriterion
        └─ True if margin_of_error < epsilon (sessions converged)
```

#### IF should_reconfigure() == True:

```
stop_dockers()                                            Blue_Lagoon/honeypot_tools.py:218

generate_new_profile(base_path)                           Reconfigurator/new_config_pipeline.py:620
 ├─ sample_previous_profiles(experiment_dir, 5)           new_config_pipeline.py:120
 │   └─ Loads up to 5 previous hp_config_*/honeypot_config.json + sessions
 ├─ build_profile_prompt(schema, prev_profiles)           new_config_pipeline.py:162
 │   └─ Includes JSON schema, lure requirements, previous profile context
 ├─ query_openai(prompt, temperature=0.7)                 new_config_pipeline.py:107
 │   └─ get_client().chat.completions.create()
 ├─ extract_json(response)                                Utils/jsun.py
 ├─ finalize_profile(new_profile)                         new_config_pipeline.py:448
 │   ├─ uuid.uuid4()  →  profile["id"]
 │   ├─ datetime.now() → profile["timestamp"]
 │   ├─ _strip_nulls(profile)                             new_config_pipeline.py:503
 │   ├─ _scan_remote_file_refs(profile)                   new_config_pipeline.py:272
 │   └─ _enrich_remote_files(profile)                     new_config_pipeline.py:415
 ├─ validate_profile(new_profile, schema)                 new_config_pipeline.py:517
 │   └─ jsonschema.validate()
 ├─ validate_lure_coverage(new_profile)                   new_config_pipeline.py:530
 │   └─ Checks 6 lure categories meet minimums
 └─ is_novel(new_profile, previous_profiles, threshold)   Reconfigurator/profile_distance.py:62
     └─ profile_distance(new_profile, each_prev)          profile_distance.py:16
         └─ _jaccard_distance(set_a, set_b)               profile_distance.py:9
             └─ Across 5 dimensions: OS, services, files, users, ports
 RETRY up to 3 times if validation or novelty fails

enrich_lures(new_profile)               # Same as Step 3
apply_cheat_defenses(new_profile)       # Same as Step 4
deploy_cowrie_config(new_profile)       # Same as Step 5
apply_tool_traps_to_txtcmds(...)        # Same as Step 5b
reconfigurator.reset()

start_dockers()                         # Same as Step 7
clear_hp_logs()
log_extractor.reset_offset()
wait_for_cowrie()
wait_for_db()
```

### Step 11: Cleanup

```
stop_dockers()                                            Blue_Lagoon/honeypot_tools.py:218
 ├─ subprocess: docker-compose down --remove-orphans
 └─ subprocess: docker image prune -f
```

---

## PATH B: Multi-Hop Honeynet — `main_honeynet()` at `main.py:264-469`

### Steps 1-2: Create Experiment + Build Chain

```
create_experiment_folder(experiment_name)                  Utils/meta.py:10

build_chain_manifest(run_id, chain_profiles)               Blue_Lagoon/credential_chain.py:52
 └─ For each profile in chain_profiles:
    ├─ json.load(profile_path)
    ├─ Extracts hostname, root credentials
    ├─ Assigns IPs: 172.{RID}.{net}.{host}
    └─ Creates HopInfo(hop_index, attack_ip, internal_ip, subnet, ssh_port, ...)

Returns: ChainManifest(hops=[HopInfo, HopInfo, HopInfo], run_id)
```

### Step 3: Per-Hop Initialization (FOR EACH HOP)

```
FOR hop_index, hop IN manifest.hops:
 │
 ├─ json.load(hop.profile_path)
 │
 ├─ enrich_lures(profile)                                 # Same as Path A Step 3
 │
 ├─ apply_cheat_defenses(profile)                         # Same as Path A Step 4
 │
 ├─ inject_next_hop_breadcrumbs(profile, hop, next_hop)   Blue_Lagoon/credential_chain.py:109
 │   ├─ _inject_etc_hosts(profile, next_ip, next_hostname)
 │   │                                                    credential_chain.py:152
 │   │   └─ Adds "172.x.x.x  hostname" to /etc/hosts
 │   │
 │   ├─ _inject_bash_history_no_password(profile, next_ip, next_user, next_port)
 │   │                                                    credential_chain.py:164
 │   │   └─ Adds "ssh root@172.x.x.x -p 2222" to .bash_history
 │   │
 │   ├─ _inject_ssh_config(profile, next_ip, next_user, next_hostname, next_port)
 │   │                                                    credential_chain.py:194
 │   │   └─ Adds Host block to ~/.ssh/config
 │   │
 │   ├─ _inject_scattered_password(profile, next_ip, next_user, next_password, next_hostname)
 │   │                                                    credential_chain.py:280
 │   │   └─ Places real password in one of: backup script, mail, notes, deploy config
 │   │
 │   ├─ _inject_decoy_credentials(profile, next_ip, next_hostname)
 │   │                                                    credential_chain.py:318
 │   │   └─ Adds 2 fake credential sets to /opt/.env.bak and /var/backups/credentials.old
 │   │
 │   └─ _ensure_lateral_movement_target(profile, next_ip)
 │                                                        credential_chain.py:378
 │       └─ Adds next-hop to lures.lateral_movement_targets
 │
 ├─ deploy_cowrie_config(profile, hop_index=i)            # Same as Path A Step 5
 │   └─ Deploys to cowrie_config_hop{i+1}/ instead of cowrie_config/
 │
 └─ apply_tool_traps_to_txtcmds(txtcmds_path, profile)   # Same as Path A Step 5b
```

### Step 4: Generate Honeynet Compose

```
generate_honeynet_compose(manifest)                       Blue_Lagoon/compose_generator.py:23
 ├─ Builds YAML with:
 │   ├─ Kali service on net_entry
 │   ├─ pot1 on net_entry + net_hop1
 │   ├─ pot2 on net_hop1 + net_hop2
 │   └─ pot3 on net_hop2
 ├─ FOR EACH HOP with DB:
 │   ├─ _inject_db_env(svc, hop_num, hop_index, run_id, hop)
 │   │                                                    compose_generator.py:128
 │   └─ _build_db_service(hop_num, hop_index, run_id, hop)
 │                                                        compose_generator.py:159
 └─ yaml.dump() → docker-compose.honeynet.yml
```

### Step 5: Start All Containers

```
start_dockers()                                           # Same as Path A Step 7

clear_hp_logs()                                           Blue_Lagoon/honeypot_tools.py:326
 └─ Clears logs for ALL hops (honeynet mode)

log_extractor.reset_offset()                              Sangria/log_extractor.py:20

wait_for_all_cowrie(len(manifest.hops))                   Blue_Lagoon/honeypot_tools.py:441
 └─ FOR EACH HOP:
     wait_for_cowrie(f"pot{i+1}")                         honeypot_tools.py:418

wait_for_honeynet_dbs(config.chain_db_enabled)            Blue_Lagoon/honeypot_tools.py:447
 └─ FOR EACH HOP with db_enabled=True:
     Polls docker inspect for healthy status
```

### Step 6: Attack Session Loop

**Identical to Path A Step 9**, except:
- Only attacks Hop 1 (`pot1_profile` used for prompt)
- `log_extractor` reads from `cowrie_config_hop1/var/log/cowrie/cowrie.json`

### Step 7: Per-Hop Reconfiguration (credential-stable)

```
IF reconfigurator.should_reconfigure():
 │
 FOR EACH HOP:
 │
 ├─ stop_single_hop(hop_idx)                              Blue_Lagoon/honeypot_tools.py:395
 │   ├─ _resolve_container_name(f"pot{hop_idx+1}")        honeypot_tools.py:377
 │   └─ subprocess: docker stop <container>
 │
 ├─ json.load(hop.profile_path)       # Reload base profile
 ├─ enrich_lures(new_profile)         # Re-enrich
 ├─ apply_cheat_defenses(new_profile) # Re-apply defenses
 │
 ├─ inject_next_hop_breadcrumbs(new_profile, hop, next_hop)
 │   └─ SAME credentials as before (credential-stable)
 │
 ├─ deploy_cowrie_config(new_profile, hop_index=hop_idx)
 ├─ apply_tool_traps_to_txtcmds(...)
 │
 └─ start_single_hop(hop_idx)                             Blue_Lagoon/honeypot_tools.py:406
     ├─ _resolve_container_name(f"pot{hop_idx+1}")
     ├─ subprocess: docker start <container>
     └─ wait_for_cowrie(f"pot{hop_idx+1}")
```

### Step 8: Post-Experiment Session Correlation

```
correlate_sessions(manifest)                              Purple/session_correlator.py:156
 ├─ FOR EACH HOP:
 │   _build_hop_sessions(hop_index)                       session_correlator.py:116
 │    ├─ _read_hop_events(hop_index)                      session_correlator.py:97
 │    │   ├─ get_cowrie_log_path(hop_index)               Blue_Lagoon/honeypot_tools.py:319
 │    │   └─ json.loads() for each line
 │    └─ _parse_timestamp(ts)                             session_correlator.py:87
 │        └─ Returns HopSession objects keyed by session_id
 │
 ├─ IP-chain matching:
 │   Hop1 sessions → find Hop2 sessions where src_ip == hop1.internal_ip
 │   Hop2 sessions → find Hop3 sessions where src_ip == hop2.internal_ip
 │
 └─ Returns list[AttackerJourney]
     Each journey has: hop_sessions, total_dwell_time, max_hop_reached, pivot_success

print_correlation_report(journeys)                        session_correlator.py:227
 └─ Prints journey summaries to stdout

save_json_to_file([j.summary() for j in journeys], "session_correlation.json")
```

### Step 9: Cleanup

```
stop_dockers()                                            # Same as Path A Step 11
```

---

## Inside Cowrie: What Happens When a Command Arrives

This runs inside the Docker container, triggered by Sangria's SSH commands:

```
Attacker types command via SSH
 │
 ├─ Cowrie SSH server receives command
 │
 ├─ Built-in command handler check
 │   ├─ ls, cd, cat, head, tail, etc. → handled natively
 │   ├─ cat /etc/passwd → reads from honeyfs/etc/passwd
 │   └─ ls /var → reads from fs.pickle tree
 │
 ├─ TxtCmds check
 │   └─ e.g., "uname -a" → reads share/cowrie/txtcmds/usr/bin/uname
 │
 └─ IF NOT HANDLED → LLM Fallback
    │
    handle_command(command)                    Cowrie/.../llm_fallback.py:~400
     │
     ├─ Check cache (if enabled)
     │   └─ normalize_cache_key(command)      Utils/llm_cache.py:11
     │
     ├─ Build pre-query context
     │   prequery.build_context(command, profile)  Cowrie/.../prequery.py
     │    ├─ Strip wrappers (sudo, nohup, env, time, etc.)
     │    ├─ Match command family (117+ mappings)
     │    ├─ Extract paths from arguments
     │    ├─ Resolve paths against filesystem + profile
     │    └─ Assemble context (max 3000 chars)
     │
     ├─ Get session state
     │   SessionStateRegister.get_context()
     │    └─ Last 50 entries with LRU eviction, impact-scored
     │
     ├─ Get conversation history
     │   └─ Last 20 command-response pairs
     │
     ├─ LLMClient.call(system_prompt + prequery + state + history)
     │                                        llm_fallback.py
     │   └─ HTTP POST to configured LLM endpoint
     │       └─ Logs tokens to var/llm_tokens.jsonl
     │
     ├─ Impact classification (0-4)
     │   └─ 0=read-only, 1=config, 2=service, 3=data, 4=critical
     │
     ├─ Install detection (regex)
     │   └─ Detects apt install, pip install, etc.
     │
     └─ Store in cache + state register
```

---

## Complete Call Count Summary

| Phase | Function Calls (approx per session) |
|-------|-------------------------------------|
| Startup & Deploy | ~25 functions |
| Per Attack Iteration | ~12 functions (LLM call + SSH + state update) |
| Per Session (200 iterations) | ~2,400 function calls |
| Session Extraction | ~8 functions |
| CHeaT Detection | ~6 functions |
| Reconfiguration | ~35 functions (full redeploy) |
| Post-Experiment Correlation | ~12 functions |
