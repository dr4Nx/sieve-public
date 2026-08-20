#!/usr/bin/env python3
"""Experiment runner for log query evaluation.

Usage:
    python experiments.py --experiment <name> [options]

Core Experiments:
    template-compare     Compare template strategies: matryoshka (manual), drain3, frequency, random-only, none
    model-compare        Compare models across a fixed template strategy
    consistency          Run each query N times to measure output consistency
    sample-size          Vary the number of random sample lines
    language-compare     Compare bash vs python generated filters
    human-baseline       Compare LLM output against human best-effort scripts
    full-matrix          Run template-compare x model-compare (all combinations)

Ablation & Analysis Experiments:
    template-granularity Compare named-placeholder templates vs generic-wildcard vs raw examples
    prompt-ablation      Systematically remove prompt sections to measure F1 drop
    query-complexity     Plot F1 vs query complexity (simple, complex)
    retry-analysis       Measure how often retries fix errors vs produce different wrong answers
    cross-log-transfer   Use templates from one log type to query another (wrong templates)
    token-efficiency     Plot F1 against input token count across strategies and sample sizes
    few-shot             Compare zero-shot vs few-shot (worked examples in prompt)
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime


# ---------------------------------------------------------------------------
# Defaults: paths, models, and parameter values used across experiments
# ---------------------------------------------------------------------------

EVAL_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evaluate.py")

_LOG_DIR = os.environ.get("LOG_DIR", "data/logs")

# Raw log files by log type
LOG_FILES = {
    "audit": os.path.join(_LOG_DIR, "audit"),
    "puppet": os.path.join(_LOG_DIR, "puppet"),
    "dhcp": os.path.join(_LOG_DIR, "dhcp"),
    "sshd": os.path.join(_LOG_DIR, "sshd"),
    "cron": os.path.join(_LOG_DIR, "cron"),
}

# Evaluation query JSON files, keyed as "<logtype>_<complexity>"
QUERY_FILES = {
    "audit_simple": "queries/audit_simple.json",
    "audit_complex": "queries/audit_complex.json",
    "puppet_simple": "queries/puppet_simple.json",
    "puppet_complex": "queries/puppet_complex.json",
    "dhcp_simple": "queries/dhcp_simple.json",
    "dhcp_complex": "queries/dhcp_complex.json",
    "sshd_simple": "queries/sshd_simple.json",
    "sshd_complex": "queries/sshd_complex.json",
    "cron_simple": "queries/cron_simple.json",
    "cron_complex": "queries/cron_complex.json",
}

# Hand-crafted template files with named placeholders (e.g. <PROCESS_ID>)
MANUAL_TEMPLATES = {
    "audit": "templates/audit.json",
    "puppet": "templates/puppet.json",
    "dhcp": "templates/dhcp_v2.json",
    "sshd": "templates/sshd.json",
    "cron": "templates/cron.json",
}

# Models to compare in model-compare and full-matrix experiments
MODELS = [
    "gemini-3.1-pro-preview",
    "gemini-2.5-pro",
    "gemini-3-flash-preview",
    "gemini-3.1-flash-lite-preview",
]

LANGUAGES = ["bash", "python"]

# Sample sizes to sweep in sample-size experiment
SAMPLE_SIZES = [0, 25, 50, 100, 250]

DEFAULT_DATASETS = ["audit_simple", "puppet_simple"]
DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_LANGUAGE = "python"
DEFAULT_SAMPLE_SIZE = 50
DEFAULT_MAX_WORKERS = 1
DEFAULT_MAX_RETRIES = 4
DEFAULT_TIMEOUT = 600
DEFAULT_CONSISTENCY_RUNS = 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _log_type_for_dataset(dataset: str) -> str:
    """Extract log type from dataset name, e.g. 'audit_simple' -> 'audit'."""
    return dataset.split("_")[0]


def _count_errors(output_path: str) -> tuple[int, int]:
    """Return (error_count, query_count) from a report file."""
    if not output_path or not os.path.isfile(output_path):
        return 0, 0
    error_count = 0
    query_count = 0
    with open(output_path, errors="ignore") as f:
        for line in f:
            if line.startswith("ID: "):
                query_count += 1
            stripped = line.strip()
            if stripped.startswith("ERROR") and any(
                code in line for code in ["RESOURCE_EXHAUSTED", "UNAVAILABLE", "DEADLINE_EXCEEDED", "timeout expired"]
            ):
                error_count += 1
    return error_count, query_count


def _preflight_check(model: str) -> bool:
    """Quick API ping to verify the model is available."""
    try:
        from google import genai
        from dotenv import load_dotenv
        load_dotenv()
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            return True  # No key check possible, assume OK
        client = genai.Client(api_key=key)
        client.models.generate_content(model=model, contents="ping")
        return True
    except Exception as exc:
        print(f"Pre-flight check failed for {model}: {str(exc)[:120]}", file=sys.stderr)
        return False


def _run_eval_subprocess(cmd: list[str]) -> int:
    print(f"\n{'=' * 70}")
    print(f"Running: {' '.join(cmd)}")
    print(f"{'=' * 70}\n", flush=True)
    return subprocess.call(cmd)


def _run_eval(
    query_file: str,
    log_file: str,
    *,
    model: str = DEFAULT_MODEL,
    language: str = DEFAULT_LANGUAGE,
    sample_size: int = DEFAULT_SAMPLE_SIZE,
    templates: str | None = None,
    templater: str | None = None,
    max_workers: int = DEFAULT_MAX_WORKERS,
    max_retries: int = DEFAULT_MAX_RETRIES,
    timeout: int = DEFAULT_TIMEOUT,
    output: str | None = None,
    consistency: bool = False,
    runs: int = DEFAULT_CONSISTENCY_RUNS,
    verbose: bool = True,
    extra_args: list[str] | None = None,
    max_attempts: int = 3,
    error_tolerance: float = 0.1,
) -> int:
    """Build and run an evaluate.py subprocess command.

    Retries the eval up to ``max_attempts`` times when more than
    ``error_tolerance`` fraction of queries hit infrastructure errors,
    pausing between attempts. Raises QuotaExhaustedError if errors persist.
    """
    cmd = [
        sys.executable, EVAL_SCRIPT,
        query_file, log_file,
        "--model", model,
        "--language", language,
        "--sample-size", str(sample_size),
        "--max-workers", str(max_workers),
        "--max-retries", str(max_retries),
        "--timeout", str(timeout),
    ]
    if os.environ.get("USE_VERTEX_AI"):
        cmd.append("--vertex-ai")
    if templates:
        cmd.extend(["--templates", templates])
    elif templater:
        cmd.extend(["--templater", templater])
    if output:
        cmd.extend(["--output", output])
    if consistency:
        cmd.append("--consistency")
        cmd.extend(["--runs", str(runs)])
    if verbose:
        cmd.append("--verbose")
    if extra_args:
        cmd.extend(extra_args)

    # Brief pause between eval runs to avoid back-to-back quota pressure
    time.sleep(5)

    rc = _run_eval_subprocess(cmd)
    error_count, query_count = _count_errors(output)
    error_rate = error_count / query_count if query_count else 0
    if query_count and error_rate > error_tolerance:
        print(f"\n*** {error_count}/{query_count} queries hit infrastructure errors "
              f"(rate {error_rate:.0%} > tolerance {error_tolerance:.0%}) ***")
        for attempt in range(2, max_attempts + 1):
            wait = 300  # 5 minute backoff
            print(f"Waiting {wait}s before retry attempt {attempt}/{max_attempts}...")
            time.sleep(wait)
            print(f"Retry attempt {attempt}/{max_attempts}")
            rc = _run_eval_subprocess(cmd)
            error_count, query_count = _count_errors(output)
            error_rate = error_count / query_count if query_count else 0
            if not query_count or error_rate <= error_tolerance:
                print(f"Recovered: {error_count}/{query_count} errors after retry.")
                break
        else:
            print(f"\n*** ABORT: {error_count}/{query_count} queries still failing after {max_attempts} attempts ***")
            raise QuotaExhaustedError(f"{error_count}/{query_count} queries failed in {output}")
    return rc
    return rc


class QuotaExhaustedError(Exception):
    """Raised when a 429 quota error is detected in eval output."""
    pass


def _output_path(experiment: str, tag: str, timestamp: str) -> str:
    """Create experiment output directory and return the report file path."""
    exp_dir = os.path.join("eval", "experiments", experiment, timestamp)
    os.makedirs(exp_dir, exist_ok=True)
    return os.path.join(exp_dir, f"{tag}.txt")


def _build_stripped_templates(source_path: str, output_path: str, *, strip_names: bool = False) -> str:
    """Build a modified template file from a manual template source.

    If strip_names is True, replace named placeholders like <PROCESS_ID>
    with generic <*> wildcards. Examples are kept unchanged so the LLM
    still sees real log lines but loses the semantic field names.
    """
    with open(source_path) as f:
        data = json.load(f)

    templates = data.get("templates", [])
    examples = data.get("examples", {})

    if strip_names:
        import re
        new_templates = []
        new_examples = {}
        for t in templates:
            stripped = re.sub(r"<[A-Z_]+>", "<*>", t)
            new_templates.append(stripped)
            if t in examples:
                new_examples[stripped] = examples[t]
        data = {"templates": new_templates, "examples": new_examples}

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    return output_path


def _build_examples_only_templates(source_path: str, output_path: str) -> str:
    """Build a template file that contains only raw example lines, no template patterns.

    Each unique example line becomes a "template" entry. This tests whether
    the LLM can infer structure from raw lines alone without abstracted patterns.
    """
    with open(source_path) as f:
        data = json.load(f)

    examples = data.get("examples", {})
    example_lines = [ex for ex in examples.values() if ex]
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for line in example_lines:
        if line not in seen:
            seen.add(line)
            unique.append(line)

    out_data = {"templates": unique, "examples": {}}
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(out_data, f, indent=2)
        f.write("\n")
    return output_path


# ---------------------------------------------------------------------------
# Core Experiments
# ---------------------------------------------------------------------------

def run_template_compare(args) -> None:
    """Compare template strategies on fixed model/language/sample-size.

    Strategies:
      - matryoshka: hand-crafted templates with named placeholders + examples
      - drain3:     auto-generated templates via drain3 log mining
      - frequency:  auto-generated templates via frequency-based token analysis
      - random-only: no templates, only random sample lines from the log
      - none:       no templates and no sample lines (query + prompt only)

    Each strategy is run on every dataset. Results show how much each
    type of log context contributes to LLM accuracy.
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    strategies = {
        "matryoshka": lambda ds: {"templates": MANUAL_TEMPLATES[_log_type_for_dataset(ds)]},
        "drain3": lambda _: {"templater": "drain3"},
        "frequency": lambda _: {"templater": "frequency"},
        "random-only": lambda _: {},       # sample lines only, no templates
        "none": lambda _: {"sample_size": 1},  # minimal context (1 line, no templates)
    }

    for dataset in args.datasets:
        log_type = _log_type_for_dataset(dataset)
        query_file = QUERY_FILES[dataset]
        log_file = LOG_FILES[log_type]

        for strategy_name, strategy_fn in strategies.items():
            tag = f"{dataset}_{strategy_name}"
            out = _output_path("template-compare", tag, timestamp)
            kwargs = strategy_fn(dataset)
            _run_eval(
                query_file, log_file,
                model=args.model,
                language=args.language,
                sample_size=kwargs.pop("sample_size", args.sample_size),
                templates=kwargs.get("templates"),
                templater=kwargs.get("templater"),
                max_workers=args.max_workers,
                output=out,
            )


