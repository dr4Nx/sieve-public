"""Build Puppet query datasets and ground truth files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

if __package__ in {None, ""}:
    import sys

    ROOT = Path(__file__).resolve().parents[2]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from ground_truth.puppet.parser import load_template_fields, parse_records
    from ground_truth.puppet.queries_complex import build_complex_queries
    from ground_truth.puppet.queries_simple import build_simple_queries
else:
    from .parser import load_template_fields, parse_records
    from .queries_complex import build_complex_queries
    from .queries_simple import build_simple_queries


DEFAULT_LOG_FILE = "data/logs/puppet"
DEFAULT_TEMPLATE_FILE = "templates/puppet.json"
DEFAULT_SIMPLE_OUTPUT = "queries/puppet_simple.json"
DEFAULT_COMPLEX_OUTPUT = "queries/puppet_complex.json"
REQUIRED_TEMPLATE_FIELDS = {
    "PROCESS_ID",
    "RESOURCE_IDENTIFIER",
    "CONFIGURATION_VERSION",
    "DURATION",
    "EVENT_COUNT",
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Puppet query JSON with ground truth.")
    parser.add_argument("--log-file", default=DEFAULT_LOG_FILE, help="Path to Puppet log file.")
    parser.add_argument(
        "--template-file",
        default=DEFAULT_TEMPLATE_FILE,
        help="Path to Puppet template JSON.",
    )
    parser.add_argument(
        "--simple-output",
        default=DEFAULT_SIMPLE_OUTPUT,
        help="Output path for simple Puppet queries JSON.",
    )
    parser.add_argument(
        "--complex-output",
        default=DEFAULT_COMPLEX_OUTPUT,
        help="Output path for complex Puppet queries JSON.",
    )
    return parser.parse_args()


def _validate_templates(template_file: str | Path) -> None:
    fields = load_template_fields(template_file)
    missing = sorted(REQUIRED_TEMPLATE_FIELDS - fields)
    if missing:
        raise ValueError(
            f"Template catalog {template_file} is missing required Puppet fields: {', '.join(missing)}"
        )


def _write_json(path: str | Path, obj) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(obj, indent=2) + "\n")


def main() -> None:
    args = _parse_args()
    _validate_templates(args.template_file)
    records = parse_records(args.log_file)
    simple_queries = build_simple_queries(records)
    complex_queries = build_complex_queries(records)
    _write_json(args.simple_output, simple_queries)
    _write_json(args.complex_output, complex_queries)
    print(f"Wrote {len(simple_queries)} simple queries to {args.simple_output}")
    print(f"Wrote {len(complex_queries)} complex queries to {args.complex_output}")


if __name__ == "__main__":
    main()
