"""Extract log templates using frequency-based token analysis.

Algorithm:
1. Tokenize messages and group by token count.
2. For each position in a length group, count unique values.
   Positions where the unique-value ratio exceeds a threshold are variable.
3. Build a "skeleton" from the constant tokens; lines sharing a skeleton
   collapse into one template.
4. Emit one template + one example per skeleton.

This is a simplified IPLoM-style approach. Fast (two linear passes),
needs no external deps, and handles structured key=value logs naturally.
"""

import argparse
import gzip
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from typing import Optional

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


WILDCARD = "<*>"

# General-purpose patterns that normalize highly variable tokens before
# grouping.  These are format-agnostic and target common structural
# patterns found across many log types.
_NORMALIZE_PATTERNS = [
    # Parenthesized identifiers like (/Stage[main]/Ntp/File[/etc/ntp.conf])
    (re.compile(r"^\([^)]+\)"), WILDCARD),
    # Quoted strings: 'value' or "value"
    (re.compile(r"'[^']*'"), f"'{WILDCARD}'"),
    (re.compile(r'"[^"]*"'), f'"{WILDCARD}"'),
    # Hex values like 0x7fff2a3b or {md5}abc123
    (re.compile(r"\b0x[0-9a-fA-F]+\b"), WILDCARD),
    (re.compile(r"\{[a-z0-9]+\}[0-9a-fA-F]+"), WILDCARD),
    # IP:port or IP addresses
    (re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?::\d+)?\b"), WILDCARD),
    # Numbers in parentheses like (1234567.890:42)
    (re.compile(r"\([0-9.:]+\)"), f"({WILDCARD})"),
    # File/URL paths (/foo/bar/baz or puppet://host/path)
    (re.compile(r"(?:puppet|https?|ftp)://\S+"), WILDCARD),
    (re.compile(r"/(?:[a-zA-Z0-9_.%-]+/){2,}\S*"), WILDCARD),
]


def _normalize_message(line: str) -> str:
    """Normalize variable parts of a message before tokenization."""
    for pattern, replacement in _NORMALIZE_PATTERNS:
        line = pattern.sub(replacement, line)
    return line