def run_model_compare(args) -> None:
    """Compare different Gemini models on the same queries and templates.

    Uses manual templates (matryoshka) as a fixed context so the only
    variable is the model. Useful for measuring how model capability
    translates to log query accuracy.
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    models = args.models or MODELS

    for dataset in args.datasets:
        log_type = _log_type_for_dataset(dataset)
        query_file = QUERY_FILES[dataset]
        log_file = LOG_FILES[log_type]

        for model in models:
            tag = f"{dataset}_{model.replace('/', '_')}"
            out = _output_path("model-compare", tag, timestamp)
            _run_eval(
                query_file, log_file,
                model=model,
                language=args.language,
                sample_size=args.sample_size,
                templates=MANUAL_TEMPLATES.get(log_type),
                max_workers=args.max_workers,
                output=out,
            )


def run_consistency(args) -> None:
    """Run each query N times to measure output consistency.

    Uses the --consistency flag in evaluate.py which runs all queries
    multiple times and reports per-query variance (precision/recall/f1
    min/max/mean). Reveals how much non-determinism affects results.
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    for dataset in args.datasets:
        log_type = _log_type_for_dataset(dataset)
        query_file = QUERY_FILES[dataset]
        log_file = LOG_FILES[log_type]

        tag = f"{dataset}_consistency"
        out = _output_path("consistency", tag, timestamp)
        _run_eval(
            query_file, log_file,
            model=args.model,
            language=args.language,
            sample_size=args.sample_size,
            templates=MANUAL_TEMPLATES.get(log_type),
            max_workers=args.max_workers,
            consistency=True,
            runs=args.runs,
            output=out,
        )


