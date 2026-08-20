"""Prompt construction for Gemini log filtering."""

import json
import os
from typing import List, Optional

from .logging_utils import Logger


def _language_constraints(language: str) -> str:
    if language == "python":
        return (
            "- Use Python 3 with only the standard library (e.g., re, json, gzip).\n"
            "- Output ONLY Python code (no shell wrapper, no code fences).\n"
            "- Read the target file from sys.argv[1] (or argparse) and do not hardcode other paths.\n"
            "- The code MUST read from the file path provided and MUST NOT modify files.\n"
            "- Do NOT write, edit, create, or delete files (no open(..., 'w'/'a'/'x'), pathlib write_*(), os.remove()).\n"
            "- Do NOT invoke subprocesses or shells.\n"
            "- Be mindful of word boundaries when relevant (i.e. searching for 'amanda1' should not match 'amanda123').\n"
            "- Make sure to use correct syntax and think as much as needed to get it right.\n"
            "- Quote patterns safely.\n"
            "- There may be multiple formats of log lines that fulfill the original request; try to cover them all in the code if possible.\n"
            "- The log timeline starts in year 2000. Do not assume any year rollover\n"
            "- If timestamps are requested in output, emit Unix timestamps in seconds unless the query explicitly asks for the original timestamp text or another format.\n"
            "- Interpret timestamps as local wall-clock log time unless the query explicitly asks for UTC conversion.\n"
            "- The Python code can be multi-line and may include comments.\n"
            "- Wrap the code in a JSON object as the value of \"code\"; escape newlines as \\n.\n"
        )
    return (
        "- Use ONLY grep, egrep, awk. Preferably use awk.\n"
        "- If the command requires it, you can pass output into a new command with the | operator.\n"
        "- The command MUST read from the file path provided and MUST NOT modify files.\n"
        "- Avoid dangerous tokens (rm, mv, cp, sudo, >, >>, sed -i, curl, wget, tee, touch, mkdir).\n"
        "- Awk can be multi-line and should include comments.\n"
        "- Prefer awk when feasible.\n"
        "- Be mindful of word boundaries when relevant (i.e. searching for 'amanda1' should not match 'amanda123').\n"
        "- Make sure to use correct syntax and think as much as needed to get it right.\n"
        "- Quote patterns safely.\n"
        "- There may be multiple formats of log lines that fulfill the original request; try to cover them all in the command if possible.\n"
        "- Assume Linux, POSIX sh/bash.\n"
        "- The log timeline starts in year 2000. Do not assume any year rollover\n"
        "- If timestamps are requested in output, emit Unix timestamps in seconds unless the query explicitly asks for the original timestamp text or another format.\n"
        "- Interpret timestamps as local wall-clock log time unless the query explicitly asks for UTC conversion.\n"
        "- Wrap the command in a JSON object as the value of \"command\".\n"
    )


def _query_execution_guardrails(query: str) -> str:
    lines = [
        "QUERY EXECUTION GUARDRAILS:",
        "- Parse robustly: support variable whitespace and optional process/PID decorations; avoid relying on one brittle regex.",
        "- Build explicit intermediate records for stateful logic (event_type, timestamp, client/host, process_id, transaction_id, interface, IP).",
        "- Preserve identifier formatting exactly as seen in logs (e.g., keep '0x' prefix on transaction IDs).",
        "- Never emit placeholder values (None/null/N/A) for required output fields; skip rows missing required fields.",
        "- For transaction-level joins, key by (client, transaction_id) when available; do not merge globally by transaction_id alone.",
        "- Use (host, process_id) only as a fallback to infer missing transaction_id when the mapping is unambiguous.",
        "",
    ]
    return "\n".join(lines)


