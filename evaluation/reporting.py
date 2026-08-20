"""Report and diff file writing for evaluations."""

import os
import re
from datetime import datetime
from typing import Dict, List, Optional


def write_diff_if_needed(
    eval_dir: str,
    entry_id: str,
    nl_query: str,
    precision: float,
    recall: float,
    f1: float,
    tp: int,
    fp: int,
    fn: int,
    may_precision: float,
    may_recall: float,
    may_f1: float,
    norm_pred_lines: List[str],
    norm_must: List[str],
    norm_may: List[str],
    requested_output_format: Optional[List[str]],
    requested_output_data_type: Optional[List[str]],
    used_command: Optional[str],
    results_entry: Dict,
) -> None:
    if precision == 1.0 and recall == 1.0 and may_precision == 1.0 and may_recall == 1.0:
        return

    safe_id = re.sub(r"[^A-Za-z0-9_.-]", "_", str(entry_id))
    q_ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    per_query_dir = os.path.join(eval_dir, safe_id)
    os.makedirs(per_query_dir, exist_ok=True)
    diff_name = os.path.join(per_query_dir, f"eval-{safe_id}-{q_ts}.txt")

    pred_set = set(norm_pred_lines)
    must_set = set(norm_must)
    may_set = set(norm_may)
    false_neg = sorted(list(must_set - pred_set))
    false_pos = sorted(list(pred_set - must_set))
    may_false_neg = sorted(list(may_set - pred_set))
    may_false_pos = sorted(list(pred_set - may_set))
    with open(diff_name, "w", encoding="utf-8") as df:
        df.write(f"# Eval diff for ID: {entry_id}\n")
        df.write(f"# Generated: {q_ts}\n")
        if used_command:
            df.write(f"# Command used: {used_command}\n")
        if requested_output_format:
            df.write(
                "# Requested output format: {}\n".format(
                    ",".join(str(item) for item in requested_output_format)
                )
            )
        if requested_output_data_type:
            df.write(
                "# Requested output data type: {}\n".format(
                    ",".join(str(item) for item in requested_output_data_type)
                )
            )
        df.write(f"# Query: {nl_query}\n\n")
        df.write(
            f"# Metrics: precision={precision:.4f} recall={recall:.4f} f1={f1:.4f} TP={tp} FP={fp} FN={fn}\n\n"
        )
        df.write(
            f"# May metrics: precision={may_precision:.4f} recall={may_recall:.4f} f1={may_f1:.4f}\n\n"
        )
        df.write("# --- GROUND TRUTH (must_contain) ---\n")
        for item in sorted(must_set):
            df.write(item + "\n")
        df.write("\n# --- GROUND TRUTH (may_contain) ---\n")
        for item in sorted(may_set):
            df.write(item + "\n")
        df.write("\n# --- PREDICTED (returned lines) ---\n")
        for item in sorted(pred_set):
            df.write(item + "\n")
        df.write("\n# --- MISSING (false negatives) ---\n")
        if false_neg:
            for item in false_neg:
                df.write(item + "\n")
        else:
            df.write("(none)\n")
        df.write("\n# --- EXTRA (false positives) ---\n")
        if false_pos:
            for item in false_pos:
                df.write(item + "\n")
        else:
            df.write("(none)\n")
        df.write("\n# --- MAY MISSING (false negatives) ---\n")
        if may_false_neg:
            for item in may_false_neg:
                df.write(item + "\n")
        else:
            df.write("(none)\n")
        df.write("\n# --- MAY EXTRA (false positives) ---\n")
        if may_false_pos:
            for item in may_false_pos:
                df.write(item + "\n")
        else:
            df.write("(none)\n")

    results_entry["diff_file"] = diff_name