def run_sample_size(args) -> None:
    """Vary the number of random sample lines included in the prompt.

    Keeps manual templates fixed and sweeps sample_size through
    [0, 25, 50, 100, 250] (or --sample-sizes override). Tests whether
    more random lines improve accuracy or just waste tokens.
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    sizes = args.sample_sizes or SAMPLE_SIZES

    for dataset in args.datasets:
        log_type = _log_type_for_dataset(dataset)
        query_file = QUERY_FILES[dataset]
        log_file = LOG_FILES[log_type]

        for size in sizes:
            tag = f"{dataset}_sample{size}"
            out = _output_path("sample-size", tag, timestamp)
            _run_eval(
                query_file, log_file,
                model=args.model,
                language=args.language,
                sample_size=size,
                templates=MANUAL_TEMPLATES.get(log_type),
                max_workers=args.max_workers,
                output=out,
            )


def run_language_compare(args) -> None:
    """Compare bash (grep/awk) vs python generated filters.

    Same model, templates, and queries; only the output language differs.
    Tests whether one language produces more reliable log filters.
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    languages = args.languages or LANGUAGES

    for dataset in args.datasets:
        log_type = _log_type_for_dataset(dataset)
        query_file = QUERY_FILES[dataset]
        log_file = LOG_FILES[log_type]

        for lang in languages:
            tag = f"{dataset}_{lang}"
            out = _output_path("language-compare", tag, timestamp)
            _run_eval(
                query_file, log_file,
                model=args.model,
                language=lang,
                sample_size=args.sample_size,
                templates=MANUAL_TEMPLATES.get(log_type),
                max_workers=args.max_workers,
                output=out,
            )


