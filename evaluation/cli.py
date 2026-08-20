"""CLI entry for evaluation of log filtering."""

import argparse
import copy
import os
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from itertools import cycle
from statistics import mean

from .io_utils import load_eval_json, resolve_log_file
from .metrics import compute_metrics
from .reporting import (
    write_consistency_report,
    write_dataset_consistency_report,
    write_diff_if_needed,
    write_report,
)
from .runner import prepare_query_runtime, run_query, run_query_consistency_once
from log_query.logging_utils import Logger
from log_query.paths import default_eval_dir, default_output_dir, log_parser_script


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate log filtering performance using log_parser.py"
    )
    parser.add_argument("eval_json", help="Path to evaluation JSON file (e.g., dhcp_queries.json)")
    parser.add_argument("log_file", help="Path to log file OR directory containing log files")
    parser.add_argument(
        "--model",
        default="gemini-2.5-flash",
        help="Gemini model ID to use (e.g., gemini-2.5-flash, gemini-2.5-flash-lite, gemini-3.1-pro-preview)",
    )
    parser.add_argument(
        "--language",
        choices=("bash", "python"),
        default="bash",
        help="Language for generated filters (default: bash)",
    )
    parser.add_argument("--sample-size", type=int, default=250, help="Sample size forwarded to log_parser.py")
    parser.add_argument("--max-retries", type=int, default=4, help="Retries forwarded to log_parser.py")
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate generated command/script on the sample before running",
    )
    parser.add_argument("--limit", type=int, help="Evaluate only the first N matching (where) queries")
    parser.add_argument("--verbose", action="store_true", help="Print progress to stdout for each query")
    parser.add_argument("--api-key", help="Override GEMINI_API_KEY (optional)")
    parser.add_argument("--vertex-ai", action="store_true", help="Use Vertex AI instead of standalone Gemini API")
    parser.add_argument(
        "--project",
        default=os.environ.get("VERTEX_PROJECT"),
        help="GCP project for Vertex AI (env: VERTEX_PROJECT)",
    )
    parser.add_argument(
        "--location",
        default="global",
        help="GCP location for Vertex AI (default: global)",
    )
    parser.add_argument("--templates", help="Path to log templates (optional)")
    parser.add_argument("--worked-examples", help="Path to JSON file with worked query->code examples for few-shot prompting")
    parser.add_argument("--sample-seed", type=int, help="Fixed RNG seed for sample line selection (deterministic across runs)")
    parser.add_argument(
        "--templater",
        choices=("drain3", "frequency"),
        help="Generate templates using a built-in templater (default: none)",
    )
    parser.add_argument("--templater-config", help="Path to drain3.ini config file (templater)")
    parser.add_argument(
        "--templater-message-separator",
        default=": ",
        help="Split each line on this separator before templating (default: ': ')",
    )
    parser.add_argument(
        "--templater-separator-mode",
        choices=("first", "last"),
        default="first",
        help="Use the first or last occurrence of the separator (default: first)",
    )
    parser.add_argument(
        "--templater-allow-missing-separator",
        action="store_true",
        help="Allow lines without the separator to be processed",
    )
    parser.add_argument(
        "--templater-max-lines",
        type=int,
        help="Only template the first N lines (useful for quick sampling)",
    )
    parser.add_argument("--output", help="Override output file name (optional)")
    parser.add_argument("--timeout", type=int, default=600, help="Per-query timeout seconds (default 600)")
    parser.add_argument("--max-workers", type=int, default=8, help="Max parallel workers (default 8)")
    parser.add_argument("--consistency", action="store_true", help="Run the same query multiple times to measure consistency")
    parser.add_argument("--query-id", help="Query id to select for consistency runs")
    parser.add_argument("--runs", type=int, default=5, help="Number of repeated consistency runs (default 5)")
    return parser.parse_args()


def _normalize_ground_truth(lines) -> list[str]:
    normalized = []
    for item in lines or []:
        if isinstance(item, list):
            parts = [str(part) for part in item if part is not None]
            if parts:
                normalized.append(" ".join(parts))
            continue
        if item is None:
            continue
        normalized.append(str(item))
    return normalized


