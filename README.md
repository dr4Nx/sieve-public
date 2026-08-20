# Parser-Free Log Querying
> LLM-generated code as a substitute for log parsers in security log analysis

## Table of Contents

- [Overview](#overview)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [LLM API Configuration](#llm-api-configuration)
  - [Usage](#usage)
- [Reproducing Experiments](#reproducing-experiments)
- [Building Queries from Scratch](#building-queries-from-scratch)
- [Data](#data)

---

## Overview

Given a natural-language query and a raw log file, an LLM (Gemini) writes a
Python or shell filter that reads the file and returns the matching lines or
extracted fields. The framework executes the filter in a sandboxed subprocess
and scores the output against rule-based ground truth.

**Repository layout:**

| Path | Contents |
|------|----------|
| `log_query/` | LLM client, prompt construction, sandboxing, templaters |
| `evaluation/` | Multi-query runner, F1 scoring, report writers |
| `ground_truth/` | Per-log-type rule-based parsers and query builders |
| `queries/` | Pre-built query benchmarks (10 JSONs, larger ones gzipped) |
| `human_baselines/` | Hand-written grep / Python scripts used as the human comparison |
| `log_parser.py` | Single-query CLI |
| `evaluate.py` | Multi-query evaluator |
| `experiments.py` | Experiment orchestrator |

## Getting Started

### Prerequisites

- **Python**: 3.10 or higher
- **API Access**: At least one Gemini API key, or Vertex AI access

### Installation

```bash
# Create virtual environment
python3 -m venv env
source env/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### LLM API Configuration

The model is selected with `--model MODEL`. The backend is inferred from the
name: anything starting with `gemini-` routes to Google; anything starting
with `gpt-`, `o1`, `o3`, `o4`, or `o5` routes to OpenAI.

#### Gemini API

```bash
export GEMINI_API_KEY=YOUR_API_KEY
export GEMINI_API_KEY_2=YOUR_API_KEY_2  # optional
export GEMINI_API_KEY_3=YOUR_API_KEY_3  # optional
```

The evaluator rotates round-robin across all keys present and skips any key
that returns billing-exhausted at startup. Default model: `gemini-2.5-flash`.

#### Vertex AI

```bash
gcloud auth application-default login
export USE_VERTEX_AI=1
export VERTEX_PROJECT=YOUR_GCP_PROJECT
```

Add `--vertex-ai` to single-query commands; `experiments.py` reads
`USE_VERTEX_AI` from the environment.

#### OpenAI

```bash
export OPENAI_API_KEY=YOUR_API_KEY
```

Pass any OpenAI chat-completions model with `--model`, for example
`--model gpt-5.4`, `--model gpt-4o`, or `--model o3`.

### Usage

#### Single Query

```bash
python log_parser.py "Find DHCPACK lines" data/logs/dhcp --language python
```

| Argument | Default | Description |
|----------|---------|-------------|
| `--language` | `bash` | `bash` or `python` for the generated filter |
| `--model` | `gemini-2.5-flash` | Gemini model ID |
| `--templates PATH` | - | Hand-written template file |
| `--templater` | - | `frequency` or `drain3` to auto-generate templates |
| `--sample-size` | `250` | Reservoir sample size passed in the prompt |
| `--sample-seed N` | - | Make sampling deterministic |
| `--max-retries` | `4` | Retries with error feedback on failure |
| `--validate` | - | Run the generated filter on the sample first |

#### Evaluation

```bash
python evaluate.py queries/dhcp_simple.json data/logs/dhcp \
    --templater frequency \
    --language python \
    --sample-size 100 \
    --max-workers 8
```

Reports land under `eval/<dataset>/<run>/` with per-query F1, generated code,
and matched lines.

Larger query JSONs (`audit_simple`, `dhcp_simple`, `dhcp_complex`,
`puppet_simple`, `sshd_simple`) are stored gzipped. The loader transparently
falls back to `<file>.json.gz` when `<file>.json` is missing; `gunzip -k` if
you want to read them in an editor.

## Reproducing Experiments

`experiments.py` wraps `evaluate.py` for the experiments reported in the
paper.

| Experiment | Description |
|-----------|-------------|
| `template-compare` | Compare context strategies: matryoshka (manual), drain3, frequency, random-only, none |
| `prompt-ablation` | Drop one prompt component at a time and measure F1 |
| `model-compare` | Compare Gemini models on a fixed strategy |
| `language-compare` | Bash vs Python for the generated filter |
| `sample-size` | Sweep the number of context sample lines |
| `consistency` | Run each query N times to measure variance |
| `human-baseline` | Compare LLM filters against `human_baselines/` |
| `few-shot` | Add worked query/code examples to the prompt |
| `retry-analysis` | Track how often retries flip wrong answers to correct ones |
| `cross-log-transfer` | Use templates from a different log type |

| Argument | Default | Description |
|----------|---------|-------------|
| `--experiment` | - | **Required**. Experiment name from the table above |
| `--datasets` | `audit_simple puppet_simple` | One or more of `<logtype>_<simple\|complex>` |
| `--model` | `gemini-2.5-flash` | Single model for non-comparison experiments |
| `--models` | all | Override model list for `model-compare` / `full-matrix` |
| `--language` | `python` | `bash` or `python` |
| `--sample-size` | `50` | Reservoir sample size |
| `--max-workers` | `1` | Parallel workers per eval run |
| `--runs` | `5` | Repeats for `consistency` |

Example:

```bash
python experiments.py --experiment template-compare \
    --datasets dhcp_simple dhcp_complex \
    --max-workers 20
```

Outputs land under `eval/experiments/<name>/<timestamp>/`.

## Building Queries from Scratch

Each `ground_truth/<logtype>/build_queries.py` regenerates the dataset's
JSON from the raw log file and a rule-based parser:

```bash
python -m ground_truth.audit.build_queries  --log-file data/logs/audit
python -m ground_truth.cron.build_queries   --log-file data/logs/cron
python -m ground_truth.puppet.build_queries --log-file data/logs/puppet
python -m ground_truth.sshd.build_queries   --log-file data/logs/sshd
```

DHCP queries are not regenerated from a parser; the JSON in `queries/` is the
canonical version.

## Data

### SecurityLogs Dataset

The benchmark targets five log types from the SecurityLogs corpus.
The raw logs ship gzipped under `data/logs/`. Decompress them once after
cloning:

```bash
gunzip data/logs/*.gz
```

This produces `data/logs/{audit,cron,dhcp,puppet,sshd}` (uncompressed), which
is where the default `LOG_FILES` paths in `experiments.py` point. Set
`LOG_DIR` if you want the logs elsewhere.

**Included Log Types:**

| Type | Lines | Source |
|------|-------|--------|
| Audit  | Linux audit subsystem  | SecurityLogs |
| SSH    | OpenSSH server         | SecurityLogs |
| DHCP   | dhclient / dhcpd       | SecurityLogs |
| CRON   | cron + PAM session     | SecurityLogs |
| Puppet | Puppet agent runs      | SecurityLogs |

### Human Baseline

`human_baselines/` contains 93 hand-written grep / Python reference scripts
representing a typical sysadmin approach to each query. See
`human_baselines/README.md` for layout and conventions.

### Determinism

`--sample-seed <int>` makes reservoir sampling deterministic. Variance across
repeated runs then reflects only model nondeterminism.