def _run_human_scripts(
    dataset: str,
    query_file: str,
    log_file: str,
    baseline_dir: str,
    output_path: str,
) -> None:
    """Run human baseline scripts against ground truth and write a report."""
    from evaluation.io_utils import load_eval_json
    from evaluation.metrics import compute_metrics
    import re as _re

    entries = load_eval_json(query_file)
    results = []
    for entry in entries:
        qtype = entry.get("query_type", "")
        if qtype not in ("where", "select"):
            continue
        qid = entry.get("__query_key") or entry.get("id", "")
        nl = entry.get("natural_language", "")
        gt = entry.get("ground_truth", {}) or {}
        must_raw = gt.get("must_contain", []) or []
        # Normalize ground truth same as evaluation/cli.py
        must = []
        for item in must_raw:
            if isinstance(item, list):
                parts = [str(p) for p in item if p is not None]
                if parts:
                    must.append(" ".join(parts))
            elif item is not None:
                must.append(str(item))
        norm_must = [_re.sub(r"\s+", " ", m).strip() for m in must if m and m.strip()]

        # Find the script. Try query-type-specific names first to handle
        # collisions where the same id has both a where and a select variant.
        script = None
        candidates = [
            f"{qid}_{qtype}.py",
            f"{qid}_{qtype}.sh",
            f"{qid}.py",
            f"{qid}.sh",
        ]
        for name in candidates:
            candidate = os.path.join(baseline_dir, name)
            if os.path.isfile(candidate):
                script = candidate
                break
        if not script:
            results.append({"id": qid, "query": nl, "query_type": qtype,
                            "error": f"no script found for {qid}", "precision": 0.0,
                            "recall": 0.0, "f1": 0.0, "tp": 0, "fp": 0,
                            "fn": len(set(norm_must)), "returned": 0, "must": len(set(norm_must))})
            continue

        # Run the script
        if script.endswith(".py"):
            cmd = [sys.executable, script, log_file]
        else:
            cmd = ["bash", script, log_file]
        try:
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True, timeout=600)
            pred_lines = proc.stdout.strip().splitlines() if proc.stdout else []
        except Exception as exc:
            results.append({"id": qid, "query": nl, "query_type": qtype,
                            "error": str(exc), "precision": 0.0, "recall": 0.0,
                            "f1": 0.0, "tp": 0, "fp": 0,
                            "fn": len(set(norm_must)), "returned": 0, "must": len(set(norm_must))})
            continue

        norm_pred = [_re.sub(r"\s+", " ", l).strip() for l in pred_lines if l and l.strip()]
        precision, recall, f1, tp, fp, fn = compute_metrics(norm_pred, norm_must)
        results.append({"id": qid, "query": nl, "query_type": qtype,
                        "precision": precision, "recall": recall, "f1": f1,
                        "tp": tp, "fp": fp, "fn": fn,
                        "returned": len(set(norm_pred)), "must": len(set(norm_must)),
                        "script": script})

    # Write report
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    evaluated = len(results)
    macro_p = sum(r["precision"] for r in results) / evaluated if evaluated else 0
    macro_r = sum(r["recall"] for r in results) / evaluated if evaluated else 0
    macro_f1 = sum(r["f1"] for r in results) / evaluated if evaluated else 0

    with open(output_path, "w") as f:
        f.write(f"# Human baseline report for {dataset}\n")
        f.write(f"# Baseline scripts: {baseline_dir}\n")
        f.write(f"# Log file: {log_file}\n")
        f.write(f"# Queries evaluated: {evaluated}\n\n")
        for r in results:
            f.write(f"ID: {r['id']} | type: {r['query_type']} | query: {r['query']}\n")
            if r.get("error"):
                f.write(f"  ERROR: {r['error']}\n")
            if r.get("script"):
                f.write(f"  script: {r['script']}\n")
            f.write(f"  precision={r['precision']:.4f} recall={r['recall']:.4f} f1={r['f1']:.4f}"
                    f" TP={r['tp']} FP={r['fp']} FN={r['fn']}"
                    f" returned={r['returned']} must={r['must']}\n\n")
        f.write(f"# Macro Averages\n")
        f.write(f"# precision={macro_p:.4f} recall={macro_r:.4f} f1={macro_f1:.4f}\n")