def write_report(
    out_file: str,
    timestamp: str,
    args,
    resolved_log: str,
    evaluated: int,
    results: List[Dict],
    macro_p: float,
    macro_r: float,
    macro_f1: float,
    macro_may_p: float,
    macro_may_r: float,
    macro_may_f1: float,
    total_retries: int,
    avg_retries: float,
    include_code: bool = True,
) -> None:
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(f"# Evaluation report generated {timestamp}\n")
        f.write(f"# Source JSON: {args.eval_json}\n")
        f.write(f"# Log file input: {args.log_file}\n")
        f.write(f"# Log file resolved: {resolved_log}\n")
        f.write(f"# Model: {args.model}\n")
        if getattr(args, "language", "bash") != "bash":
            f.write(f"# Language: {args.language}\n")
        f.write(f"# Sample size: {args.sample_size}\n")
        f.write(f"# Max retries: {args.max_retries}\n")
        f.write(f"# Timeout: {args.timeout}\n")
        if args.templates:
            f.write(f"# Templates: {args.templates}\n")
        f.write(f"# Queries evaluated: {evaluated}\n\n")

        for result in results:
            query_type = result.get("query_type") or "unknown"
            query = result.get("query") or ""
            output_format = result.get("output_format") or []
            output_format_error = result.get("output_format_error")
            output_data_type = result.get("output_data_type") or []
            output_data_type_error = result.get("output_data_type_error")
            if query:
                f.write(f"ID: {result['id']} | type: {query_type} | query: {query}\n")
            else:
                f.write(f"ID: {result['id']} | type: {query_type}\n")
            if output_format:
                f.write(f"  requested output format={','.join(str(item) for item in output_format)}\n")
            if output_format_error:
                f.write(f"  output_format_note={output_format_error}\n")
            if output_data_type:
                f.write(f"  requested output data type={','.join(str(item) for item in output_data_type)}\n")
            if output_data_type_error:
                f.write(f"  output_data_type_note={output_data_type_error}\n")
            if "error" in result:
                f.write(f"  ERROR: {result['error']}\n")
                f.write(f"  precision=0.0 recall=0.0 f1=0.0 TP=0 FP=0 FN={result['fn']}\n")
                f.write(
                    "  may_precision=0.0 may_recall=0.0 may_f1=0.0 may_TP=0 may_FP=0 may_FN={}\n".format(
                        result["may_fn"]
                    )
                )
                retries_val = result.get("retries")
                retry_text = "unknown" if retries_val is None else str(retries_val)
                f.write(f"  retries={retry_text}\n")
                if include_code:
                    in_tok = result.get("input_tokens")
                    out_tok = result.get("output_tokens")
                    if in_tok is not None or out_tok is not None:
                        f.write(f"  input_tokens={in_tok or 0} output_tokens={out_tok or 0}\n")
                elapsed = result.get("elapsed_seconds")
                if elapsed is not None:
                    f.write(f"  elapsed_seconds={elapsed}\n")
                f.write("\n")
                continue
            if include_code and "command" in result and result["command"]:
                f.write(f"  command: {result['command']}\n")

            f.write(
                "  precision={:.4f} recall={:.4f} f1={:.4f} TP={} FP={} FN={} returned={} must={}\n".format(
                    result["precision"],
                    result["recall"],
                    result["f1"],
                    result["tp"],
                    result["fp"],
                    result["fn"],
                    result["returned"],
                    result["must"],
                )
            )
            f.write(
                "  may_precision={:.4f} may_recall={:.4f} may_f1={:.4f} may_TP={} may_FP={} may_FN={} may={}\n".format(
                    result["may_precision"],
                    result["may_recall"],
                    result["may_f1"],
                    result["may_tp"],
                    result["may_fp"],
                    result["may_fn"],
                    result["may"],
                )
            )
            retries_val = result.get("retries")
            retry_text = "unknown" if retries_val is None else str(retries_val)
            f.write(f"  retries={retry_text}\n")
            if include_code:
                in_tok = result.get("input_tokens")
                out_tok = result.get("output_tokens")
                if in_tok is not None or out_tok is not None:
                    f.write(f"  input_tokens={in_tok or 0} output_tokens={out_tok or 0}\n")
            elapsed = result.get("elapsed_seconds")
            if elapsed is not None:
                f.write(f"  elapsed_seconds={elapsed}\n")
            f.write("\n")

        total_input_tokens = sum(r.get("input_tokens") or 0 for r in results if r)
        total_output_tokens = sum(r.get("output_tokens") or 0 for r in results if r)
        elapsed_values = [r.get("elapsed_seconds") for r in results if r and r.get("elapsed_seconds") is not None]
        total_elapsed = sum(elapsed_values) if elapsed_values else 0.0
        avg_elapsed = (total_elapsed / len(elapsed_values)) if elapsed_values else 0.0

        f.write("# Macro Averages (where/select queries)\n")
        f.write("# precision={:.4f} recall={:.4f} f1={:.4f}\n".format(macro_p, macro_r, macro_f1))
        f.write("# may_precision={:.4f} may_recall={:.4f} may_f1={:.4f}\n".format(macro_may_p, macro_may_r, macro_may_f1))
        f.write("# retries_total={} retries_avg={:.2f}\n".format(total_retries, avg_retries))
        f.write("# total_input_tokens={} total_output_tokens={}\n".format(total_input_tokens, total_output_tokens))
        f.write("# total_elapsed={:.2f}s avg_elapsed={:.2f}s\n".format(total_elapsed, avg_elapsed))

        scored = []
        for result in results:
            if result is None:
                continue
            f1 = result.get("f1")
            if f1 is None:
                f1 = 0.0
            scored.append((f1, result))
        scored.sort(key=lambda item: item[0])
        worst = scored[:5]
        f.write("# Worst 5 queries by f1\n")
        for idx, (f1, result) in enumerate(worst, start=1):
            qid = result.get("id", "unknown")
            qtype = result.get("query_type", "unknown")
            query = result.get("query", "")
            error = result.get("error")
            if error:
                f.write(f"# {idx}. {qid} | type: {qtype} | f1=0.0000 | error: {error}\n")
            elif query:
                f.write(f"# {idx}. {qid} | type: {qtype} | f1={f1:.4f} | query: {query}\n")
            else:
                f.write(f"# {idx}. {qid} | type: {qtype} | f1={f1:.4f}\n")


