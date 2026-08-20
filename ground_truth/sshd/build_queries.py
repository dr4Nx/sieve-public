"""Build sshd query datasets and ground truth files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

if __package__ in {None, ""}:
    import sys
    ROOT = Path(__file__).resolve().parents[2]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from ground_truth.sshd.parser import parse_records
    from ground_truth.sshd.queries_complex import build_complex_queries
    from ground_truth.sshd.queries_simple import build_simple_queries
else:
    from .parser import parse_records
    from .queries_complex import build_complex_queries
    from .queries_simple import build_simple_queries


DEFAULT_LOG_FILE = "data/logs/sshd"
DEFAULT_SIMPLE_OUTPUT = "queries/sshd_simple.json"
DEFAULT_COMPLEX_OUTPUT = "queries/sshd_complex.json"


def _write_json(path: str | Path, obj) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(obj, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build sshd query JSON with ground truth.")
    parser.add_argument("--log-file", default=DEFAULT_LOG_FILE)
    parser.add_argument("--simple-output", default=DEFAULT_SIMPLE_OUTPUT)
    parser.add_argument("--complex-output", default=DEFAULT_COMPLEX_OUTPUT)
    args = parser.parse_args()

    records = parse_records(args.log_file)
    simple_queries = build_simple_queries(records)
    complex_queries = build_complex_queries(records)
    _write_json(args.simple_output, simple_queries)
    _write_json(args.complex_output, complex_queries)
    print(f"Parsed {len(records)} sshd records")
    print(f"Wrote {len(simple_queries)} simple queries to {args.simple_output}")
    print(f"Wrote {len(complex_queries)} complex queries to {args.complex_output}")


if __name__ == "__main__":
    main()
