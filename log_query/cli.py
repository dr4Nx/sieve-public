"""CLI entry for log filtering via Gemini."""

import argparse
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from .gemini_client import build_gemini_client
from .logging_utils import Logger
from .output import build_output_paths, write_failure_output, write_success_output
from .paths import default_batch_output_dir, default_output_dir
from .prompt import craft_prompt
from .request_args import (
    looks_like_gemini_model_name,
    parse_output_data_type_arg,
    parse_output_format_arg,
)
from .safety import looks_safe
from .sampling import reservoir_sample


def _extract_text(resp) -> str:
    try:
        cand = resp.candidates[0]
        parts = getattr(cand, "content", None).parts or []
        buf = []
        for part in parts:
            if getattr(part, "text", None):
                buf.append(part.text)
            if getattr(part, "executable_code", None):
                code = part.executable_code.code
                if code:
                    buf.append(code)
        return "\n".join(buf).strip()
    except Exception:
        return ""


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate & (optionally) run a grep/awk/python filter via Gemini."
    )
    parser.add_argument(
        "query_or_filename",
        help="Query text, or log filename when --queries-file is used",
    )
    parser.add_argument(
        "filename",
        nargs="?",
        help="Path to the log file (may be .gz)",
    )
    parser.add_argument(
        "--queries-file",
        help="Path to a text file containing one query per line; runs all queries in one batch",
    )

    parser.add_argument(
        "--sample-size",
        type=int,
        default=250,
        help="How many lines to sample for context (default: 250)",
    )
    parser.add_argument(
        "--model",
        default="gemini-2.5-flash",
        help="Gemini model ID (e.g., gemini-2.5-flash, gemini-2.5-flash-lite, gemini-3.1-pro-preview)",
    )
    parser.add_argument(
        "--language",
        choices=("bash", "python"),
        default="bash",
        help="Language for the generated filter (default: bash)",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate the generated command/script on the sample before running",
    )
    parser.add_argument("--dry-run", action="store_true", help="Only print the generated command; do not execute")
    parser.add_argument("--confirm", action="store_true", help="Ask for confirmation before executing")
    parser.add_argument(
        "--direct-output",
        action="store_true",
        help="Print command output directly and skip creating output-<timestamp>.txt",
    )

    parser.add_argument("--suppress-logs", action="store_true", help="Suppress progress logs (default is verbose)")
    parser.add_argument("--debug", action="store_true", help="Very verbose (debug) logs")

    parser.add_argument("--api-key", help="Gemini API key (otherwise reads GEMINI_API_KEY)")
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
    parser.add_argument("--templates", help="Path to file containing log format templates")
    parser.add_argument("--worked-examples", help="Path to JSON file with worked query->code examples for few-shot prompting")
    parser.add_argument("--sample-seed", type=int, help="Fixed RNG seed for sample line selection (deterministic across runs)")
    parser.add_argument(
        "--output-format",
        help="Comma-separated output field order for select-style results (e.g., field1,field2)",
    )
    parser.add_argument(
        "--output-data-type",
        help="Comma-separated output data types matching output format order (e.g., string,float)",
    )
    parser.add_argument(
        "--templater",
        choices=("drain3", "frequency"),
        help="Generate templates using a built-in templater (default: none)",
    )
    parser.add_argument("--templater-config", help="Path to templater config file (drain3.ini or frequency JSON)")
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
    parser.add_argument("--max-retries", type=int, default=4, help="Maximum number of retries if command fails")
    parser.add_argument(
        "--batch-max-workers",
        type=int,
        default=5,
        help="Max parallel workers when using --queries-file (default: 5)",
    )

    return parser.parse_args()