def _normalize_output_format(output_format, query_type: str) -> tuple[list[str] | None, str | None]:
    if output_format is None:
        return None, None
    if query_type != "select":
        return None, f"ignored output_format for query_type={query_type or 'unknown'}"
    if not isinstance(output_format, list):
        return None, "invalid output_format: expected a list of field names"
    fields = []
    for item in output_format:
        if not isinstance(item, str) or not item.strip():
            return None, "invalid output_format: all fields must be non-empty strings"
        fields.append(item.strip())
    if not fields:
        return None, "invalid output_format: list is empty"
    return fields, None


def _normalize_output_data_type(
    output_data_type,
    query_type: str,
    output_format: list[str] | None,
) -> tuple[list[str] | None, str | None]:
    if output_data_type is None:
        return None, None
    if query_type != "select":
        return None, f"ignored output_data_type for query_type={query_type or 'unknown'}"
    if not isinstance(output_data_type, list):
        return None, "invalid output_data_type: expected a list of types"
    types = []
    for item in output_data_type:
        if not isinstance(item, str) or not item.strip():
            return None, "invalid output_data_type: all entries must be non-empty strings"
        types.append(item.strip())
    if not types:
        return None, "invalid output_data_type: list is empty"
    if output_format and len(types) != len(output_format):
        return None, "invalid output_data_type: length must match output_format"
    return types, None


def _derive_full_report_path(short_path: str) -> str:
    base, ext = os.path.splitext(short_path)
    if not ext:
        ext = ".txt"
    return f"{base}-full{ext}"


def _validate_args(args: argparse.Namespace) -> None:
    if args.templates and args.templater:
        print("Specify either --templates or --templater, not both.", file=sys.stderr)
        sys.exit(1)
    if args.templater_max_lines is not None and args.templater_max_lines <= 0:
        print("--templater-max-lines must be a positive integer.", file=sys.stderr)
        sys.exit(1)
    if args.max_workers <= 0:
        print("--max-workers must be a positive integer.", file=sys.stderr)
        sys.exit(1)
    if args.consistency and args.runs <= 0:
        print("--runs must be a positive integer.", file=sys.stderr)
        sys.exit(1)


def _collect_api_keys(args: argparse.Namespace) -> list[str]:
    """Gather all available API keys for round-robin rotation.

    Performs a liveness check against the requested model and excludes
    keys whose billing/quota is currently exhausted, so rotation does
    not waste retries on dead keys.

    For Vertex AI runs, key rotation is not used (Vertex uses GCP project
    credentials, not API keys), so this returns an empty list.
    """
    if getattr(args, "vertex_ai", False):
        return []
    from dotenv import load_dotenv
    load_dotenv()
    model = (getattr(args, "model", "") or "").lower()
    is_openai = model.startswith(("gpt-", "o1", "o3", "o4", "o5"))
    candidates: list[str] = []
    explicit = getattr(args, "api_key", None)
    if explicit:
        candidates.append(explicit)
    if is_openai:
        for env_name in ["OPENAI_API_KEY", "OPENAI_API_KEY_2", "OPENAI_API_KEY_3"]:
            val = os.environ.get(env_name)
            if val and val not in candidates:
                candidates.append(val)
        return candidates  # OpenAI: skip Gemini liveness check
    for env_name in ["GEMINI_API_KEY", "GEMINI_API_KEY_2", "GEMINI_API_KEY_3"]:
        val = os.environ.get(env_name)
        if val and val not in candidates:
            candidates.append(val)

    # Liveness check: filter out keys that are billing-exhausted for the model
    if not model or not candidates:
        return candidates
    try:
        from google import genai
    except Exception:
        return candidates

    live: list[str] = []
    for key in candidates:
        try:
            client = genai.Client(api_key=key)
            client.models.generate_content(model=model, contents="ping")
            live.append(key)
        except Exception as exc:
            msg = str(exc)
            if "spending cap" in msg or "billing" in msg.lower():
                continue  # exclude exhausted billing
            # Other errors (quota, transient): keep the key, retry logic will handle it
            live.append(key)
    return live or candidates