def run_human_baseline(args) -> None:
    """Run human baseline scripts and LLM eval, then compare.

    Human scripts should be placed in human_baselines/<dataset>/ as
    executable files named by query ID (e.g., dhcp_query_1.sh, multiline_1.py).
    Bash scripts (.sh) are run with bash, Python scripts (.py) with python3.
    Each script receives the log file path as its only argument and should
    print output lines to stdout.
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    baseline_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "human_baselines")

    for dataset in args.datasets:
        log_type = _log_type_for_dataset(dataset)
        query_file = QUERY_FILES[dataset]
        log_file = LOG_FILES[log_type]
        ds_baseline_dir = os.path.join(baseline_dir, dataset)

        if not os.path.isdir(ds_baseline_dir):
            print(f"\nNo human baselines found at: {ds_baseline_dir}")
            print(f"To add baselines, create {ds_baseline_dir}/ with scripts named by query ID.")
            continue

        # Run human scripts
        human_out = _output_path("human-baseline", f"{dataset}_human", timestamp)
        print(f"\nRunning human baseline scripts from {ds_baseline_dir}...")
        _run_human_scripts(dataset, query_file, log_file, ds_baseline_dir, human_out)
        print(f"Human baseline report: {human_out}")

        # Run LLM eval
        llm_out = _output_path("human-baseline", f"{dataset}_llm", timestamp)
        _run_eval(
            query_file, log_file,
            model=args.model,
            language=args.language,
            sample_size=args.sample_size,
            templates=MANUAL_TEMPLATES.get(log_type),
            max_workers=args.max_workers,
            output=llm_out,
        )


def run_full_matrix(args) -> None:
    """Run the full cross-product of template strategies x models.

    This is the most expensive experiment: for each dataset it runs
    every (model, strategy) combination. With 4 models and 5 strategies
    that's 20 eval runs per dataset. Use --datasets to limit scope.
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    models = args.models or MODELS

    strategies = {
        "matryoshka": lambda ds: {"templates": MANUAL_TEMPLATES[_log_type_for_dataset(ds)]},
        "drain3": lambda _: {"templater": "drain3"},
        "frequency": lambda _: {"templater": "frequency"},
        "random-only": lambda _: {},
        "none": lambda _: {"sample_size": 1},
    }

    for dataset in args.datasets:
        log_type = _log_type_for_dataset(dataset)
        query_file = QUERY_FILES[dataset]
        log_file = LOG_FILES[log_type]

        for model in models:
            for strategy_name, strategy_fn in strategies.items():
                tag = f"{dataset}_{model.replace('/', '_')}_{strategy_name}"
                out = _output_path("full-matrix", tag, timestamp)
                kwargs = strategy_fn(dataset)
                _run_eval(
                    query_file, log_file,
                    model=model,
                    language=args.language,
                    sample_size=kwargs.pop("sample_size", args.sample_size),
                    templates=kwargs.get("templates"),
                    templater=kwargs.get("templater"),
                    max_workers=args.max_workers,
                    output=out,
                )


# ---------------------------------------------------------------------------
# Ablation & Analysis Experiments
# ---------------------------------------------------------------------------