def _load_templates(templates_path: Optional[str], log: Optional[Logger]) -> str:
    log_templates = ""
    if not templates_path:
        if log:
            log.info("No templates file specified - proceeding without log format templates")
        return log_templates

    if not os.path.exists(templates_path):
        if log:
            log.warn(f"Templates file not found: {templates_path}")
        return log_templates

    try:
        with open(templates_path, "r", encoding="utf-8") as f:
            template_content = f.read().strip()
    except Exception as exc:
        if log:
            log.warn(f"Failed to load templates from {templates_path}: {exc}")
        return log_templates

    if not template_content:
        if log:
            log.warn(f"Templates file is empty: {templates_path}")
        return log_templates

    payload = None
    if template_content.lstrip().startswith("{"):
        try:
            payload = json.loads(template_content)
        except Exception:
            payload = None

    if isinstance(payload, dict) and payload.get("templates") is not None:
        templates = payload.get("templates") or []
        examples = payload.get("examples") if isinstance(payload.get("examples"), dict) else {}
        if not templates:
            if log:
                log.warn(f"Templates file has no templates: {templates_path}")
            return log_templates
        if log:
            log.info(f"Using templates from {templates_path} ({len(templates)} templates loaded)")
        log_templates = "\n\nKNOWN LOG FORMATS (AUTHORITATIVE; review all before writing your filter):\n"
        log_templates += "Multiple templates may match the same query. Handle every one that could apply. Rare formats may appear thousands of times in the full file.\n"
        for template in templates:
            example = examples.get(template)
            if example:
                log_templates += f"TEMPLATE: {template}\nEXAMPLE: {example}\n"
            else:
                log_templates += f"TEMPLATE: {template}\n"
        return log_templates

    if log:
        log.info(
            f"Using templates from {templates_path} ({len(template_content.splitlines())} lines loaded)"
        )
    log_templates = "\n\nKNOWN LOG FORMATS:\n"
    log_templates += "The following are known log message templates that may appear in the logs:\n"
    log_templates += template_content + "\n"
    log_templates += "\nUse these templates to understand the structure and extract relevant fields.\n"
    return log_templates


def _output_format_guidance(output_format_fields: Optional[List[str]]) -> str:
    if not output_format_fields:
        return (
            "- Do not extract, reorder, normalize, summarize, or reformat fields unless the query explicitly asks for structured output.\n\n"
        )
    joined = ", ".join(output_format_fields)
    has_timestamp_field = any(
        ("time" in field.lower()) or ("timestamp" in field.lower()) for field in output_format_fields
    )
    has_epoch_like_boundary_field = any(
        field.lower() in {"start", "end", "window_start", "window_end"}
        or field.lower().endswith("_start")
        or field.lower().endswith("_end")
        for field in output_format_fields
    )
    timestamp_rule = ""
    if has_timestamp_field or has_epoch_like_boundary_field:
        timestamp_rule = "- Any requested timestamp/time field must be Unix timestamp in seconds unless the query explicitly asks for the original timestamp text or another format.\n"
    return (
        "OUTPUT FORMAT REQUIREMENTS:\n"
        f"- Emit result rows in this exact field order: {joined}\n"
        "- Emit one result row per line.\n"
        "- Output plain text values separated by single spaces (no JSON, no CSV, no tabs).\n"
        "- Do not print a header row unless the user query explicitly asks for one.\n"
        "- Print only the requested fields in the specified order.\n\n"
        "- Do not emit placeholder values like None/null/N/A for required fields.\n"
        "- Keep string identifiers exact (do not strip prefixes like 0x, do not alter MAC/IP punctuation).\n\n"
        f"{timestamp_rule}"
    )


def _output_data_type_guidance(
    output_data_types: Optional[List[str]],
    output_format_fields: Optional[List[str]],
) -> str:
    if not output_data_types:
        return ""
    lines = [
        "OUTPUT DATA TYPE REQUIREMENTS:",
        "- Ensure each emitted field value follows the requested type constraints.",
    ]
    if output_format_fields and len(output_format_fields) == len(output_data_types):
        lines.append("- Required type by field:")
        for field, dtype in zip(output_format_fields, output_data_types):
            lines.append(f"  - {field}: {dtype}")
    else:
        lines.append("- Required types in output order: " + ", ".join(output_data_types))
    lines.append(
        "- Use consistent formatting (e.g., integers without decimals, floats as numeric values, strings as plain text)."
    )
    lines.append("- For string identifiers, preserve exact source formatting (including prefixes like 0x).")
    if output_format_fields and len(output_format_fields) == len(output_data_types):
        for field, dtype in zip(output_format_fields, output_data_types):
            fl = field.lower()
            is_time_like = (
                ("time" in fl)
                or ("timestamp" in fl)
                or fl in {"start", "end", "window_start", "window_end"}
                or fl.endswith("_start")
                or fl.endswith("_end")
            )
            is_numeric = dtype.strip().lower() in {"float", "int", "integer", "number"}
            if is_time_like and is_numeric:
                lines.append(f"- Field '{field}' must be Unix timestamp in seconds.")
    lines.append("")
    return "\n".join(lines)