def _args_with_key(args: argparse.Namespace, key: str) -> argparse.Namespace:
    """Return a shallow copy of args with a specific api_key."""
    patched = copy.copy(args)
    patched.api_key = key
    return patched


def _task_from_entry(entry, idx: int) -> dict:
    qid = entry.get("__query_key") or entry.get("id") or f"row{idx}"
    nl_query = entry.get("natural_language", "")
    query_type = entry.get("query_type", "")
    gt = entry.get("ground_truth", {}) or {}
    must = _normalize_ground_truth(gt.get("must_contain", []) or [])
    may = _normalize_ground_truth(gt.get("may_contain", []) or [])
    output_format, output_format_error = _normalize_output_format(entry.get("output_format"), query_type)
    output_data_type, output_data_type_error = _normalize_output_data_type(
        entry.get("output_data_type"), query_type, output_format
    )
    return {
        "index": idx - 1,
        "id": qid,
        "query_type": query_type,
        "nl_query": nl_query,
        "must": must,
        "may": may,
        "output_format": output_format,
        "output_format_error": output_format_error,
        "output_data_type": output_data_type,
        "output_data_type_error": output_data_type_error,
    }


def _build_tasks(entries, limit: int | None = None) -> list[dict]:
    where_entries = [e for e in entries if e.get("query_type") in {"where", "select"}]
    if limit is not None:
        where_entries = where_entries[:limit]
    return [_task_from_entry(entry, idx) for idx, entry in enumerate(where_entries, start=1)]


def _select_task_by_id(tasks: list[dict], query_id: str) -> dict:
    for task in tasks:
        if task["id"] == query_id:
            return task
    raise KeyError(query_id)


def _result_from_pred_lines(task: dict, pred_lines: list[str]) -> dict:
    retry_count = None
    if pred_lines and pred_lines[0].startswith("__RETRIES__:"):
        try:
            retry_count = int(pred_lines[0].split(":", 1)[1].strip())
        except ValueError:
            retry_count = None
        pred_lines = pred_lines[1:]

    used_command = None
    if pred_lines and pred_lines[0].startswith("__COMMAND__:"):
        used_command = pred_lines[0].split(":", 1)[1].strip()
        pred_lines = pred_lines[1:]

    input_tokens = None
    output_tokens = None
    if pred_lines and pred_lines[0].startswith("__TOKENS__:"):
        try:
            parts = pred_lines[0].split(":", 1)[1].strip().split(",")
            input_tokens = int(parts[0])
            output_tokens = int(parts[1])
        except (ValueError, IndexError):
            pass
        pred_lines = pred_lines[1:]

    elapsed_seconds = None
    if pred_lines and pred_lines[0].startswith("__ELAPSED__:"):
        try:
            elapsed_seconds = float(pred_lines[0].split(":", 1)[1].strip())
        except (ValueError, IndexError):
            pass
        pred_lines = pred_lines[1:]

    if pred_lines and pred_lines[0].startswith("__EVAL_ERROR__:"):
        return {
            "id": task["id"],
            "query_type": task.get("query_type", ""),
            "query": task["nl_query"],
            "error": pred_lines[0],
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "tp": 0,
            "fp": 0,
            "fn": len(task["must"]),
            "may_precision": 0.0,
            "may_recall": 0.0,
            "may_f1": 0.0,
            "may_tp": 0,
            "may_fp": 0,
            "may_fn": len(task["may"]),
            "retries": retry_count,
            "output_format": task.get("output_format"),
            "output_format_error": task.get("output_format_error"),
            "output_data_type": task.get("output_data_type"),
            "output_data_type_error": task.get("output_data_type_error"),
            "command": used_command,
            "pred_lines": [],
            "returned": 0,
            "must": len(set(task["must"])),
            "may": len(set(task["may"])),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "elapsed_seconds": elapsed_seconds,
        }

    norm_pred_lines = [re.sub(r"\s+", " ", l).strip() for l in pred_lines if l and l.strip()]
    norm_must = [re.sub(r"\s+", " ", m).strip() for m in task["must"] if m and m.strip()]
    norm_may = [re.sub(r"\s+", " ", m).strip() for m in task["may"] if m and m.strip()]

    precision, recall, f1, tp, fp, fn = compute_metrics(norm_pred_lines, norm_must)
    may_precision, may_recall, may_f1, may_tp, may_fp, may_fn = compute_metrics(norm_pred_lines, norm_may)
    return {
        "id": task["id"],
        "query_type": task.get("query_type", ""),
        "query": task["nl_query"],
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "may_precision": may_precision,
        "may_recall": may_recall,
        "may_f1": may_f1,
        "may_tp": may_tp,
        "may_fp": may_fp,
        "may_fn": may_fn,
        "retries": retry_count,
        "returned": len(set(norm_pred_lines)),
        "must": len(set(norm_must)),
        "may": len(set(norm_may)),
        "output_format": task.get("output_format"),
        "output_format_error": task.get("output_format_error"),
        "output_data_type": task.get("output_data_type"),
        "output_data_type_error": task.get("output_data_type_error"),
        "command": used_command,
        "pred_lines": norm_pred_lines,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "elapsed_seconds": elapsed_seconds,
    }


