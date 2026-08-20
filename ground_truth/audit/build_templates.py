"""Build templates/audit.json from parsed audit output."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


DEFAULT_PARSED_FILE = "data/parsed_logs/audit.json"
DEFAULT_OUTPUT = "templates/audit.json"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build templates/audit.json from parsed audit data.")
    parser.add_argument("--parsed-file", default=DEFAULT_PARSED_FILE, help="Path to parsed audit JSON.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Path to write templates/audit.json.")
    parser.add_argument("--examples-per-template", type=int, default=3, help="Max examples per template.")
    return parser.parse_args()


def build_template_catalog(parsed_file: str | Path, output: str | Path, examples_per_template: int = 1) -> None:
    parsed = json.loads(Path(parsed_file).read_text())
    source_templates: dict[str, dict] = parsed["templates"]
    ordered_ids = sorted(source_templates, key=lambda value: int(value))
    templates = [source_templates[template_id]["template"] for template_id in ordered_ids]

    examples_by_template_id: dict[str, str] = {}
    for entry in parsed["entries"]:
        for template_id in entry.get("templates", []):
            template_id = str(template_id)
            if template_id not in source_templates or template_id in examples_by_template_id:
                continue
            content = entry.get("content")
            if content:
                examples_by_template_id[template_id] = content

    examples = {
        source_templates[template_id]["template"]: examples_by_template_id.get(template_id, "")
        for template_id in ordered_ids
    }

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps({"templates": templates, "examples": examples}, indent=2) + "\n")


def main() -> None:
    args = _parse_args()
    build_template_catalog(args.parsed_file, args.output, args.examples_per_template)
    print(f"Wrote template catalog to {args.output}")


if __name__ == "__main__":
    main()