def _load_worked_examples(worked_examples_path: Optional[str], language: str, log: Optional[Logger]) -> str:
    """Load worked query->code examples from a JSON file.

    Expected format: [{"query": "...", "code": "..."}, ...]
    Returns an empty string if no path is given or the file is missing.
    """
    if not worked_examples_path:
        return ""
    if not os.path.exists(worked_examples_path):
        if log:
            log.warn(f"Worked examples file not found: {worked_examples_path}")
        return ""
    try:
        with open(worked_examples_path, "r", encoding="utf-8") as f:
            examples = json.load(f)
    except Exception as exc:
        if log:
            log.warn(f"Failed to load worked examples from {worked_examples_path}: {exc}")
        return ""
    if not isinstance(examples, list) or not examples:
        return ""

    label = "code" if language == "python" else "command"
    section = "\nWORKED EXAMPLES:\n"
    section += "The following are example queries with correct solutions. Use them as reference for style and approach.\n"
    for i, ex in enumerate(examples, 1):
        query = ex.get("query", "")
        code = ex.get("code", "")
        if not query or not code:
            continue
        section += f"Example {i} query: {query}\n"
        section += f"Example {i} {label}:\n{code}\n\n"
    return section


def craft_prompt(
    query: str,
    filename: str,
    sample_lines: List[str],
    total_lines: int,
    sample_size: int,
    templates_path: Optional[str] = None,
    language: str = "bash",
    retry_count: int = 0,
    previous_error: Optional[str] = None,
    log: Optional[Logger] = None,
    output_format_fields: Optional[List[str]] = None,
    output_data_types: Optional[List[str]] = None,
    worked_examples_path: Optional[str] = None,
) -> str:
    log_templates = _load_templates(templates_path, log)
    worked_examples = _load_worked_examples(worked_examples_path, language, log)
    output_format_guidance = _output_format_guidance(output_format_fields)
    output_data_type_guidance = _output_data_type_guidance(output_data_types, output_format_fields)
    query_execution_guardrails = _query_execution_guardrails(query)

    language = language or "bash"
    intro = "You are a log-filtering assistant. You will output a single command that filters the given file.\n"
    if language == "python":
        intro = "You are a log-filtering assistant. You will output Python code that filters the given file.\n"
    header = (
        intro
        + "USER QUERY (HIGHEST PRIORITY):\n"
        f"{query}\n"
        "- Follow the user query literally when deciding what to match and what to print.\n"
        "- Treat the requested output semantics in the user query as higher priority than generic defaults.\n"
        "- If the user query conflicts with a default formatting rule, follow the user query.\n\n"
        + "CONSTRAINTS:\n"
        f"{_language_constraints(language)}\n"
        f"LANGUAGE: {language}\n\n"
        f"Target file: {filename}\n"
        f"Context: sampled {sample_size} lines out of ~{total_lines} total.\n"
        f"{log_templates}\n"
        f"{worked_examples}"
        f"{query_execution_guardrails}"
        f"{output_format_guidance}"
        f"{output_data_type_guidance}"
        f"{('RETRY ATTEMPT ' + str(retry_count) + '/4 - Previous command failed with error: ' + previous_error + '\nPlease fix the command while preserving the user query semantics.\n\n') if retry_count > 0 else ''}"
        "Sample follows between <SAMPLE> tags. Use it only to learn the log structure. Do not let sample patterns override the user query.\n"
        "<SAMPLE>\n"
    )
    if language == "python":
        tail = (
            "</SAMPLE>\n"
            "Now output ONLY a JSON object like:\n"
            "{\"language\":\"python\",\"code\":\"<python code with \\n escapes>\"}\n"
            "No extra text."
        )
    else:
        tail = (
            "</SAMPLE>\n"
            "Now output ONLY a JSON object like:\n"
            "{\"language\":\"bash\",\"command\":\"<command>\"}\n"
            "No extra text."
        )
    body = "".join(sample_lines)
    return header + body + tail