def _build_pred_lines_from_consistency_run(run_result: dict) -> list[str]:
    if run_result.get("error"):
        return [f"__EVAL_ERROR__: {run_result['error']}"]
    pred_lines: list[str] = []
    if run_result.get("retry_count") is not None:
        pred_lines.append(f"__RETRIES__:{run_result['retry_count']}")
    if run_result.get("command"):
        pred_lines.append(f"__COMMAND__:{run_result['command']}")
    in_tok = run_result.get("input_tokens")
    out_tok = run_result.get("output_tokens")
    if in_tok is not None or out_tok is not None:
        pred_lines.append(f"__TOKENS__:{in_tok or 0},{out_tok or 0}")
    elapsed = run_result.get("elapsed_seconds")
    if elapsed is not None:
        pred_lines.append(f"__ELAPSED__:{elapsed}")
    pred_lines.extend(list(run_result.get("stdout_lines") or []))
    return pred_lines


def _summarize_consistency(run_results: list[dict], artifact_dir: str) -> dict:
    precision_values = [run["precision"] for run in run_results]
    recall_values = [run["recall"] for run in run_results]
    f1_values = [run["f1"] for run in run_results]
    may_f1_values = [run["may_f1"] for run in run_results]
    retry_values = [run.get("retries") or 0 for run in run_results]
    command_values = [run.get("command") for run in run_results if run.get("command")]
    output_keys = [tuple(run.get("pred_lines") or []) for run in run_results]
    output_counter = Counter(output_keys)
    return {
        "run_count": len(run_results),
        "successful_runs": sum(1 for run in run_results if not run.get("error")),
        "failed_runs": sum(1 for run in run_results if run.get("error")),
        "precision_mean": mean(precision_values) if precision_values else 0.0,
        "precision_min": min(precision_values) if precision_values else 0.0,
        "precision_max": max(precision_values) if precision_values else 0.0,
        "recall_mean": mean(recall_values) if recall_values else 0.0,
        "recall_min": min(recall_values) if recall_values else 0.0,
        "recall_max": max(recall_values) if recall_values else 0.0,
        "f1_mean": mean(f1_values) if f1_values else 0.0,
        "f1_min": min(f1_values) if f1_values else 0.0,
        "f1_max": max(f1_values) if f1_values else 0.0,
        "may_f1_mean": mean(may_f1_values) if may_f1_values else 0.0,
        "may_f1_min": min(may_f1_values) if may_f1_values else 0.0,
        "may_f1_max": max(may_f1_values) if may_f1_values else 0.0,
        "retries_total": sum(retry_values),
        "retries_avg": mean(retry_values) if retry_values else 0.0,
        "retries_max": max(retry_values) if retry_values else 0,
        "unique_commands": len(set(command_values)),
        "unique_outputs": len(set(output_keys)),
        "most_common_output_frequency": output_counter.most_common(1)[0][1] if output_counter else 0,
        "artifact_dir": artifact_dir,
    }


