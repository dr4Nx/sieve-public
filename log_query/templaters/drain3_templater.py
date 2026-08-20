"""Extract log templates from a file using drain3."""

import argparse
import gzip
import json
import os
import sys
from datetime import datetime

from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig

from ..paths import default_extracted_templates_dir


def _open_log_file(path: str):
    if path.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return open(path, "r", encoding="utf-8", errors="replace")


def _default_output_dir() -> str:
    return default_extracted_templates_dir()


def _stem_name(path: str) -> str:
    base = os.path.basename(path)
    if base.endswith(".gz"):
        base = base[:-3]
    stem, _ext = os.path.splitext(base)
    return stem or "log"


def _collect_templates(template_miner: TemplateMiner) -> list[str]:
    clusters = getattr(template_miner.drain, "clusters", None)
    if isinstance(clusters, dict):
        cluster_iter = clusters.values()
    elif isinstance(clusters, list):
        cluster_iter = clusters
    else:
        cluster_iter = []

    templates = []
    for cluster in cluster_iter:
        if hasattr(cluster, "get_template"):
            template = cluster.get_template()
        elif hasattr(cluster, "template"):
            template = cluster.template
        else:
            template = str(cluster)
        if template:
            templates.append(template)
    return templates


def _extract_templates(
    input_path: str,
    max_lines: int | None,
    config_path: str | None,
    message_separator: str | None,
    require_separator: bool,
    separator_mode: str,
    debug: bool,
) -> tuple[list[str], dict]:
    config = TemplateMinerConfig()
    if config_path:
        config.load(config_path)
    template_miner = TemplateMiner(config=config)

    total_lines = 0
    empty_lines = 0
    stripped_to_empty = 0
    processed_lines = 0
    missing_separator = 0
    result_templates = set()
    examples = {}
    debug_samples = 0

    with _open_log_file(input_path) as handle:
        for idx, raw_line in enumerate(handle, start=1):
            if max_lines and idx > max_lines:
                break
            total_lines += 1
            original_line = raw_line.rstrip("\n")
            line = original_line.strip()
            if not line:
                empty_lines += 1
                continue
            if message_separator:
                if separator_mode == "last":
                    _, sep, remainder = line.rpartition(message_separator)
                else:
                    _, sep, remainder = line.partition(message_separator)
                if sep:
                    line = remainder.strip()
                    if not line:
                        missing_separator += 1
                        continue
                elif require_separator:
                    missing_separator += 1
                    continue
            if not line:
                stripped_to_empty += 1
                continue
            result = template_miner.add_log_message(line)
            if isinstance(result, dict):
                template = result.get("template_mined") or result.get("template")
                if template:
                    result_templates.add(template)
                    examples.setdefault(template, original_line)
                if debug and debug_samples < 3:
                    print(f"Debug sample {debug_samples + 1}: {result}", file=sys.stderr)
                    debug_samples += 1
            processed_lines += 1

    templates = list(result_templates)
    if not templates:
        templates = _collect_templates(template_miner)
    for template in templates:
        examples.setdefault(template, "")
    if debug:
        print(
            "Debug: total_lines=%d empty_lines=%d stripped_to_empty=%d processed_lines=%d clusters=%d"
            % (total_lines, empty_lines, stripped_to_empty, processed_lines, len(templates)),
            file=sys.stderr,
        )
        if message_separator:
            print("Debug: missing_separator=%d" % missing_separator, file=sys.stderr)
    templates = sorted(set(templates))
    ordered_examples = {template: examples.get(template, "") for template in templates}
    return templates, ordered_examples


def run_templater(
    input_file: str,
    output_dir: str | None = None,
    output_file: str | None = None,
    max_lines: int | None = None,
    config_path: str | None = None,
    message_separator: str | None = None,
    require_separator: bool = True,
    separator_mode: str = "first",
    debug: bool = False,
) -> tuple[str, dict]:
    if not os.path.isfile(input_file):
        raise FileNotFoundError(f"Input file not found: {input_file}")
    if max_lines is not None and max_lines <= 0:
        raise ValueError("--max-lines must be a positive integer.")

    output_dir = output_dir or _default_output_dir()
    os.makedirs(output_dir, exist_ok=True)

    templates, examples = _extract_templates(
        input_file,
        max_lines,
        config_path,
        message_separator,
        require_separator,
        separator_mode,
        debug,
    )

    if output_file:
        output_path = os.path.join(output_dir, output_file)
    else:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        stem = _stem_name(input_file)
        output_path = os.path.join(output_dir, f"{stem}_templates_{timestamp}.json")

    payload = {
        "templates": templates,
        "examples": examples,
    }

    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")

    return output_path, payload


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract log templates via drain3.")
    parser.add_argument("input_file", help="Path to the log file (plain text or .gz)")
    parser.add_argument(
        "--output-dir",
        default=_default_output_dir(),
        help="Directory to write extracted templates (default: log_query/extracted_templates)",
    )
    parser.add_argument(
        "--output-file",
        help="Optional output filename (default: derived from input file name)",
    )
    parser.add_argument(
        "--max-lines",
        type=int,
        help="Only process the first N lines (useful for quick sampling)",
    )
    parser.add_argument(
        "--config",
        help="Path to drain3.ini config file (for masking and Drain params)",
    )
    parser.add_argument(
        "--message-separator",
        help="Split each line on this separator and parse the right-hand side",
    )
    parser.add_argument(
        "--require-separator",
        action="store_true",
        default=True,
        help="Skip lines that do not contain the message separator (default: on)",
    )
    parser.add_argument(
        "--allow-missing-separator",
        action="store_true",
        help="Allow lines without the message separator to be processed",
    )
    parser.add_argument(
        "--separator-mode",
        choices=("first", "last"),
        default="first",
        help="Use the first or last occurrence of the separator (default: first)",
    )
    parser.add_argument("--debug", action="store_true", help="Print line-processing stats to stderr")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    try:
        output_path, payload = run_templater(
            args.input_file,
            output_dir=args.output_dir,
            output_file=args.output_file,
            max_lines=args.max_lines,
            config_path=args.config,
            message_separator=args.message_separator,
            require_separator=args.require_separator and not args.allow_missing_separator,
            separator_mode=args.separator_mode,
            debug=args.debug,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    print(f"Wrote {len(payload.get('templates', []))} templates to {output_path}")


if __name__ == "__main__":
    main()
