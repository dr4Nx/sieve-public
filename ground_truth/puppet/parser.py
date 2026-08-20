"""Parsing and extraction helpers for Puppet syslog records."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from pathlib import Path


SYSLOG_RE = re.compile(
    r"^(?P<timestamp>[A-Z][a-z]{2}\s+\d+\s+\d\d:\d\d:\d\d)\s+"
    r"(?P<host>\S+)\s+"
    r"(?P<process>[^:]+):\s*"
    r"(?P<message>.*)$"
)
PROCESS_RE = re.compile(r"^(?P<name>.+?)\[(?P<pid>\d+)\]$")
RESOURCE_RE = re.compile(r"^\((?P<resource>[^)]+)\)")
MODULE_RE = re.compile(r"/Stage\[main\]/(?P<module>[^/\]]+)")
CONFIG_VERSION_RE = re.compile(r"Applying configuration version '?([^']+)'?")
DURATION_RE = re.compile(r"Finished catalog run in ([0-9]+(?:\.[0-9]+)?) seconds")
EVENT_COUNT_RE = re.compile(r"Triggered 'refresh' from (\d+) events")
SCHEDULE_RE = re.compile(r"Scheduling refresh of (?P<target>.+)$")
CHECKSUM_RE = re.compile(r"Computing checksum on file (?P<path>\S+)")


@dataclass(frozen=True)
class PuppetRecord:
    line_number: int
    raw_line: str
    timestamp_text: str
    host: str
    process_label: str
    process_name: str
    process_id: int | None
    message: str

    @property
    def stream_key(self) -> tuple[str, int] | None:
        if self.process_id is None:
            return None
        return (self.host, self.process_id)


def parse_records(log_path: str | Path) -> list[PuppetRecord]:
    records: list[PuppetRecord] = []
    with Path(log_path).open() as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            stripped = raw_line.rstrip("\n")
            match = SYSLOG_RE.match(stripped)
            if not match:
                continue
            process_label = match.group("process")
            process_name = process_label
            process_id = None
            process_match = PROCESS_RE.match(process_label)
            if process_match:
                process_name = process_match.group("name")
                process_id = int(process_match.group("pid"))
            records.append(
                PuppetRecord(
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


def load_template_fields(template_path: str | Path) -> set[str]:
    obj = json.loads(Path(template_path).read_text())
    fields: set[str] = set()
    for template in obj.get("templates", []):
        for part in template.split("<")[1:]:
            fields.add(part.split(">", 1)[0])
    return fields


def extract_resource_identifier(message: str) -> str | None:
    match = RESOURCE_RE.match(message)
    if match:
        return match.group("resource")
    return None


def extract_top_level_module(message: str) -> str | None:
    match = MODULE_RE.search(message)
    if match:
        return match.group("module")
    return None


def extract_configuration_version(message: str) -> str | None:
    match = CONFIG_VERSION_RE.search(message)
    if match:
        return match.group(1)
    return None


def extract_duration_seconds(message: str) -> float | None:
    match = DURATION_RE.search(message)
    if match:
        return float(match.group(1))
    return None


def extract_event_count(message: str) -> int | None:
    match = EVENT_COUNT_RE.search(message)
    if match:
        return int(match.group(1))
    return None


def extract_refresh_target(message: str) -> str | None:
    match = SCHEDULE_RE.search(message)
    if match:
        return match.group("target")
    return None


def extract_checksum_path(message: str) -> str | None:
    match = CHECKSUM_RE.search(message)
    if match:
        return match.group("path")
    return None


def is_disabled_run(record: PuppetRecord) -> bool:
    message = record.message.lower()
    return (
        "administratively disabled" in message
        or "disabling puppet." in message
        or message == "disabling puppet"
    )


def is_enabled_run(record: PuppetRecord) -> bool:
    return "enabling puppet." in record.message.lower()


def is_node_definition_failure(record: PuppetRecord) -> bool:
    return "Unable to fetch my node definition" in record.message


def is_catalog_retrieval_failure(record: PuppetRecord) -> bool:
    return "Could not retrieve catalog from remote server" in record.message


def is_cached_catalog(record: PuppetRecord) -> bool:
    return "Using cached catalog" in record.message


def is_report_failure(record: PuppetRecord) -> bool:
    return "Could not send report" in record.message


def is_skipped_dependency(record: PuppetRecord) -> bool:
    return "Skipping because of failed dependencies" in record.message


def is_command_missing(record: PuppetRecord) -> bool:
    return "command not found" in record.message


def is_certificate_failure(record: PuppetRecord) -> bool:
    return "certificate verify failed" in record.message


def is_refresh_trigger(record: PuppetRecord) -> bool:
    return "Triggered 'refresh' from" in record.message


def is_refresh_schedule(record: PuppetRecord) -> bool:
    return "Scheduling refresh of" in record.message


def is_configuration_applied(record: PuppetRecord) -> bool:
    return "Applying configuration version" in record.message


def is_finished_run(record: PuppetRecord) -> bool:
    return "Finished catalog run in" in record.message


def classify_error_family(record: PuppetRecord) -> str | None:
    message = record.message.lower()
    if "certificate verify failed" in message:
        return "certificate_verify_failed"
    if "getaddrinfo" in message:
        return "getaddrinfo"
    if "network is unreachable" in message:
        return "network_unreachable"
    if "no child processes" in message:
        return "no_child_processes"
    if "command not found" in message:
        return "command_not_found"
    if "timed out after" in message:
        return "timeout"
    if "error downloading packages" in message:
        return "error_downloading_packages"
    return None