def write_consistency_report(
    out_file: str,
    timestamp: str,
    args,
    resolved_log: str,
    task: Dict,
    run_results: List[Dict],
    summary: Dict,
    include_output: bool = True,
) -> None:
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(f"# Consistency report generated {timestamp}\n")
        f.write(f"# Source JSON: {args.eval_json}\n")
        f.write(f"# Query ID: {task['id']}\n")
        f.write(f"# Query type: {task.get('query_type', 'unknown')}\n")
        f.write(f"# Query: {task.get('nl_query', '')}\n")
        f.write(f"# Log file input: {args.log_file}\n")
        f.write(f"# Log file resolved: {resolved_log}\n")
        f.write(f"# Model: {args.model}\n")
        f.write(f"# Runs: {summary['run_count']}\n")
        if getattr(args, "language", "bash") != "bash":
            f.write(f"# Language: {args.language}\n")
        f.write(f"# Sample size: {args.sample_size}\n")
        f.write(f"# Max retries: {args.max_retries}\n")
        f.write(f"# Timeout: {args.timeout}\n")
        if args.templates:
            f.write(f"# Templates: {args.templates}\n")
        if summary.get("artifact_dir"):
            f.write(f"# Artifact directory: {summary['artifact_dir']}\n")
        f.write("\n")

        if task.get("output_format"):
            f.write(
                "# Requested output format: {}\n".format(
                    ",".join(str(item) for item in task["output_format"])
                )
            )
        if task.get("output_data_type"):
            f.write(
                "# Requested output data type: {}\n".format(
                    ",".join(str(item) for item in task["output_data_type"])
                )
            )
        if task.get("output_format_error"):
            f.write(f"# output_format_note={task['output_format_error']}\n")
        if task.get("output_data_type_error"):
            f.write(f"# output_data_type_note={task['output_data_type_error']}\n")
        f.write("\n")

        f.write("# Aggregate Summary\n")
        f.write(f"# successful_runs={summary['successful_runs']} failed_runs={summary['failed_runs']}\n")
        f.write(
            "# precision_mean={:.4f} precision_min={:.4f} precision_max={:.4f}\n".format(
                summary["precision_mean"], summary["precision_min"], summary["precision_max"]
            )
        )
        f.write(
            "# recall_mean={:.4f} recall_min={:.4f} recall_max={:.4f}\n".format(
                summary["recall_mean"], summary["recall_min"], summary["recall_max"]
            )
        )
        f.write(
            "# f1_mean={:.4f} f1_min={:.4f} f1_max={:.4f}\n".format(
                summary["f1_mean"], summary["f1_min"], summary["f1_max"]
            )
        )
        f.write(
            "# may_f1_mean={:.4f} may_f1_min={:.4f} may_f1_max={:.4f}\n".format(
                summary["may_f1_mean"], summary["may_f1_min"], summary["may_f1_max"]
            )
        )
        f.write(
            "# retries_total={} retries_avg={:.2f} retries_max={}\n".format(
                summary["retries_total"], summary["retries_avg"], summary["retries_max"]
            )
        )
        f.write(
            "# unique_commands={} unique_outputs={} most_common_output_frequency={}\n\n".format(
                summary["unique_commands"],
                summary["unique_outputs"],
                summary["most_common_output_frequency"],
            )
        )

        for run in run_results:
            f.write(f"Run {run['run_index']}/{summary['run_count']}\n")
            f.write(f"  status={run.get('status', 'unknown')}\n")
            if run.get("error"):
                f.write(f"  ERROR: {run['error']}\n")
            f.write(
                "  precision={:.4f} recall={:.4f} f1={:.4f} TP={} FP={} FN={} returned={} must={}\n".format(
                    run["precision"],
                    run["recall"],
                    run["f1"],
                    run["tp"],
                    run["fp"],
                    run["fn"],
                    run["returned"],
                    run["must"],
                )
            )
            f.write(
                "  may_precision={:.4f} may_recall={:.4f} may_f1={:.4f} may_TP={} may_FP={} may_FN={} may={}\n".format(
                    run["may_precision"],
                    run["may_recall"],
                    run["may_f1"],
                    run["may_tp"],
                    run["may_fp"],
                    run["may_fn"],
                    run["may"],
                )
            )
            retries_val = run.get("retries")
            retry_text = "unknown" if retries_val is None else str(retries_val)
            f.write(f"  retries={retry_text}\n")
            if include_output:
                in_tok = run.get("input_tokens")
                out_tok = run.get("output_tokens")
                if in_tok is not None or out_tok is not None:
                    f.write(f"  input_tokens={in_tok or 0} output_tokens={out_tok or 0}\n")
            elapsed = run.get("elapsed_seconds")
            if elapsed is not None:
                f.write(f"  elapsed_seconds={elapsed}\n")
            if run.get("output_file"):
                f.write(f"  output_file={run['output_file']}\n")
            if include_output and run.get("command_file"):
                f.write(f"  command_file={run['command_file']}\n")
            if include_output and run.get("command"):
                f.write(f"  command: {run['command']}\n")
            if include_output and run.get("stderr"):
                f.write(f"  stderr: {run['stderr']}\n")
            if include_output:
                f.write("  output_lines:\n")
                output_lines = run.get("pred_lines") or []
                if output_lines:
                    for line in output_lines:
                        f.write(f"    {line}\n")
                else:
                    f.write("    (none)\n")
            f.write("\n")