def _run_consistency_task(
    args,
    resolved_log: str,
    task: dict,
    artifact_dir: str,
    timestamp: str,
    show_run_progress: bool = True,
) -> tuple[list[dict], dict]:
    os.makedirs(artifact_dir, exist_ok=True)
    runtime_log = Logger("ERROR")
    _prepared_args, runtime = prepare_query_runtime(
        task["nl_query"],
        resolved_log,
        args,
        task.get("output_format"),
        task.get("output_data_type"),
        runtime_log,
    )

    api_keys = _collect_api_keys(args)
    key_cycle = cycle(api_keys) if api_keys else None

    run_results: list[dict | None] = [None] * args.runs
    max_workers = min(args.max_workers if args.max_workers > 0 else 1, args.runs)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_index = {}
        for run_index in range(1, args.runs + 1):
            run_stamp = f"{timestamp}-run{run_index:03d}"
            run_args = _args_with_key(args, next(key_cycle)) if key_cycle else args
            future = executor.submit(
                run_query_consistency_once,
                task["nl_query"],
                resolved_log,
                run_args,
                runtime,
                task.get("output_format"),
                task.get("output_data_type"),
                artifact_dir,
                run_stamp,
                f"Run {run_index}/{args.runs}",
                Logger("ERROR"),
            )
            future_to_index[future] = run_index

        completed = 0
        for future in as_completed(future_to_index):
            run_index = future_to_index[future]
            try:
                raw_run = future.result()
            except Exception as exc:
                raw_run = {
                    "status": "exception",
                    "exit_code": 1,
                    "error": str(exc),
                    "stdout_lines": [],
                    "stderr": str(exc),
                    "output_file": None,
                    "command_file": None,
                    "command": None,
                    "retry_count": None,
                }

            result_entry = _result_from_pred_lines(task, _build_pred_lines_from_consistency_run(raw_run))
            result_entry["run_index"] = run_index
            result_entry["status"] = raw_run.get("status", "unknown")
            result_entry["stderr"] = raw_run.get("stderr", "") or ""
            result_entry["output_file"] = raw_run.get("output_file")
            result_entry["command_file"] = raw_run.get("command_file")
            run_results[run_index - 1] = result_entry

            completed += 1
            if show_run_progress:
                if args.verbose:
                    print(f"[{completed}/{args.runs}] Completed consistency run {run_index} for query ID={task['id']}", flush=True)
                else:
                    print(f"\rCompleted {completed}/{args.runs} consistency runs", end="", flush=True)

    finalized_results = [run for run in run_results if run is not None]
    if show_run_progress and args.runs and not args.verbose:
        print("", flush=True)
    summary = _summarize_consistency(finalized_results, artifact_dir)
    return finalized_results, summary


def _run_single_consistency_evaluation(args, resolved_log: str, tasks: list[dict]) -> None:
    try:
        task = _select_task_by_id(tasks, args.query_id)
    except KeyError:
        print(f"Query id not found in evaluation file: {args.query_id}", file=sys.stderr)
        sys.exit(1)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    eval_dir = default_eval_dir()
    os.makedirs(eval_dir, exist_ok=True)
    safe_id = re.sub(r"[^A-Za-z0-9_.-]", "_", str(task["id"]))
    short_out_file = args.output or os.path.join(eval_dir, f"consistency-{safe_id}-{timestamp}.txt")
    full_out_file = _derive_full_report_path(short_out_file)
    artifact_dir = os.path.join(default_output_dir(), f"consistency-{safe_id}-{timestamp}")

    finalized_results, summary = _run_consistency_task(args, resolved_log, task, artifact_dir, timestamp, show_run_progress=True)
    write_consistency_report(
        short_out_file,
        timestamp,
        args,
        resolved_log,
        task,
        finalized_results,
        summary,
        include_output=False,
    )
    write_consistency_report(
        full_out_file,
        timestamp,
        args,
        resolved_log,
        task,
        finalized_results,
        summary,
        include_output=True,
    )
    print(
        "Consistency evaluation complete. Short report: {} | Full report: {}".format(
            short_out_file, full_out_file
        )
    )


