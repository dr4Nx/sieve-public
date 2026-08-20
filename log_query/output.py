"""Output helpers for command generation results."""

import os
import shlex
import sys
from typing import Optional

from .paths import default_output_dir


def build_output_paths(timestamp: str, output_dir: Optional[str] = None) -> tuple[str, str]:
    output_dir = output_dir or default_output_dir()
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"output-{timestamp}.txt")
    return output_dir, output_file


def _quote(value: object) -> str:
    return shlex.quote(str(value))


def _append_flag(parts: list[str], flag: str, value: object | None = None) -> None:
    parts.append(flag)
    if value is not None:
        parts.append(_quote(value))


def build_invocation(args, query: Optional[str] = None) -> str:
    effective_query = query if query is not None else getattr(args, "query", None)
    parts = ["python", _quote(sys.argv[0])]
    if effective_query:
        parts.extend([_quote(effective_query), _quote(args.filename)])
    else:
        _append_flag(parts, "--queries-file", args.queries_file)
        parts.append(_quote(args.filename))
    if args.sample_size != 250:
        _append_flag(parts, "--sample-size", args.sample_size)
    if args.model != "gemini-2.5-flash":
        _append_flag(parts, "--model", args.model)
    if getattr(args, "language", "bash") != "bash":
        _append_flag(parts, "--language", args.language)
    if getattr(args, "validate", False):
        _append_flag(parts, "--validate")
    if args.dry_run:
        _append_flag(parts, "--dry-run")
    if args.confirm:
        _append_flag(parts, "--confirm")
    if args.direct_output:
        _append_flag(parts, "--direct-output")
    if args.suppress_logs:
        _append_flag(parts, "--suppress-logs")
    if args.debug:
        _append_flag(parts, "--debug")
    if args.api_key:
        _append_flag(parts, "--api-key", args.api_key)
    if args.vertex_ai:
        _append_flag(parts, "--vertex-ai")
    if args.project:
        _append_flag(parts, "--project", args.project)
    if args.location:
        _append_flag(parts, "--location", args.location)
    if args.templates:
        _append_flag(parts, "--templates", args.templates)
    output_format = getattr(args, "output_format", None)
    if output_format:
        if isinstance(output_format, list):
            output_format = ",".join(str(part) for part in output_format)
        _append_flag(parts, "--output-format", output_format)
    output_data_type = getattr(args, "output_data_type", None)
    if output_data_type:
        if isinstance(output_data_type, list):
            output_data_type = ",".join(str(part) for part in output_data_type)
        _append_flag(parts, "--output-data-type", output_data_type)
    if getattr(args, "templater", None):
        _append_flag(parts, "--templater", args.templater)
        if getattr(args, "templater_config", None):
            _append_flag(parts, "--templater-config", args.templater_config)
        if getattr(args, "templater_message_separator", None):
            _append_flag(parts, "--templater-message-separator", args.templater_message_separator)
        if getattr(args, "templater_separator_mode", "first") != "first":
            _append_flag(parts, "--templater-separator-mode", args.templater_separator_mode)
        if getattr(args, "templater_allow_missing_separator", False):
            _append_flag(parts, "--templater-allow-missing-separator")
        if getattr(args, "templater_max_lines", None):
            _append_flag(parts, "--templater-max-lines", args.templater_max_lines)
    if args.max_retries != 4:
        _append_flag(parts, "--max-retries", args.max_retries)
    if getattr(args, "batch_max_workers", 5) != 5:
        _append_flag(parts, "--batch-max-workers", args.batch_max_workers)
    return " ".join(parts)


def write_success_output(
    output_file: str,
    args,
    query: str,
    final_command: str,
    retry_count: int,
    stdout_text: str,
) -> None:
    with open(output_file, "w") as out:
        full_command = build_invocation(args, query=query)
        out.write(f"# Original command: {full_command}\n")
        out.write(f"# User input query: {query}\n")
        out.write(f"# Target file: {args.filename}\n")
        if retry_count > 0:
            out.write(f"# Retries needed: {retry_count}\n")
        out.write(f"\n# Final command executed:\n{final_command}\n\n")
        out.write("# START_OUTPUT\n")
        out.write(stdout_text)
        out.write("\n# END_OUTPUT\n")


def write_failure_output(
    output_file: str,
    args,
    query: str,
    retry_count: int,
    command: Optional[str],
    error_msg: str,
) -> None:
    with open(output_file, "w") as out:
        full_command = build_invocation(args, query=query)
        out.write(f"# Original command: {full_command}\n")
        out.write(f"# User input query: {query}\n")
        out.write(f"# Target file: {args.filename}\n")
        out.write(f"# Retries attempted: {retry_count}\n")
        out.write(f"# FAILED - Final error: {error_msg}\n")
        if command:
            out.write(f"\n# Last attempted command:\n{command}\n\n")
