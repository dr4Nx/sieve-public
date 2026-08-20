"""Parsing and extraction helpers for cron logs."""

from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path


# Cron uses ISO-8601 timestamps: 2017-07-14T03:15:01.576215-04:00
SYSLOG_RE = re.compile(
    r"^(?P<timestamp>\S+)\s+"
    r"(?P<host>\S+)\s+"
    r"(?P<process>[^:]+):\s*"
    r"(?P<message>.*)$"
)
PROCESS_RE = re.compile(r"^(?P<name>.+?)\[(?P<pid>\d+)\]$")
CMD_RE = re.compile(r"\((?P<user>\S+)\)\s+CMD\s+\(\s*(?P<command>.+?)\s*\)$")
SESSION_OPENED_RE = re.compile(
    r"pam_unix\(crond:session\):\s+session opened for user (?P<user>\S+)"
)
SESSION_CLOSED_RE = re.compile(
    r"pam_unix\(crond:session\):\s+session closed for user (?P<user>\S+)"
)
SCALING_RE = re.compile(r"RANDOM_DELAY will be scaled with factor (?P<factor>\d+)%")
INOTIFY_RE = re.compile(r"running with inotify support")


@dataclass(frozen=True)
class CronRecord:
    line_number: int
    raw_line: str
    timestamp_text: str
    host: str
    process_label: str
    process_name: str
    process_id: int | None
    message: str


def parse_records(log_path: str | Path) -> list[CronRecord]:
    records: list[CronRecord] = []
    with Path(log_path).open(errors="ignore") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            stripped = raw_line.rstrip("\n")
            match = SYSLOG_RE.match(stripped)
            if not match:
                continue
            process_label = match.group("process")
            process_name = process_label
            process_id = None
            proc_match = PROCESS_RE.match(process_label)
            if proc_match:
                process_name = proc_match.group("name")
                process_id = int(proc_match.group("pid"))
            records.append(
                CronRecord(
                    line_number=line_number,
                    raw_line=stripped,
                    timestamp_text=match.group("timestamp"),
                    host=match.group("host"),
                    process_label=process_label,
                    process_name=process_name,
                    process_id=process_id,
                    message=match.group("message"),
                )
            )
    return records


# ---------------------------------------------------------------------------
# Predicates
# ---------------------------------------------------------------------------

def is_cmd_execution(record: CronRecord) -> bool:
    return "CMD" in record.message and "(" in record.message

def is_session_opened(record: CronRecord) -> bool:
    return "session opened" in record.message

def is_session_closed(record: CronRecord) -> bool:
    return "session closed" in record.message

def is_scaling_factor(record: CronRecord) -> bool:
    return "RANDOM_DELAY will be scaled" in record.message

def is_inotify(record: CronRecord) -> bool:
    return "inotify support" in record.message


# ---------------------------------------------------------------------------
# Extractors
# ---------------------------------------------------------------------------

def extract_cmd_info(message: str) -> dict | None:
    m = CMD_RE.search(message)
    if m:
        return {"user": m.group("user"), "command": m.group("command").strip()}
    return None

def extract_session_user(message: str) -> str | None:
    m = SESSION_OPENED_RE.search(message)
    if m:
        return m.group("user")
    m = SESSION_CLOSED_RE.search(message)
    if m:
        return m.group("user")
    return None

def extract_scaling_factor(message: str) -> int | None:
    m = SCALING_RE.search(message)
    return int(m.group("factor")) if m else None

def extract_timestamp_date(timestamp_text: str) -> str | None:
    """Extract the date portion (YYYY-MM-DD) from an ISO timestamp."""
    m = re.match(r"(\d{4}-\d{2}-\d{2})", timestamp_text)
    return m.group(1) if m else None

def extract_timestamp_hour(timestamp_text: str) -> int | None:
    """Extract the hour from an ISO timestamp."""
    m = re.search(r"T(\d{2}):", timestamp_text)
    return int(m.group(1)) if m else None