def _run_dataset_consistency_evaluation(args, resolved_log: str, tasks: list[dict]) -> None:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    eval_dir = default_eval_dir()
    os.makedirs(eval_dir, exist_ok=True)
    short_out_file = args.output or os.path.join(eval_dir, f"consistency-dataset-{timestamp}.txt")
    full_out_file = _derive_full_report_path(short_out_file)
    artifact_root = os.path.join(default_output_dir(), f"consistency-dataset-{timestamp}")
    os.makedirs(artifact_root, exist_ok=True)

    _pre_template_if_needed(args, resolved_log)

    dataset_results = []
    total = len(tasks)
    for idx, task in enumerate(tasks, start=1):
        safe_id = re.sub(r"[^A-Za-z0-9_.-]", "_", str(task["id"]))
        artifact_dir = os.path.join(artifact_root, safe_id)
        finalized_results, summary = _run_consistency_task(
            args,
            resolved_log,
            task,
            artifact_dir,
            f"{timestamp}-{safe_id}",
            show_run_progress=False,
        )
        dataset_results.append({"task": task, "runs": finalized_results, "summary": summary})
        if args.verbose:
            print(f"[{idx}/{total}] Completed consistency query ID={task['id']}: {task['nl_query']}", flush=True)
        else:
            print(f"\rCompleted {idx}/{total} consistency queries", end="", flush=True)

    if total and not args.verbose:
        print("", flush=True)

    write_dataset_consistency_report(
        short_out_file,
        timestamp,
        args,
        resolved_log,
        dataset_results,
        include_output=False,
    )
    write_dataset_consistency_report(
        full_out_file,
        timestamp,
        args,
        resolved_log,
        dataset_results,
        include_output=True,
    )
    print(
        "Dataset consistency evaluation complete. Short report: {} | Full report: {}".format(
            short_out_file, full_out_file
        )
    )


def _pre_template_if_needed(args, resolved_log: str) -> None:
    """Run the templater once and replace --templater with --templates on args."""
    if not getattr(args, "templater", None):
        return
    if args.templater == "frequency":
        from log_query.templaters import frequency_templater as _templater_mod
    else:
        from log_query.templaters import drain3_templater as _templater_mod

    template_path, _payload = _templater_mod.run_templater(
        resolved_log,
        max_lines=getattr(args, "templater_max_lines", None),
        config_path=getattr(args, "templater_config", None),
        message_separator=getattr(args, "templater_message_separator", None),
        require_separator=not getattr(args, "templater_allow_missing_separator", False),
        separator_mode=getattr(args, "templater_separator_mode", "first"),
    )
    args.templates = template_path
    args.templater = None


