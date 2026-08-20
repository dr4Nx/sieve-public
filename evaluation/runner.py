"""Run log_parser.py and parse its output."""

import argparse
import json
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from log_query.cli import prepare_static_runtime, run_query_with_runtime
from log_query.logging_utils import Logger
from log_query.paths import default_output_dir
from log_query.request_args import build_log_query_namespace, build_log_query_subprocess_command


def run_query(
    query: str,
    log_path: str,
    args,
    script_path: str,
    output_format: Optional[List[str]] = None,
    output_data_type: Optional[List[str]] = None,
) -> List[str]:
    """Invoke log_parser.py and capture output lines."""
    cmd = build_log_query_subprocess_command(
        script_path,
        query,
        log_path,
        args,
        output_format,
        output_data_type,
    )
    _start = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=getattr(args, "timeout", 600),
        )
    except subprocess.TimeoutExpired:
        return ["__EVAL_ERROR__: timeout expired"]
    except Exception as exc:
        return [f"__EVAL_ERROR__: failed to start process: {exc}"]
    _elapsed = round(time.monotonic() - _start, 2)

    stdout_text = (proc.stdout or "").strip()
    if not stdout_text:
        if proc.returncode != 0:
            stderr_snip = (proc.stderr or "").strip().splitlines()
            err_line = _select_error_line(stderr_snip, proc.returncode)
            return [f"__EVAL_ERROR__: script exited {proc.returncode}: {err_line}"]
        return []

    try:
        obj = json.loads(stdout_text)
    except Exception:
        obj = None
        last_line = ""
        for line in reversed((proc.stdout or "").splitlines()):
            if line.strip():
                last_line = line.strip()
                break
        if last_line:
            try:
                obj = json.loads(last_line)
            except Exception:
                obj = None
        if obj is None:
            if proc.returncode != 0:
                stderr_snip = (proc.stderr or "").strip().splitlines()
                err_line = _select_error_line(stderr_snip, proc.returncode)
                return [f"__EVAL_ERROR__: script exited {proc.returncode}: {err_line}"]
            return proc.stdout.splitlines()

    rc = obj.get("returncode", proc.returncode)
    cmd_used = obj.get("command")
    retry_count = obj.get("retry_count")
    stdout_lines = obj.get("stdout_lines", []) or []
    stderr_text = obj.get("stderr", "") or ""

    if rc != 0:
        stderr_snip = stderr_text.splitlines() if stderr_text else []
        err_line = _select_error_line(stderr_snip, rc)
        return [f"__EVAL_ERROR__: script exited {rc}: {err_line}"]

    out_lines: List[str] = []
    if retry_count is not None:
        out_lines.append(f"__RETRIES__:{retry_count}")
    if cmd_used:
        out_lines.append(f"__COMMAND__:{cmd_used}")
    input_tokens = obj.get("input_tokens")
    output_tokens = obj.get("output_tokens")
    if input_tokens is not None or output_tokens is not None:
        out_lines.append(f"__TOKENS__:{input_tokens or 0},{output_tokens or 0}")
    out_lines.append(f"__ELAPSED__:{_elapsed}")
    out_lines.extend(list(stdout_lines))
    return out_lines


def prepare_query_runtime(
    query: str,
    log_path: str,
    eval_args,
    output_format: Optional[List[str]] = None,
    output_data_type: Optional[List[str]] = None,
    log: Optional[Logger] = None,
) -> Tuple[argparse.Namespace, Dict[str, Any]]:
    log_query_args = build_log_query_namespace(eval_args, query, log_path, output_format, output_data_type)
    runtime_log = log or Logger("ERROR")
    runtime = prepare_static_runtime(log_query_args, runtime_log)
    return log_query_args, runtime


def run_query_consistency_once(
    query: str,
    log_path: str,
    eval_args,
    runtime: Dict[str, Any],
    output_format: Optional[List[str]] = None,
    output_data_type: Optional[List[str]] = None,
    output_dir: Optional[str] = None,
    timestamp: Optional[str] = None,
    run_label: Optional[str] = None,
    log: Optional[Logger] = None,
) -> Dict[str, Any]:
    log_query_args = build_log_query_namespace(eval_args, query, log_path, output_format, output_data_type)
    run_log = log or Logger("ERROR")
    run_output_dir = output_dir or default_output_dir()
    run_timestamp = timestamp or "consistency-run"
    result = run_query_with_runtime(
        args=log_query_args,
        query=query,
        runtime=runtime,
        output_dir=run_output_dir,
        timestamp=run_timestamp,
        log=run_log,
        query_label=run_label,
    )
    return {
        "status": result.get("status", "unknown"),
        "exit_code": result.get("exit_code", 1),
        "error": result.get("error"),
        "command": result.get("command"),
        "retry_count": result.get("retry_count"),
        "stdout_lines": list(result.get("stdout_lines") or []),
        "stderr": result.get("stderr", "") or "",
        "output_file": result.get("output_file"),
        "command_file": result.get("command_file"),
        "input_tokens": result.get("input_tokens"),
        "output_tokens": result.get("output_tokens"),
        "elapsed_seconds": result.get("elapsed_seconds"),
    }


def _select_error_line(stderr_lines: List[str], rc: int) -> str:
    for line in reversed(stderr_lines):
        if line.strip().startswith("[ERROR]"):
            return line.strip()
    for line in reversed(stderr_lines):
        if line.strip():
            return line.strip()
    return f"exit {rc}"
