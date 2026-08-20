#!/usr/bin/env python3
"""Measure execution-only timing for final Drain3-context scripts."""

import argparse
import gzip
import json
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path


ARTIFACT = Path(__file__).resolve().parents[1]
REPORT_DIR = ARTIFACT / "results" / "generated_code"
REPORT_RE = re.compile(
    r"^(?P<log>audit|cron|dhcp|puppet|sshd)_(?P<tier>simple|complex)_drain3\\.txt$"
)
ID_RE = re.compile(
    r"^ID: (?P<id>[^|]+) \\| type: (?P<query_type>[^|]+) \\| query:",
    re.MULTILINE,
)


def percentile(values: list[float], q: float) -> float:
    values = sorted(values)
    if not values:
        raise ValueError("empty values")
    pos = (len(values) - 1) * q
    lo, hi = int(pos), min(int(pos) + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (pos - lo)


def decompress_logs(log_dir: Path) -> dict[str, tuple[Path, int]]:
    log_dir.mkdir(parents=True, exist_ok=True)
    logs: dict[str, tuple[Path, int]] = {}
    for compressed in sorted((ARTIFACT / "data" / "logs").glob("*.gz")):
        name = compressed.stem
        destination = log_dir / name
        if not destination.exists():
            with gzip.open(compressed, "rb") as source, destination.open("wb") as target:
                while chunk := source.read(1024 * 1024):
                    target.write(chunk)
        with destination.open("rb") as log_file:
            logs[name] = (destination, sum(1 for _ in log_file))
    return logs


def summarize(rows: list[dict]) -> dict:
    elapsed = [row["elapsed_seconds"] for row in rows]
    throughput = [row["lines_per_second"] for row in rows]
    return {
        "n_queries": len(rows),
        "mean_execution_seconds": statistics.mean(elapsed),
        "median_execution_seconds": statistics.median(elapsed),
        "p95_execution_seconds": percentile(elapsed, 0.95),
        "mean_lines_per_second": statistics.mean(throughput),
        "median_lines_per_second": statistics.median(throughput),
        "p05_lines_per_second": percentile(throughput, 0.05),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--workdir",
        type=Path,
        default=Path("/tmp/sieve-execution-throughput-drain3"),
        help="Directory for decompressed logs, extracted scripts, and timing output.",
    )
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()

    log_dir = args.workdir / "logs"
    script_dir = args.workdir / "scripts"
    records_path = args.workdir / "records.jsonl"
    summary_path = args.workdir / "summary.json"
    logs = decompress_logs(log_dir)
    script_dir.mkdir(parents=True, exist_ok=True)

    records = []
    completed = set()
    if records_path.exists():
        for line in records_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                record = json.loads(line)
                records.append(record)
                completed.add((record["log"], record["tier"], record["query_id"]))

    for report in sorted(REPORT_DIR.glob("*_drain3.txt")):
        match = REPORT_RE.match(report.name)
        if not match:
            continue
        log_name, tier = match.group("log"), match.group("tier")
        log_path, lines = logs[log_name]
        text = report.read_text(encoding="utf-8")
        starts = list(ID_RE.finditer(text))
        for index, start in enumerate(starts):
            block = text[start.start() : starts[index + 1].start() if index + 1 < len(starts) else len(text)]
            query_id = start.group("id").strip()
            key = (log_name, tier, query_id)
            if key in completed:
                continue
            command_start = block.find("\n  command: ")
            if command_start < 0:
                continue
            command_start += len("\n  command: ")
            command_end = block.find("\n  precision=", command_start)
            if command_end < 0:
                raise RuntimeError(f"Could not find the end of {key}'s generated code")
            script_path = script_dir / f"{log_name}_{tier}_{query_id}.py"
            script_path.write_text(block[command_start:command_end].rstrip() + "\n", encoding="utf-8")
            started = time.perf_counter()
            try:
                result = subprocess.run(
                    [sys.executable, str(script_path), str(log_path)],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=args.timeout,
                )
                elapsed = time.perf_counter() - started
                status = "ok" if result.returncode == 0 else f"exit_{result.returncode}"
                stderr = (result.stderr or "").strip()[:500]
            except subprocess.TimeoutExpired:
                elapsed, status, stderr = args.timeout, "timeout", ""
            record = {
                "log": log_name,
                "tier": tier,
                "query_id": query_id,
                "lines": lines,
                "elapsed_seconds": elapsed,
                "lines_per_second": lines / elapsed if elapsed else None,
                "status": status,
                "stderr": stderr,
            }
            records.append(record)
            completed.add(key)
            with records_path.open("a", encoding="utf-8") as output:
                output.write(json.dumps(record) + "\n")

    successful = [record for record in records if record["status"] == "ok"]
    if len(successful) != len(records):
        failures = [record for record in records if record["status"] != "ok"]
        raise RuntimeError(f"{len(failures)}/{len(records)} scripts failed: {failures[:3]}")
    summary = {
        "method": "Final Drain3-context scripts executed once on decompressed original logs with stdout discarded; execution-only wall-clock timing.",
        "all": summarize(successful),
        "simple": summarize([record for record in successful if record["tier"] == "simple"]),
        "complex": summarize([record for record in successful if record["tier"] == "complex"]),
        "per_query": records,
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in summary.items() if key != "per_query"}, indent=2))


if __name__ == "__main__":
    main()