def _run_standard_evaluation(args, resolved_log: str, tasks: list[dict]) -> None:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    eval_dir = default_eval_dir()
    os.makedirs(eval_dir, exist_ok=True)
    short_out_file = args.output or os.path.join(eval_dir, f"eval-{timestamp}.txt")
    full_out_file = _derive_full_report_path(short_out_file)
    repo_script = log_parser_script()

    _pre_template_if_needed(args, resolved_log)

    results = [None] * len(tasks)
    macro_p = macro_r = macro_f1 = 0.0
    macro_may_p = macro_may_r = macro_may_f1 = 0.0
    evaluated = 0
    total_retries = 0
    retries_counted = 0

    total = len(tasks)
    completed = 0
    max_workers = args.max_workers if args.max_workers and args.max_workers > 0 else 1
    max_workers = min(max_workers, total) if total else 1
    api_keys = _collect_api_keys(args)
    key_cycle = cycle(api_keys) if api_keys else None

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_task = {}
        for task in tasks:
            task_args = _args_with_key(args, next(key_cycle)) if key_cycle else args
            future = executor.submit(
                run_query,
                task["nl_query"],
                resolved_log,
                task_args,
                repo_script,
                task.get("output_format"),
                task.get("output_data_type"),
            )
            future_to_task[future] = task
        for future in as_completed(future_to_task):
            task = future_to_task[future]
            try:
                pred_lines = future.result()
            except Exception as exc:
                pred_lines = [f"__EVAL_ERROR__: {exc}"]

            completed += 1
            if args.verbose:
                print(f"[{completed}/{total}] Completed query ID={task['id']}: {task['nl_query']}", flush=True)
            else:
                print(f"\rCompleted {completed}/{total} prompts", end="", flush=True)

            results_entry = _result_from_pred_lines(task, pred_lines)
            results[task["index"]] = results_entry

            if "error" not in results_entry:
                try:
                    write_diff_if_needed(
                        eval_dir,
                        task["id"],
                        task["nl_query"],
                        results_entry["precision"],
                        results_entry["recall"],
                        results_entry["f1"],
                        results_entry["tp"],
                        results_entry["fp"],
                        results_entry["fn"],
                        results_entry["may_precision"],
                        results_entry["may_recall"],
                        results_entry["may_f1"],
                        results_entry["pred_lines"],
                        task["must"],
                        task["may"],
                        task.get("output_format"),
                        task.get("output_data_type"),
                        results_entry.get("command"),
                        results_entry,
                    )
                except Exception as exc:
                    results_entry["diff_file_error"] = str(exc)

            macro_p += results_entry["precision"]
            macro_r += results_entry["recall"]
            macro_f1 += results_entry["f1"]
            macro_may_p += results_entry["may_precision"]
            macro_may_r += results_entry["may_recall"]
            macro_may_f1 += results_entry["may_f1"]
            evaluated += 1
            if results_entry.get("retries") is not None:
                total_retries += results_entry["retries"]
                retries_counted += 1

    if total and not args.verbose:
        print("", flush=True)

    macro_p = macro_p / evaluated if evaluated else 0.0
    macro_r = macro_r / evaluated if evaluated else 0.0
    macro_f1 = macro_f1 / evaluated if evaluated else 0.0
    macro_may_p = macro_may_p / evaluated if evaluated else 0.0
    macro_may_r = macro_may_r / evaluated if evaluated else 0.0
    macro_may_f1 = macro_may_f1 / evaluated if evaluated else 0.0
    avg_retries = (total_retries / retries_counted) if retries_counted else 0.0

    write_report(
        short_out_file,
        timestamp,
        args,
        resolved_log,
        evaluated,
        results,
        macro_p,
        macro_r,
        macro_f1,
        macro_may_p,
        macro_may_r,
        macro_may_f1,
        total_retries,
        avg_retries,
        include_code=False,
    )
    write_report(
        full_out_file,
        timestamp,
        args,
        resolved_log,
        evaluated,
        results,
        macro_p,
        macro_r,
        macro_f1,
        macro_may_p,
        macro_may_r,
        macro_may_f1,
        total_retries,
        avg_retries,
        include_code=True,
    )
    print(
        "Evaluation complete. Short report: {} | Full report: {}".format(
            short_out_file, full_out_file
        )
    )


def _run_consistency_evaluation(args, resolved_log: str, tasks: list[dict]) -> None:
    if args.query_id:
        _run_single_consistency_evaluation(args, resolved_log, tasks)
    else:
        _run_dataset_consistency_evaluation(args, resolved_log, tasks)


def main() -> None:
    args = _parse_args()
    _validate_args(args)

    repo_script = log_parser_script()
    if not os.path.isfile(repo_script):
        print(f"log_parser.py not found at {repo_script}", file=sys.stderr)
        sys.exit(2)

    try:
        resolved_log = resolve_log_file(args.log_file)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)

    try:
        entries = load_eval_json(args.eval_json)
    except Exception as exc:
        print(f"Failed to load evaluation JSON: {exc}", file=sys.stderr)
        sys.exit(2)

    tasks = _build_tasks(entries, limit=args.limit)
    if not tasks:
        print("No 'where' or 'select' queries found to evaluate.")
        sys.exit(0)

    if args.consistency:
        _run_consistency_evaluation(args, resolved_log, tasks)
    else:
        _run_standard_evaluation(args, resolved_log, tasks)


if __name__ == "__main__":
    main()