def _validate_args(args: argparse.Namespace, log: Logger) -> None:
    if args.queries_file:
        if args.filename is not None:
            log.error("When using --queries-file, provide only one positional argument: <filename>.")
            sys.exit(1)
        args.query = None
        args.filename = args.query_or_filename
    else:
        if args.filename is None:
            log.error("Provide both positional arguments: <query> <filename>.")
            sys.exit(1)
        args.query = args.query_or_filename

    if args.queries_file and not os.path.isfile(args.queries_file):
        log.error(f"Queries file not found: {args.queries_file}")
        sys.exit(1)
    if not os.path.isfile(args.filename):
        log.error(f"File not found: {args.filename}")
        sys.exit(1)
    if args.sample_size <= 0:
        log.error("--sample-size must be a positive integer.")
        sys.exit(1)
    from .openai_client import looks_like_openai_model_name
    if not (looks_like_gemini_model_name(args.model) or looks_like_openai_model_name(args.model)):
        log.error(
            "--model must be a Gemini model ID (e.g. gemini-2.5-flash) or an "
            "OpenAI model ID (e.g. gpt-5.4, gpt-4o, o3)."
        )
        sys.exit(1)
    if args.vertex_ai and (not args.project or not args.location):
        log.error("--vertex-ai requires both --project and --location.")
        sys.exit(1)
    if args.max_retries < 0:
        log.error("--max-retries must be non-negative.")
        sys.exit(1)
    if args.batch_max_workers <= 0:
        log.error("--batch-max-workers must be a positive integer.")
        sys.exit(1)
    if args.templates and args.templater:
        log.error("Specify either --templates or --templater, not both.")
        sys.exit(1)
    if args.templater_max_lines is not None and args.templater_max_lines <= 0:
        log.error("--templater-max-lines must be a positive integer.")
        sys.exit(1)
    if args.queries_file and args.direct_output:
        log.error("--direct-output is not supported with --queries-file.")
        sys.exit(1)
    if args.queries_file and args.confirm:
        log.error("--confirm is not supported with --queries-file.")
        sys.exit(1)
    args.output_format = parse_output_format_arg(getattr(args, "output_format", None), log)
    args.output_data_type = parse_output_data_type_arg(getattr(args, "output_data_type", None), log)
    if args.output_data_type and args.output_format and len(args.output_data_type) != len(args.output_format):
        log.error("--output-data-type length must match --output-format length.")
        sys.exit(1)


def _build_system_instruction(language: str) -> str:
    if language == "python":
        return (
            "Return ONLY a JSON object with keys language and code. "
            "The code must be Python 3 using only the standard library. "
            "Do not include explanations, code fences, or surrounding text."
        )
    return (
        "Return ONLY a JSON object with keys language and command. "
        "Do not include explanations, code fences, or surrounding text."
    )


def _maybe_unescape(text: str, language: str) -> str:
    """If the code came back with literal \\n / \\t escapes (over-escaped JSON),
    decode them. Returns text unchanged when no escapes are present or the
    decode would corrupt the source."""
    if "\\n" not in text and "\\t" not in text:
        return text
    try:
        decoded = bytes(text, "utf-8").decode("unicode_escape")
    except Exception:
        return text
    if language == "python":
        import ast
        try:
            ast.parse(text)
            return text  # Original parses fine; don't second-guess.
        except SyntaxError:
            try:
                ast.parse(decoded)
                return decoded
            except SyntaxError:
                return text
    return decoded


def _parse_output_contract(payload: str, language: str, log: Logger) -> str:
    text = payload.strip()
    if not text:
        return ""
    if text.startswith("{") and text.endswith("}"):
        try:
            obj = json.loads(text)
        except Exception:
            obj = None
        if isinstance(obj, dict):
            if language == "python":
                code = obj.get("code")
                if isinstance(code, str) and code.strip():
                    return _maybe_unescape(code.strip(), language)
            else:
                cmd = obj.get("command")
                if isinstance(cmd, str) and cmd.strip():
                    return _maybe_unescape(cmd.strip(), language)
            log.warn("Output JSON missing expected field; falling back to raw text.")
            return text
        key = "code" if language == "python" else "command"
        match = re.search(rf"\"{key}\"\s*:\s*\"(.*?)\"", text, re.DOTALL)
        if match:
            raw_val = match.group(1)
            try:
                unescaped = bytes(raw_val, "utf-8").decode("unicode_escape")
            except Exception:
                unescaped = raw_val
            if unescaped.strip():
                return unescaped.strip()
    return text


def _write_sample_file(output_dir: str, timestamp: str, sample_lines) -> str:
    sample_path = os.path.join(output_dir, f"sample-{timestamp}.log")
    with open(sample_path, "w", encoding="utf-8") as f:
        f.write("".join(sample_lines))
    return sample_path