def _build_templates(
    messages: list[list[str]],
    originals: list[str],
    variability_threshold: float,
    debug: bool,
) -> tuple[list[str], dict[str, str]]:
    """Build templates from tokenized messages.

    Args:
        messages: List of tokenized messages (each is a list of strings).
        originals: Corresponding full original log lines (for examples).
        variability_threshold: Fraction of unique values at a position
            above which the position is marked variable (0.0–1.0).
        debug: Print stats to stderr.

    Returns:
        (sorted_templates, examples_dict)
    """
    # Group indices by token count.
    by_length: dict[int, list[int]] = defaultdict(list)
    for idx, tokens in enumerate(messages):
        by_length[len(tokens)].append(idx)

    # For each length group, identify variable positions and build skeletons.
    skeleton_examples: dict[str, str] = {}
    skeleton_counts: dict[str, int] = {}

    for length, indices in by_length.items():
        group_size = len(indices)
        if group_size == 0:
            continue

        # Count unique values at each position.
        position_values: list[set[str]] = [set() for _ in range(length)]
        for idx in indices:
            for pos, token in enumerate(messages[idx]):
                position_values[pos].add(token)

        # Mark positions as variable or constant.
        variable_positions: set[int] = set()
        for pos in range(length):
            unique_ratio = len(position_values[pos]) / group_size
            if unique_ratio > variability_threshold:
                variable_positions.add(pos)

        # Build skeleton for each line and group.
        for idx in indices:
            tokens = messages[idx]
            skeleton_parts = []
            for pos, token in enumerate(tokens):
                if pos in variable_positions:
                    skeleton_parts.append(WILDCARD)
                else:
                    skeleton_parts.append(token)
            skeleton = " ".join(skeleton_parts)
            skeleton_counts[skeleton] = skeleton_counts.get(skeleton, 0) + 1
            if skeleton not in skeleton_examples:
                skeleton_examples[skeleton] = originals[idx]

    # Consolidation pass: merge skeletons that share the same "structural
    # signature": the non-wildcard tokens that aren't key=value pairs.
    # This collapses templates that differ only in specific field values
    # (like ino=, dev=, pid=) while keeping structurally different templates
    # separate.
    _KV_RE = re.compile(r"^\w+=")

    def _signature(skel: str) -> tuple[str, ...]:
        """Extract structural tokens: non-wildcard, non-key=value tokens."""
        tokens = skel.split()
        sig = []
        for t in tokens:
            if t == WILDCARD:
                continue
            # Keep key names from key=value but wildcard the value
            if _KV_RE.match(t):
                key = t.split("=", 1)[0]
                sig.append(f"{key}=")
            else:
                sig.append(t)
        return tuple(sig)

    sig_best: dict[tuple[str, ...], str] = {}
    sig_counts: dict[tuple[str, ...], int] = {}
    sig_examples: dict[tuple[str, ...], str] = {}
    for skel, count in skeleton_counts.items():
        sig = _signature(skel)
        if sig not in sig_counts or count > sig_counts[sig]:
            sig_best[sig] = skel
            sig_examples[sig] = skeleton_examples[skel]
        sig_counts[sig] = sig_counts.get(sig, 0) + count

    # Rebuild consolidated skeleton_counts / skeleton_examples.
    skeleton_counts = {sig_best[sig]: sig_counts[sig] for sig in sig_best}
    skeleton_examples = {sig_best[sig]: sig_examples[sig] for sig in sig_best}

    # Filter out rare patterns (one-off messages that add noise).
    min_count = max(2, len(messages) // 10000)
    filtered = {
        skel: skeleton_examples[skel]
        for skel, count in skeleton_counts.items()
        if count >= min_count
    }

    if debug:
        print(
            "Debug: length_groups=%d skeletons=%d consolidated=%d kept=%d (min_count=%d)"
            % (len(by_length), len(sig_best) + sum(1 for _ in []), len(skeleton_counts), len(filtered), min_count),
            file=sys.stderr,
        )

    sorted_templates = sorted(filtered.keys())
    sorted_examples = {t: filtered[t] for t in sorted_templates}
    return sorted_templates, sorted_examples


def _extract_templates(
    input_path: str,
    max_lines: int | None,
    variability_threshold: float,
    message_separator: str | None,
    require_separator: bool,
    separator_mode: str,
    debug: bool,
) -> tuple[list[str], dict[str, str]]:
    messages: list[list[str]] = []
    originals: list[str] = []

    total_lines = 0
    empty_lines = 0
    missing_separator = 0

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
                continue
            normalized = _normalize_message(line)
            messages.append(normalized.split())
            originals.append(original_line)

    if debug:
        print(
            "Debug: total_lines=%d empty_lines=%d processed_lines=%d"
            % (total_lines, empty_lines, len(messages)),
            file=sys.stderr,
        )
        if message_separator:
            print("Debug: missing_separator=%d" % missing_separator, file=sys.stderr)

    return _build_templates(messages, originals, variability_threshold, debug)


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

    # variability_threshold: fraction of unique values at a token position
    # above which the position is marked as variable. Lower = more wildcards.
    # Config file can be JSON: {"variability_threshold": 0.3}
    variability_threshold = 0.3
    if config_path:
        try:
            with open(config_path, "r") as f:
                cfg = json.load(f)
            variability_threshold = float(cfg.get("variability_threshold", variability_threshold))
        except Exception:
            pass

    output_dir = output_dir or _default_output_dir()
    os.makedirs(output_dir, exist_ok=True)

    templates, examples = _extract_templates(
        input_file,
        max_lines,
        variability_threshold,
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
    parser = argparse.ArgumentParser(description="Extract log templates via frequency-based analysis.")
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
        help="Path to JSON config file (e.g., {\"variability_threshold\": 0.3})",
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
