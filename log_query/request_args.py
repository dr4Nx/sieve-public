"""Shared helpers for log_query CLI argument parsing and invocation."""

import argparse
import re
import sys
from typing import List, Optional

from .logging_utils import Logger


def looks_like_gemini_model_name(model: str) -> bool:
    value = (model or "").strip()
    if not value:
        return False
    return re.fullmatch(r"(?:models/)?gemini-[a-z0-9][a-z0-9.-]*", value) is not None



def _parse_csv_arg(raw_value: Optional[str], flag_name: str, log: Logger) -> Optional[List[str]]:
    if raw_value is None:
        return None
    text = str(raw_value).strip()
    if not text:
        log.error(f"{flag_name} must not be empty.")
        sys.exit(1)
    items = [part.strip() for part in text.split(",")]
    if not all(items):
        log.error(f"{flag_name} contains an empty value. Use comma-separated non-empty values.")
        sys.exit(1)
    return items



def parse_output_format_arg(raw_value: Optional[str], log: Logger) -> Optional[List[str]]:
    return _parse_csv_arg(raw_value, "--output-format", log)



def parse_output_data_type_arg(raw_value: Optional[str], log: Logger) -> Optional[List[str]]:
    return _parse_csv_arg(raw_value, "--output-data-type", log)



def _append_templater_args(cmd: List[str], args) -> None:
    templater = getattr(args, "templater", None)
    if not templater:
        return
    cmd.extend(["--templater", templater])
    if getattr(args, "templater_config", None):
        cmd.extend(["--templater-config", args.templater_config])
    if getattr(args, "templater_message_separator", None):
        cmd.extend(["--templater-message-separator", args.templater_message_separator])
    if getattr(args, "templater_separator_mode", "first") != "first":
        cmd.extend(["--templater-separator-mode", args.templater_separator_mode])
    if getattr(args, "templater_allow_missing_separator", False):
        cmd.append("--templater-allow-missing-separator")
    if getattr(args, "templater_max_lines", None):
        cmd.extend(["--templater-max-lines", str(args.templater_max_lines)])



def build_log_query_subprocess_command(
    script_path: str,
    query: str,
    log_path: str,
    args,
    output_format: Optional[List[str]] = None,
    output_data_type: Optional[List[str]] = None,
) -> List[str]:
    cmd = [
        sys.executable,
        script_path,
        query,
        log_path,
        "--direct-output",
        "--suppress-logs",
        "--sample-size",
        str(args.sample_size),
        "--model",
        args.model,
        "--max-retries",
        str(args.max_retries),
    ]
    if getattr(args, "language", "bash") != "bash":
        cmd.extend(["--language", args.language])
    if output_format:
        cmd.extend(["--output-format", ",".join(output_format)])
    if output_data_type:
        cmd.extend(["--output-data-type", ",".join(output_data_type)])
    if getattr(args, "validate", False):
        cmd.append("--validate")
    if getattr(args, "api_key", None):
        cmd.extend(["--api-key", args.api_key])
    if getattr(args, "vertex_ai", False):
        cmd.append("--vertex-ai")
    if getattr(args, "project", None):
        cmd.extend(["--project", args.project])
    if getattr(args, "location", None):
        cmd.extend(["--location", args.location])
    if getattr(args, "templates", None):
        cmd.extend(["--templates", args.templates])
    else:
        _append_templater_args(cmd, args)
    if getattr(args, "worked_examples", None):
        cmd.extend(["--worked-examples", args.worked_examples])
    if getattr(args, "sample_seed", None) is not None:
        cmd.extend(["--sample-seed", str(args.sample_seed)])
    return cmd



def build_log_query_namespace(
    eval_args,
    query: str,
    log_path: str,
    output_format: Optional[List[str]] = None,
    output_data_type: Optional[List[str]] = None,
) -> argparse.Namespace:
    return argparse.Namespace(
        query_or_filename=query,
        query=query,
        filename=log_path,
        queries_file=None,
        sample_size=eval_args.sample_size,
        model=eval_args.model,
        language=getattr(eval_args, "language", "bash"),
        validate=getattr(eval_args, "validate", False),
        dry_run=False,
        confirm=False,
        direct_output=False,
        suppress_logs=True,
        debug=False,
        api_key=getattr(eval_args, "api_key", None),
        vertex_ai=getattr(eval_args, "vertex_ai", False),
        project=getattr(eval_args, "project", None),
        location=getattr(eval_args, "location", None),
        templates=getattr(eval_args, "templates", None),
        output_format=output_format,
        output_data_type=output_data_type,
        templater=getattr(eval_args, "templater", None),
        templater_config=getattr(eval_args, "templater_config", None),
        templater_message_separator=getattr(eval_args, "templater_message_separator", None),
        templater_separator_mode=getattr(eval_args, "templater_separator_mode", "first"),
        templater_allow_missing_separator=getattr(eval_args, "templater_allow_missing_separator", False),
        templater_max_lines=getattr(eval_args, "templater_max_lines", None),
        worked_examples=getattr(eval_args, "worked_examples", None),
        sample_seed=getattr(eval_args, "sample_seed", None),
        max_retries=eval_args.max_retries,
        batch_max_workers=5,
    )