def _validate_generated(
    command: str,
    language: str,
    filename: str,
    sample_lines,
    output_dir: str,
    timestamp: str,
    log: Logger,
) -> Optional[str]:
    sample_path = _write_sample_file(output_dir, timestamp, sample_lines)
    if language == "python":
        validate_script = os.path.join(output_dir, f"validate-{timestamp}.py")
        with open(validate_script, "w", encoding="utf-8") as f:
            f.write(command.rstrip() + "\n")
        exec_cmd = [sys.executable, validate_script, sample_path]
    else:
        validate_cmd = command.replace(filename, sample_path)
        exec_cmd = ["bash", "-lc", validate_cmd]
    try:
        result = subprocess.run(
            exec_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=20,
        )
    except subprocess.TimeoutExpired:
        return "Validation timed out"
    except Exception as exc:
        return f"Validation failed to start: {exc}"

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        if stderr:
            return stderr
        return f"Validation failed with exit code {result.returncode}"
    return None


def _load_queries_file(path: str, log: Logger) -> List[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError as exc:
        log.error(f"Failed to read queries file '{path}': {exc}")
        sys.exit(1)

    queries = []
    for raw_line in lines:
        query = raw_line.strip()
        if not query or query.startswith("#"):
            continue
        queries.append(query)

    if not queries:
        log.error(f"No usable queries found in {path}.")
        sys.exit(1)
    return queries


def prepare_static_runtime(args: argparse.Namespace, log: Logger) -> Dict[str, Any]:
    sample, total = reservoir_sample(args.filename, max(1, args.sample_size), log, seed=getattr(args, "sample_seed", None))

    templated_templates_path = None
    if args.templater:
        try:
            if args.templater == "frequency":
                from .templaters import frequency_templater as _templater_mod
            else:
                from .templaters import drain3_templater as _templater_mod
        except Exception as exc:
            log.error(f"Failed to load templater '{args.templater}': {exc}")
            sys.exit(2)

        if not args.suppress_logs:
            log.info(f"Templating logs with {args.templater}...")
        try:
            templated_templates_path, _payload = _templater_mod.run_templater(
                args.filename,
                max_lines=args.templater_max_lines,
                config_path=args.templater_config,
                message_separator=args.templater_message_separator,
                require_separator=not args.templater_allow_missing_separator,
                separator_mode=args.templater_separator_mode,
                debug=args.debug,
            )
        except Exception as exc:
            log.error(f"Templating failed: {exc}")
            sys.exit(2)
        if not args.suppress_logs:
            log.info(f"Templating complete: {templated_templates_path}")

    return {
        "sample": sample,
        "total": total,
        "templated_templates_path": templated_templates_path,
    }


def run_query_with_runtime(
    args: argparse.Namespace,
    query: str,
    runtime: Dict[str, Any],
    output_dir: str,
    timestamp: str,
    log: Logger,
    query_label: Optional[str] = None,
    client=None,
    types_mod=None,
) -> dict:
    if client is None or types_mod is None:
        client, types_mod = build_gemini_client(args, log)
    return _run_single_query(
        args=args,
        query=query,
        sample=runtime["sample"],
        total=runtime["total"],
        client=client,
        types_mod=types_mod,
        templated_templates_path=runtime.get("templated_templates_path"),
        output_dir=output_dir,
        timestamp=timestamp,
        log=log,
        query_label=query_label,
    )


def _run_single_query(
    args: argparse.Namespace,
    query: str,
    sample,
    total: int,
    client,
    types_mod,
    templated_templates_path: Optional[str],
    output_dir: str,
    timestamp: str,
    log: Logger,
    query_label: Optional[str] = None,
) -> dict:
    import time as _time
    _start = _time.monotonic()
    result = _run_single_query_impl(
        args, query, sample, total, client, types_mod,
        templated_templates_path, output_dir, timestamp, log, query_label,
    )
    result["elapsed_seconds"] = round(_time.monotonic() - _start, 2)
    return result


def _run_single_query_impl(
    args: argparse.Namespace,
    query: str,
    sample,
    total: int,
    client,
    types_mod,
    templated_templates_path: Optional[str],
    output_dir: str,
    timestamp: str,
    log: Logger,
    query_label: Optional[str] = None,
) -> dict:
    output_dir, output_file = build_output_paths(timestamp, output_dir=output_dir)
    retry_count = 0
    max_retries = args.max_retries
    previous_error = None
    artifact_label = "Python script" if args.language == "python" else "command"
    prefix = f"[{query_label}] " if query_label else ""
    command_file = None
    total_input_tokens = 0
    total_output_tokens = 0

    while retry_count <= max_retries:
        prompt = craft_prompt(
            query,
            args.filename,
            sample,
            total,
            len(sample),
            args.templates or templated_templates_path,
            args.language,
            retry_count,
            previous_error,
            log,
            output_format_fields=args.output_format,
            output_data_types=args.output_data_type,
            worked_examples_path=getattr(args, "worked_examples", None),
        )

        if retry_count == 0:
            log.info(f"{prefix}Sending prompt to Gemini to synthesize a single filtering {artifact_label}...")
        else:
            log.info(f"{prefix}Retry {retry_count}/{max_retries}: Sending updated prompt to Gemini...")

        # Retry transient API errors (429, 503, timeouts) with exponential backoff
        import time as _t_mod
        response = None
        api_error = None
        for attempt in range(6):
            try:
                response = client.models.generate_content(
                    model=args.model,
                    contents=prompt,
                    config=types_mod.GenerateContentConfig(
                        system_instruction=_build_system_instruction(args.language)
                    ),
                )
                api_error = None
                break
            except Exception as exc:
                api_error = exc
                err_str = str(exc)
                # Detect transient errors worth retrying
                transient = any(code in err_str for code in [
                    "429", "RESOURCE_EXHAUSTED",
                    "503", "UNAVAILABLE",
                    "504", "DEADLINE_EXCEEDED",
                    "500", "INTERNAL",
                    "timeout", "Connection",
                ])
                if not transient:
                    break
                # Exponential backoff: 5, 10, 20, 40, 80, 160 seconds
                wait = 5 * (2 ** attempt)
                log.warn(f"{prefix}Transient API error (attempt {attempt + 1}/6): {err_str[:120]}; backing off {wait}s")
                _t_mod.sleep(wait)
        if api_error is not None or response is None:
            error_msg = f"Gemini API call failed after retries: {api_error}"
            log.error(f"{prefix}{error_msg}")
            return {"exit_code": 2, "status": "api_error", "error": error_msg, "output_file": output_file,
                    "input_tokens": total_input_tokens, "output_tokens": total_output_tokens}

        usage = getattr(response, "usage_metadata", None)
        input_tokens = getattr(usage, "prompt_token_count", None) if usage else None
        output_tokens = getattr(usage, "candidates_token_count", None) if usage else None
        if input_tokens:
            total_input_tokens += input_tokens
        if output_tokens:
            total_output_tokens += output_tokens

        command = _extract_text(response)
        if not command:
            log.error(f"{prefix}No command text returned by Gemini.")
            if retry_count < max_retries:
                retry_count += 1
                previous_error = "No command returned"
                continue
            return {
                "exit_code": 3,
                "status": "no_command",
                "error": "No command text returned by Gemini.",
                "output_file": output_file,
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
            }

        command = re.sub(r"^```[a-zA-Z0-9]*\n|```$", "", command).strip()
        command = _parse_output_contract(command, args.language, log)

        if not args.suppress_logs:
            retry_suffix = f" (Retry {retry_count}/{max_retries})" if retry_count > 0 else ""
            label = "code" if args.language == "python" else "command"
            print(f"\n#--- {prefix}Generated {label} (from Gemini){retry_suffix} ---#")
            print(command)
            print("#--------------------------------------#\n")

        if not looks_safe(command, args.filename, log, language=args.language):
            if retry_count < max_retries:
                retry_count += 1
                previous_error = "Command failed safety checks"
                continue
            error_msg = "Refusing to execute the generated command due to safety checks."
            log.error(f"{prefix}{error_msg}")
            return {"exit_code": 4, "status": "unsafe_command", "error": error_msg, "output_file": output_file,
                    "input_tokens": total_input_tokens, "output_tokens": total_output_tokens}

        if retry_count == 0:
            if args.dry_run:
                log.info(f"{prefix}Dry run: not executing.")
                return {"exit_code": 0, "status": "dry_run", "output_file": output_file, "command": command,
                        "input_tokens": total_input_tokens, "output_tokens": total_output_tokens}
            if args.validate:
                validation_error = _validate_generated(
                    command,
                    args.language,
                    args.filename,
                    sample,
                    output_dir,
                    timestamp,
                    log,
                )
                if validation_error:
                    if retry_count < max_retries:
                        retry_count += 1
                        previous_error = f"Validation failed: {validation_error}"
                        continue
                    log.error(f"{prefix}Validation failed: {validation_error}")
                    return {
                        "exit_code": 5,
                        "status": "validation_error",
                        "error": validation_error,
                        "output_file": output_file,
                        "input_tokens": total_input_tokens,
                        "output_tokens": total_output_tokens,
                    }
            if args.confirm:
                ans = input(f"Proceed to execute the {artifact_label}? [y/N] ").strip().lower()
                if ans not in {"y", "yes"}:
                    log.warn(f"{prefix}User declined execution. Exiting.")
                    return {"exit_code": 0, "status": "declined", "output_file": output_file,
                            "input_tokens": total_input_tokens, "output_tokens": total_output_tokens}

        if args.language == "python":
            command_file = os.path.join(output_dir, f"generated_command-{timestamp}.py")
            with open(command_file, "w", encoding="utf-8") as f:
                f.write(command.rstrip() + "\n")
            exec_cmd = [sys.executable, command_file, args.filename]
        else:
            command_file = os.path.join(output_dir, f"generated_command-{timestamp}.sh")
            with open(command_file, "w", encoding="utf-8") as f:
                f.write("#!/bin/bash\n")
                f.write(command + "\n")
            os.chmod(command_file, 0o755)
            exec_cmd = ["bash", command_file]

        log.info(f"{prefix}Executing the {artifact_label} from {command_file}...")
        result = subprocess.run(
            exec_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        rc = result.returncode

        if rc == 0:
            log.info(f"{prefix}{artifact_label.capitalize()} executed successfully.")

            if args.direct_output:
                out_obj = {
                    "query": query,
                    "command": command,
                    "returncode": rc,
                    "retry_count": retry_count,
                    "max_retries": max_retries,
                    "stdout_lines": result.stdout.splitlines() if result.stdout else [],
                    "stderr": result.stderr or "",
                    "timestamp": datetime.now().strftime("%Y%m%d-%H%M%S"),
                    "input_tokens": total_input_tokens,
                    "output_tokens": total_output_tokens,
                }
                try:
                    print(json.dumps(out_obj, ensure_ascii=False))
                except Exception:
                    print(json.dumps({"returncode": rc, "stderr": "json-encode-failed"}))
                return {
                    "exit_code": rc,
                    "status": "direct_output",
                    "output_file": output_file,
                    "command": command,
                    "retry_count": retry_count,
                    "stdout_lines": result.stdout.splitlines() if result.stdout else [],
                    "stderr": result.stderr or "",
                    "command_file": command_file,
                    "input_tokens": total_input_tokens,
                    "output_tokens": total_output_tokens,
                }

            write_success_output(output_file, args, query, command, retry_count, result.stdout)
            log.info(f"{prefix}Output saved to {output_file}")
            return {
                "exit_code": 0,
                "status": "success",
                "output_file": output_file,
                "command": command,
                "retry_count": retry_count,
                "stdout_lines": result.stdout.splitlines() if result.stdout else [],
                "stderr": result.stderr or "",
                "command_file": command_file,
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
            }

        error_msg = result.stderr.strip() if result.stderr else f"{artifact_label} failed with exit code {rc}"
        if retry_count < max_retries:
            log.warn(
                f"{prefix}{artifact_label.capitalize()} failed (attempt {retry_count + 1}/{max_retries + 1}): {error_msg}"
            )
            retry_count += 1
            previous_error = error_msg
            continue

        log.error(f"{prefix}{artifact_label.capitalize()} failed after {max_retries + 1} attempts. Final error: {error_msg}")
        write_failure_output(output_file, args, query, retry_count, command, error_msg)
        return {
            "exit_code": 1,
            "status": "failure",
            "output_file": output_file,
            "error": error_msg,
            "stdout_lines": result.stdout.splitlines() if result.stdout else [],
            "stderr": result.stderr or "",
            "command": command,
            "retry_count": retry_count,
            "command_file": command_file,
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
        }

    return {"exit_code": 1, "status": "failure", "output_file": output_file, "error": "Unexpected retry loop exit.",
            "input_tokens": total_input_tokens, "output_tokens": total_output_tokens}


def main() -> None:
    load_dotenv()
    args = _parse_args()

    level = "DEBUG" if args.debug else ("ERROR" if args.suppress_logs else "INFO")
    log = Logger(level)

    _validate_args(args, log)

    runtime = prepare_static_runtime(args, log)
    sample = runtime["sample"]
    total = runtime["total"]
    templated_templates_path = runtime.get("templated_templates_path")
    client, types_mod = build_gemini_client(args, log)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    if args.queries_file:
        queries = _load_queries_file(args.queries_file, log)
        batch_output_dir = default_batch_output_dir(timestamp)
        os.makedirs(batch_output_dir, exist_ok=True)
        max_workers = min(args.batch_max_workers, len(queries))
        log.info(
            f"Running batch with {len(queries)} queries using up to {max_workers} workers. "
            f"Output directory: {batch_output_dir}"
        )

        results: list[Optional[tuple[str, dict]]] = [None] * len(queries)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_meta = {}
            for idx, query in enumerate(queries, start=1):
                item_stamp = f"{timestamp}-{idx:03d}"
                query_label = f"Query {idx}/{len(queries)}"
                future = executor.submit(
                    _run_single_query,
                    args,
                    query,
                    sample,
                    total,
                    client,
                    types_mod,
                    templated_templates_path,
                    batch_output_dir,
                    item_stamp,
                    log,
                    query_label,
                )
                future_to_meta[future] = (idx, query, item_stamp)

            completed = 0
            total_queries = len(queries)
            for future in as_completed(future_to_meta):
                idx, query, item_stamp = future_to_meta[future]
                expected_output = os.path.join(batch_output_dir, f"output-{item_stamp}.txt")
                try:
                    result = future.result()
                except Exception as exc:
                    result = {
                        "exit_code": 1,
                        "status": "exception",
                        "error": str(exc),
                        "output_file": expected_output,
                    }
                if not result.get("output_file"):
                    result["output_file"] = expected_output
                results[idx - 1] = (query, result)
                completed += 1
                if not args.suppress_logs:
                    log.info(f"Completed batch query {completed}/{total_queries}.")

        summary_lines = ["# Batch query summary", f"# Created: {datetime.now().isoformat()}", ""]
        failures = 0
        for idx, item in enumerate(results, start=1):
            if item is None:
                summary_lines.append(f"[{idx}] status=missing output=")
                summary_lines.append("query=")
                summary_lines.append("error=missing result entry")
                summary_lines.append("")
                failures += 1
                continue
            query, result = item
            status = result.get("status", "unknown")
            output_file = result.get("output_file", "")
            error = result.get("error", "")
            summary_lines.append(f"[{idx}] status={status} output={output_file}")
            summary_lines.append(f"query={query}")
            if error:
                summary_lines.append(f"error={error}")
            summary_lines.append("")
            if result.get("exit_code", 1) != 0:
                failures += 1

        summary_file = os.path.join(batch_output_dir, "batch-summary.txt")
        with open(summary_file, "w", encoding="utf-8") as f:
            f.write("\n".join(summary_lines))
        log.info(f"Batch summary saved to {summary_file}")
        if failures:
            log.error(f"Batch completed with {failures} failed queries out of {len(queries)}.")
            sys.exit(1)
        log.info(f"Batch completed successfully for all {len(queries)} queries.")
        sys.exit(0)

    result = _run_single_query(
        args=args,
        query=args.query,
        sample=sample,
        total=total,
        client=client,
        types_mod=types_mod,
        templated_templates_path=templated_templates_path,
        output_dir=default_output_dir(),
        timestamp=timestamp,
        log=log,
    )
    if result.get("exit_code", 1) != 0 and result.get("error"):
        print(f"\nFinal error:\n{result['error']}", file=sys.stderr)
    sys.exit(result.get("exit_code", 1))


if __name__ == "__main__":
    main()
