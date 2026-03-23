# Purple Analysis Suite

## Overview

Purple is Project Violet's data analysis and visualization engine. It processes raw attack session logs from Sangria and Cowrie, extracts MITRE ATT&CK classifications, computes statistical metrics, generates publication-quality visualizations, and determines when honeypot configurations should trigger reconfiguration.

## Three Analysis Modes

### 1. HP Comparison (`hp_comparison_cli.py`)

Compares session characteristics across multiple experiments.

**Input:** 2+ experiments selected interactively. Reads `hp_config_*/full_logs/attack_*.json`.

**Metrics per experiment:**
- Mean, Variance, Standard Deviation
- Min, Max, Range
- Median, Q1, Q3, IQR
- 95% Confidence Interval (t-distribution)
- Five most common session lengths

**Output:**
- `session_length_statistics.csv` — raw statistics table
- `session_length_comparison_boxplot.png` — boxplot with means marked (red diamonds)
- `session_length_mean_comparison.png` — bar chart with 95% CI error bars

### 2. Meta Analysis (`meta_analysis_cli.py`)

Cross-experiment MITRE ATT&CK distribution analysis.

**Tactic Distribution:** Counts tactic occurrences across all sessions, computes per-tactic percentages per experiment, generates stacked bar charts and CSV.

**Honeypot Deceptiveness:** Segments sessions by `discovered_honeypot` field ("yes"/"no"), compares session lengths, calculates detection percentage per experiment.

**Unique Sessions Over Time:** Tracks cumulative unique tactic sequences per session, plots convergence (plateau = behavioral saturation).

**Output:**
- `tactic_distribution_total.png`, `tactic_distribution_stacked.png`, `tactic_distribution.csv`
- `honeypot_deceptiveness.csv`
- `unique_sessions_over_time.png`

### 3. Advanced Visualizations (`run_analysis.py`)

Interactive suite with custom experiment ordering and flexible plot selection.

**Plot types:**

| Plot | What It Shows |
|------|--------------|
| Session Length | Raw session length per session index; vertical dashed lines at reconfig boundaries |
| MITRE Distribution (4 variants) | Cumulative/new tactics per session; cumulative/new techniques per session |
| Entropy (6 variants) | Shannon entropy of tactics/techniques/session_length, both global and per-config |
| Criteria (4 variants) | Levenshtein distance and session length running averages, global and per-config |
| Criteria Boxplot | Per-configuration session length boxplots with 95% CI |

## Metrics Engine

### Session Length (`metrics/session_length.py`)

Computes descriptive statistics from session `length` fields: mean, variance, std, min, max, range, median, quartiles, IQR, five most common lengths.

### MITRE Distribution (`metrics/mitre_distribution.py`)

Extracts tactic and technique counts across sessions. Returns:
- Global counts and fractional probabilities
- Per-session counts (new tactics/techniques per session)
- Cumulative unique counts over time
- Heatmaps: `(num_tactics, num_sessions)` matrices

### Entropy (`metrics/entropy.py`)

Shannon entropy: $H = -\sum p_i \ln(p_i)$

**Tactic/Technique entropy:** probability distribution of tactic or technique occurrences. High entropy = diverse patterns (unpredictable); low entropy = dominated by few patterns (predictable, attacker is stuck).

**Session length entropy:** probability distribution of session lengths. Converged = entropy plateau.

Running calculation shows convergence over time.

### Tactic Sequence Analysis (`metrics/sequences.py`)

Extracts ordered tactic/technique/command sequences per session. Encodes as indexed integer arrays for Levenshtein distance computation.

## Reconfiguration Criteria Evaluation

### Convergence Detection

Two independent convergence metrics determine when a honeypot configuration has become predictable:

#### Levenshtein Distance Criterion

For each new session, compute edit distances to all prior sessions' tactic sequences. Track the running confidence interval. When the margin of error becomes small relative to the standard deviation (`MOE < 0.2 * std`), behavior is predictable.