def run_template_granularity(args) -> None:
    """Compare template detail levels: named placeholders vs wildcards vs raw examples.

    Three conditions derived from the same manual template file:
      - named-placeholders: original templates with <PROCESS_ID>, <EVENT_TYPE>, etc.
      - generic-wildcards:  same structure but all placeholders replaced with <*>
      - examples-only:      no template patterns at all, just one raw log line per template

    Tests whether semantic field names in templates help the LLM
    understand log structure, or if raw examples are sufficient.
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    tmp_dir = os.path.join("eval", "experiments", "template-granularity", timestamp, "_tmp")

    for dataset in args.datasets:
        log_type = _log_type_for_dataset(dataset)
        query_file = QUERY_FILES[dataset]
        log_file = LOG_FILES[log_type]
        source = MANUAL_TEMPLATES[log_type]

        # Build modified template files from the manual source
        variants = {
            "named-placeholders": source,
            "generic-wildcards": _build_stripped_templates(
                source, os.path.join(tmp_dir, f"{log_type}_generic.json"), strip_names=True
            ),
            "examples-only": _build_examples_only_templates(
                source, os.path.join(tmp_dir, f"{log_type}_examples.json")
            ),
        }

        for variant_name, template_path in variants.items():
            tag = f"{dataset}_{variant_name}"
            out = _output_path("template-granularity", tag, timestamp)
            _run_eval(
                query_file, log_file,
                model=args.model,
                language=args.language,
                sample_size=args.sample_size,
                templates=template_path,
                max_workers=args.max_workers,
                output=out,
            )


def run_prompt_ablation(args) -> None:
    """Systematically remove one prompt component at a time.

    Five conditions, each removing one element to measure its contribution:
      - full:         templates + sample + retries (baseline)
      - no-templates: sample lines only, no template context
      - no-sample:    templates only, zero random sample lines
      - no-retries:   templates + sample, but max_retries=0 (first attempt only)
      - no-context:   no templates AND no sample (query + system prompt only)

    The F1 drop from baseline reveals how much each component matters.
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    for dataset in args.datasets:
        log_type = _log_type_for_dataset(dataset)
        query_file = QUERY_FILES[dataset]
        log_file = LOG_FILES[log_type]
        manual = MANUAL_TEMPLATES.get(log_type)

        conditions = {
            "full":         {"templates": manual, "sample_size": args.sample_size, "max_retries": DEFAULT_MAX_RETRIES},
            "no-templates": {"templates": None,   "sample_size": args.sample_size, "max_retries": DEFAULT_MAX_RETRIES},
            "no-sample":    {"templates": manual, "sample_size": 1,                "max_retries": DEFAULT_MAX_RETRIES},
            "no-retries":   {"templates": manual, "sample_size": args.sample_size, "max_retries": 0},
            "no-context":   {"templates": None,   "sample_size": 1,                "max_retries": DEFAULT_MAX_RETRIES},
        }

        for cond_name, cond in conditions.items():
            tag = f"{dataset}_{cond_name}"
            out = _output_path("prompt-ablation", tag, timestamp)
            _run_eval(
                query_file, log_file,
                model=args.model,
                language=args.language,
                sample_size=cond["sample_size"],
                templates=cond["templates"],
                max_retries=cond["max_retries"],
                max_workers=args.max_workers,
                output=out,
            )


def run_query_complexity(args) -> None:
    """Compare F1 on simple vs complex queries for each log type.

    Runs both the simple query set (single-field where/select filters)
    and the complex query set (multi-line stateful joins, aggregations)
    for each log type present in --datasets. Shows where LLM-generated
    code breaks down as query logic gets more involved.
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    # Deduplicate log types from the requested datasets
    log_types_requested = sorted({_log_type_for_dataset(ds) for ds in args.datasets})

    for log_type in log_types_requested:
        log_file = LOG_FILES[log_type]
        # Run both simple and complex query files for this log type
        pairs = {
            "simple": QUERY_FILES.get(f"{log_type}_simple"),
            "complex": QUERY_FILES.get(f"{log_type}_complex"),
        }

        for complexity, qf in pairs.items():
            if qf is None:
                continue
            tag = f"{log_type}_{complexity}"
            out = _output_path("query-complexity", tag, timestamp)
            _run_eval(
                qf, log_file,
                model=args.model,
                language=args.language,
                sample_size=args.sample_size,
                templates=MANUAL_TEMPLATES.get(log_type),
                max_workers=args.max_workers,
                output=out,
            )


def run_retry_analysis(args) -> None:
    """Measure the value of the retry mechanism.

    Runs each dataset twice:
      - no-retries:   max_retries=0, only the first LLM attempt is used
      - with-retries: max_retries=4 (default), failed code is fed back for correction

    Comparing the two reveals how often retries recover from errors
    (improving F1) vs just consuming extra tokens with no benefit.
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    for dataset in args.datasets:
        log_type = _log_type_for_dataset(dataset)
        query_file = QUERY_FILES[dataset]
        log_file = LOG_FILES[log_type]

        for retries, label in [(0, "no-retries"), (DEFAULT_MAX_RETRIES, "with-retries")]:
            tag = f"{dataset}_{label}"
            out = _output_path("retry-analysis", tag, timestamp)
            _run_eval(
                query_file, log_file,
                model=args.model,
                language=args.language,
                sample_size=args.sample_size,
                templates=MANUAL_TEMPLATES.get(log_type),
                max_retries=retries,
                max_workers=args.max_workers,
                output=out,
            )


