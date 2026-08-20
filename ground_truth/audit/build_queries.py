"""Build audit query datasets and ground truth files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

if __package__ in {None, ""}:
    import sys

    ROOT = Path(__file__).resolve().parents[2]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from ground_truth.audit.build_templates import build_template_catalog
    from ground_truth.audit.parser import parse_records
    from ground_truth.audit.queries_complex import build_complex_queries
    from ground_truth.audit.queries_simple import build_simple_queries
else:
    from .build_templates import build_template_catalog
    from .parser import parse_records
    from .queries_complex import build_complex_queries
    from .queries_simple import build_simple_queries


DEFAULT_LOG_FILE = "data/logs/audit"
DEFAULT_PARSED_FILE = "data/parsed_logs/audit.json"
DEFAULT_TEMPLATE_FILE = "templates/audit.json"
DEFAULT_SIMPLE_OUTPUT = "queries/audit_simple.json"
DEFAULT_COMPLEX_OUTPUT = "queries/audit_complex.json"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build audit query JSON with ground truth.")
    parser.add_argument("--log-file", default=DEFAULT_LOG_FILE, help="Path to audit log file.")
    parser.add_argument("--parsed-file", default=DEFAULT_PARSED_FILE, help="Path to parsed audit JSON.")
    parser.add_argument("--template-file", default=DEFAULT_TEMPLATE_FILE, help="Path to audit template JSON.")
    parser.add_argument("--simple-output", default=DEFAULT_SIMPLE_OUTPUT, help="Output path for simple audit queries.")
    parser.add_argument("--complex-output", default=DEFAULT_COMPLEX_OUTPUT, help="Output path for complex audit queries.")
    parser.add_argument("--examples-per-template", type=int, default=3, help="Max examples per template.")
    return parser.parse_args()


def _validate_template_shape(template_file: str | Path) -> None:
    obj = json.loads(Path(template_file).read_text())
    if not isinstance(obj, dict) or "templates" not in obj or "examples" not in obj:
        raise ValueError(f"{template_file} does not have the expected template catalog shape")
    if not isinstance(obj["templates"], list) or not isinstance(obj["examples"], dict):
        raise ValueError(f"{template_file} has invalid template catalog types")


def _write_json(path: str | Path, obj) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(obj, indent=2) + "\n")


def main() -> None:
    args = _parse_args()
    build_template_catalog(args.parsed_file, args.template_file, args.examples_per_template)
    _validate_template_shape(args.template_file)
    records = parse_records(args.log_file)
    simple_queries = build_simple_queries(records)
    complex_queries = build_complex_queries(records)
    _write_json(args.simple_output, simple_queries)
    _write_json(args.complex_output, complex_queries)
    print(f"Wrote template catalog to {args.template_file}")
    print(f"Wrote {len(simple_queries)} simple queries to {args.simple_output}")
    print(f"Wrote {len(complex_queries)} complex queries to {args.complex_output}")


if __name__ == "__main__":
    main()