#### Session Length Criterion

Track running confidence interval of session lengths. When margin of error becomes small relative to standard deviation, session lengths have stabilized.

### Cutoff Behavior

**Default (cutoff=False):** records criterion-met index but continues processing all sessions. Useful for visualization.

**Cutoff mode (cutoff=True):** breaks immediately on first convergence, treats subsequent configurations as fresh starts. Simulates actual reconfiguration triggering.

### Confidence Interval Calculation

Uses Student's t-distribution:

```
MOE = t_critical * (sample_std / sqrt(n))
```

95% CI by default (alpha = 0.05).

## CHeaT Detection (Post-Session)

See [CHeaT Defenses](cheat_defenses.md) for full details. Purple's `cheat_detector.py` runs post-session analysis against planted defense metadata:

- Unicode honeytoken credential matching
- Canary URL access detection
- Prompt trap behavioral change detection
- Overall LLM confidence score (0.0-1.0)

## Data Flow

```
Raw Attack Session (attack_*.json)
         |
    extraction.py: extract_session()
         |
    Enhanced Session (sessions.json per hp_config_)
    {session, discovered_honeypot, tactics, techniques, length, full_session}
         |
    Purple: extract_experiment(logs_path)
    ├── Load sessions.json from each hp_config_N/
    ├── Compute reconfig_indices (cumulative session counts)
    └── Return: (combined_sessions, config_sessions, reconfig_indices)
         |
    Metrics Calculation
    ├── measure_session_length()
    ├── measure_mitre_distribution()
    ├── measure_entropy_tactics/techniques()
    └── measure_tactic_sequences()
         |
    Convergence Evaluation
    ├── Levenshtein distances between tactic sequences
    ├── Confidence intervals for distributions
    └── Compare MOE < epsilon threshold
         |
    Visualization & Export
    ├── PNG plots (boxplots, bar charts, line plots, heatmaps)
    └── CSV tables (statistics, distributions)
```

## Output Structure

```
logs/hp_comparison/
├── session_length_statistics.csv
├── session_length_comparison_boxplot.png
└── session_length_mean_comparison.png

logs/{experiment}/meta_analysis/
├── tactic_distribution_total.png
├── tactic_distribution_stacked.png
├── tactic_distribution.csv
├── honeypot_deceptiveness.csv
└── unique_sessions_over_time.png

logs/{experiment}/analysis_plots/
├── session_length_{timestamp}.png
├── mitre_data_cum_tactics_{timestamp}.png
├── mitre_data_num_techniques_{timestamp}.png
├── entropy_tactics_{timestamp}.png
├── entropy_config_entropy_tactics_{timestamp}.png
├── criteria_1_{timestamp}.png          # Levenshtein global
├── criteria_2_{timestamp}.png          # Session length global
├── criteria_3_{timestamp}.png          # Levenshtein per-config
├── criteria_4_{timestamp}.png          # Session length per-config
├── criteria_boxplot_1_{timestamp}.png
└── criteria_boxplot_2_{timestamp}.png
```

## Design Insights

### Multi-Metric Redundancy

Purple uses 3 independent convergence signals (tactic sequence similarity, session length distribution, entropy) to avoid false positives. Example: high tactic entropy + stable sequence pattern = need reconfig; high tactic entropy + variable session lengths = normal variation.

### CHeaT's Orthogonal Role

Reconfiguration detects **when** to swap profiles. CHeaT detects **who** is attacking (LLM vs human). Together: the honeypot adapts to attacker behavior while simultaneously classifying the attacker type.

### Visualization for Explainability

Each plot maps to a specific analytical question:
- **Session Length:** "Is the attacker's behavior consistent?"
- **Tactic Distribution:** "Is the attacker exploiting the same attack stages?"
- **Entropy:** "Is the attacker becoming more predictable?"
- **Criteria:** "When should reconfiguration trigger?"
- **Boxplot:** "Which configurations were most effective?"