def run_cross_log_transfer(args) -> None:
    """Test whether the LLM relies on templates or its own log knowledge.

    For each dataset, runs three+ conditions:
      - correct-templates:       templates matching the actual log type (baseline)
      - wrong-<type>-templates:  templates from a different log type (e.g. dhcp
                                 templates used to query audit logs)
      - no-templates:            no templates at all (sample lines only)

    If wrong templates hurt performance vs no templates, the LLM is being
    misled. If wrong templates don't hurt, the LLM ignores them.
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    all_log_types = sorted(MANUAL_TEMPLATES.keys())

    for dataset in args.datasets:
        log_type = _log_type_for_dataset(dataset)
        query_file = QUERY_FILES[dataset]
        log_file = LOG_FILES[log_type]

        # Baseline: correct templates
        tag = f"{dataset}_correct-templates"
        out = _output_path("cross-log-transfer", tag, timestamp)
        _run_eval(
            query_file, log_file,
            model=args.model,
            language=args.language,
            sample_size=args.sample_size,
            templates=MANUAL_TEMPLATES[log_type],
            max_workers=args.max_workers,
            output=out,
        )

        # Wrong templates from each other log type
        for other_type in all_log_types:
            if other_type == log_type:
                continue
            tag = f"{dataset}_wrong-{other_type}-templates"
            out = _output_path("cross-log-transfer", tag, timestamp)
            _run_eval(
                query_file, log_file,
                model=args.model,
                language=args.language,
                sample_size=args.sample_size,
                templates=MANUAL_TEMPLATES[other_type],
                max_workers=args.max_workers,
                output=out,
            )

        # Control: no templates at all
        tag = f"{dataset}_no-templates"
        out = _output_path("cross-log-transfer", tag, timestamp)
        _run_eval(
            query_file, log_file,
            model=args.model,
            language=args.language,
            sample_size=args.sample_size,
            max_workers=args.max_workers,
            output=out,
        )


def run_token_efficiency(args) -> None:
    """Map the accuracy-vs-cost Pareto frontier.

    Runs multiple conditions varying prompt size (template strategy x
    sample size). Each eval report includes total_input_tokens and F1,
    which can be plotted to find the cheapest prompt that still achieves
    good accuracy.

    Strategies x sample sizes:
      - matryoshka + [0, 25, 50, 100]
      - frequency  + [0, 25, 50, 100]
      - random-only + [0, 25, 50, 100]
      - none (0 sample, no templates; single data point)
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    sizes = args.sample_sizes or [0, 25, 50, 100]

    strategy_configs = {
        "matryoshka":  lambda ds, sz: {"templates": MANUAL_TEMPLATES[_log_type_for_dataset(ds)], "sample_size": sz},
        "frequency":   lambda _, sz: {"templater": "frequency", "sample_size": sz},
        "random-only": lambda _, sz: {"sample_size": sz},
        "none":        lambda _, __: {"sample_size": 1},
    }

    for dataset in args.datasets:
        log_type = _log_type_for_dataset(dataset)
        query_file = QUERY_FILES[dataset]
        log_file = LOG_FILES[log_type]

        for strategy_name, config_fn in strategy_configs.items():
            # "none" only needs one run (no sample, no templates)
            run_sizes = sizes if strategy_name != "none" else [0]
            for size in run_sizes:
                tag = f"{dataset}_{strategy_name}_s{size}"
                out = _output_path("token-efficiency", tag, timestamp)
                cfg = config_fn(dataset, size)
                _run_eval(
                    query_file, log_file,
                    model=args.model,
                    language=args.language,
                    sample_size=cfg.get("sample_size", size),
                    templates=cfg.get("templates"),
                    templater=cfg.get("templater"),
                    max_workers=args.max_workers,
                    output=out,
                )