def write_dataset_consistency_report(
    out_file: str,
    timestamp: str,
    args,
    resolved_log: str,
    dataset_results: List[Dict],
    include_output: bool = False,
) -> None:
    f1_means = [item["summary"].get("f1_mean", 0.0) for item in dataset_results]
    may_f1_means = [item["summary"].get("may_f1_mean", 0.0) for item in dataset_results]
    total_retries = sum(item["summary"].get("retries_total", 0) for item in dataset_results)
    total_queries = len(dataset_results)
    avg_f1 = (sum(f1_means) / total_queries) if total_queries else 0.0
    avg_may_f1 = (sum(may_f1_means) / total_queries) if total_queries else 0.0

    with open(out_file, "w", encoding="utf-8") as f:
        f.write(f"# Dataset consistency report generated {timestamp}\n")
        f.write(f"# Source JSON: {args.eval_json}\n")
        f.write(f"# Log file input: {args.log_file}\n")
        f.write(f"# Log file resolved: {resolved_log}\n")
        f.write(f"# Model: {args.model}\n")
        if getattr(args, "language", "bash") != "bash":
            f.write(f"# Language: {args.language}\n")
        f.write(f"# Runs per query: {args.runs}\n")
        f.write(f"# Queries evaluated: {total_queries}\n")
        f.write(f"# Sample size: {args.sample_size}\n")
        f.write(f"# Max retries: {args.max_retries}\n")
        f.write(f"# Timeout: {args.timeout}\n")
        if args.templates:
            f.write(f"# Templates: {args.templates}\n")
        f.write("\n")
        f.write(f"# average_query_f1_mean={avg_f1:.4f}\n")
        f.write(f"# average_query_may_f1_mean={avg_may_f1:.4f}\n")
        f.write(f"# retries_total={total_retries}\n")

        ranked = sorted(dataset_results, key=lambda item: item["summary"].get("f1_mean", 0.0))
        f.write("# Worst 5 queries by f1_mean\n")
        for idx, item in enumerate(ranked[:5], start=1):
            task = item["task"]
            summary = item["summary"]
            f.write(
                f"# {idx}. {task['id']} | type: {task.get('query_type', 'unknown')} | "
                f"f1_mean={summary.get('f1_mean', 0.0):.4f} | query: {task.get('nl_query', '')}\n"
            )
        f.write("\n")

        for item in dataset_results:
            task = item["task"]
            summary = item["summary"]
            runs = item["runs"]
            f.write(f"ID: {task['id']} | type: {task.get('query_type', 'unknown')} | query: {task.get('nl_query', '')}\n")
            if task.get("output_format"):
                f.write(f"  requested output format={','.join(str(x) for x in task['output_format'])}\n")
            if task.get("output_data_type"):
                f.write(f"  requested output data type={','.join(str(x) for x in task['output_data_type'])}\n")
            if task.get("output_format_error"):
                f.write(f"  output_format_note={task['output_format_error']}\n")
            if task.get("output_data_type_error"):
                f.write(f"  output_data_type_note={task['output_data_type_error']}\n")
            f.write(
                "  successful_runs={} failed_runs={} unique_commands={} unique_outputs={}\n".format(
                    summary.get("successful_runs", 0),
                    summary.get("failed_runs", 0),
                    summary.get("unique_commands", 0),
                    summary.get("unique_outputs", 0),
                )
            )
            f.write(
                "  precision_mean={:.4f} recall_mean={:.4f} f1_mean={:.4f} f1_min={:.4f} f1_max={:.4f}\n".format(
                    summary.get("precision_mean", 0.0),
                    summary.get("recall_mean", 0.0),
                    summary.get("f1_mean", 0.0),
                    summary.get("f1_min", 0.0),
                    summary.get("f1_max", 0.0),
                )
            )
            f.write(
                "  may_f1_mean={:.4f} retries_total={} retries_avg={:.2f} retries_max={}\n".format(
                    summary.get("may_f1_mean", 0.0),
                    summary.get("retries_total", 0),
                    summary.get("retries_avg", 0.0),
                    summary.get("retries_max", 0),
                )
            )
            if summary.get("artifact_dir"):
                f.write(f"  artifact_dir={summary['artifact_dir']}\n")
            if include_output:
                for run in runs:
                    f.write(f"  Run {run['run_index']}/{summary.get('run_count', len(runs))}\n")
                    f.write(f"    status={run.get('status', 'unknown')}\n")
                    if run.get("error"):
                        f.write(f"    ERROR: {run['error']}\n")
                    f.write(
                        "    precision={:.4f} recall={:.4f} f1={:.4f} TP={} FP={} FN={}\n".format(
                            run.get("precision", 0.0),
                            run.get("recall", 0.0),
                            run.get("f1", 0.0),
                            run.get("tp", 0),
                            run.get("fp", 0),
                            run.get("fn", 0),
                        )
                    )
                    in_tok = run.get("input_tokens")
                    out_tok = run.get("output_tokens")
                    if in_tok is not None or out_tok is not None:
                        f.write(f"    input_tokens={in_tok or 0} output_tokens={out_tok or 0}\n")
                    elapsed = run.get("elapsed_seconds")
                    if elapsed is not None:
                        f.write(f"    elapsed_seconds={elapsed}\n")
                    if run.get("command_file"):
                        f.write(f"    command_file={run['command_file']}\n")
                    if run.get("output_file"):
                        f.write(f"    output_file={run['output_file']}\n")
                    if run.get("command"):
                        f.write(f"    command: {run['command']}\n")
                    if run.get("stderr"):
                        f.write(f"    stderr: {run['stderr']}\n")
                    output_lines = run.get("pred_lines") or []
                    f.write("    output_lines:\n")
                    if output_lines:
                        for line in output_lines:
                            f.write(f"      {line}\n")
                    else:
                        f.write("      (none)\n")
            f.write("\n")