def run_few_shot(args) -> None:
    """Compare zero-shot vs few-shot prompting with worked examples.

    Two conditions:
      - zero-shot: standard templates + sample (no worked examples)
      - few-shot:  same templates + sample, plus a dedicated WORKED EXAMPLES
                   section in the prompt showing query->code pairs

    Few-shot examples should be placed in few_shot_examples/<dataset>.json:
        [{"query": "Find lines with ...", "code": "import sys\\n..."}]

    If the file doesn't exist, only the zero-shot baseline is run and
    a message is printed explaining how to create the examples file.
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    examples_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "few_shot_examples")

    for dataset in args.datasets:
        log_type = _log_type_for_dataset(dataset)
        query_file = QUERY_FILES[dataset]
        log_file = LOG_FILES[log_type]

        # Zero-shot baseline (always runs)
        tag = f"{dataset}_zero-shot"
        out = _output_path("few-shot", tag, timestamp)
        _run_eval(
            query_file, log_file,
            model=args.model,
            language=args.language,
            sample_size=args.sample_size,
            templates=MANUAL_TEMPLATES.get(log_type),
            max_workers=args.max_workers,
            output=out,
        )

        # Few-shot: pass worked examples via --worked-examples
        examples_file = os.path.join(examples_dir, f"{dataset}.json")
        if not os.path.isfile(examples_file):
            print(f"\nNo few-shot examples found at: {examples_file}")
            print(f"Create it as: [{{'query': '...', 'code': '...'}}]")
            continue

        tag = f"{dataset}_few-shot"
        out = _output_path("few-shot", tag, timestamp)
        _run_eval(
            query_file, log_file,
            model=args.model,
            language=args.language,
            sample_size=args.sample_size,
            templates=MANUAL_TEMPLATES.get(log_type),
            max_workers=args.max_workers,
            output=out,
            extra_args=["--worked-examples", examples_file],
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

EXPERIMENTS = {
    # Core experiments
    "template-compare": run_template_compare,
    "model-compare": run_model_compare,
    "consistency": run_consistency,
    "sample-size": run_sample_size,
    "language-compare": run_language_compare,
    "human-baseline": run_human_baseline,
    "full-matrix": run_full_matrix,
    # Ablation & analysis experiments
    "template-granularity": run_template_granularity,
    "prompt-ablation": run_prompt_ablation,
    "query-complexity": run_query_complexity,
    "retry-analysis": run_retry_analysis,
    "cross-log-transfer": run_cross_log_transfer,
    "token-efficiency": run_token_efficiency,
    "few-shot": run_few_shot,
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run structured evaluation experiments.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--experiment",
        required=True,
        choices=sorted(EXPERIMENTS.keys()),
        help="Which experiment to run.",
    )
    parser.add_argument(
        "--datasets",
        nargs="+",
        default=DEFAULT_DATASETS,
        choices=sorted(QUERY_FILES.keys()),
        help=f"Datasets to evaluate (default: {' '.join(DEFAULT_DATASETS)})",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Model for single-model experiments (default: {DEFAULT_MODEL})")
    parser.add_argument("--models", nargs="+", help=f"Models for model-compare/full-matrix (default: {' '.join(MODELS)})")
    parser.add_argument("--language", default=DEFAULT_LANGUAGE, choices=LANGUAGES, help=f"Language (default: {DEFAULT_LANGUAGE})")
    parser.add_argument("--languages", nargs="+", choices=LANGUAGES, help="Languages for language-compare")
    parser.add_argument("--sample-size", type=int, default=DEFAULT_SAMPLE_SIZE, help=f"Sample size (default: {DEFAULT_SAMPLE_SIZE})")
    parser.add_argument("--sample-sizes", nargs="+", type=int, help=f"Sizes for sample-size experiment (default: {SAMPLE_SIZES})")
    parser.add_argument("--max-workers", type=int, default=DEFAULT_MAX_WORKERS, help=f"Max parallel workers (default: {DEFAULT_MAX_WORKERS})")
    parser.add_argument("--runs", type=int, default=DEFAULT_CONSISTENCY_RUNS, help=f"Runs per query for consistency (default: {DEFAULT_CONSISTENCY_RUNS})")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    experiment_fn = EXPERIMENTS[args.experiment]
    print(f"Starting experiment: {args.experiment}")
    print(f"Datasets: {args.datasets}")
    print(f"Timestamp: {datetime.now().strftime('%Y%m%d-%H%M%S')}")
    try:
        experiment_fn(args)
    except QuotaExhaustedError as exc:
        print(f"\nExperiment aborted: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"\nExperiment '{args.experiment}' complete.")


if __name__ == "__main__":
    main()
