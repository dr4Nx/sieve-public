"""Parsing and extraction helpers for sshd logs."""

from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path


SYSLOG_RE = re.compile(
    r"^(?P<timestamp>[A-Z][a-z]{2}\s+\d+\s+\d\d:\d\d:\d\d)\s+"
    r"(?P<host>\S+)\s+"
    r"(?P<process>[^:]+):\s*"
    r"(?P<message>.*)$"
)
PROCESS_RE = re.compile(r"^(?P<name>.+?)\[(?P<pid>\d+)\]$")
ACCEPTED_RE = re.compile(
    r"Accepted\s+(?P<method>\S+)\s+for\s+(?P<user>\S+)\s+from\s+(?P<ip>\S+)\s+port\s+(?P<port>\d+)"
)
AUTH_FAILURE_RE = re.compile(
    r"authentication failure.*?rhost=(?P<rhost>\S+)(?:.*?user=(?P<user>\S+))?"
)
FAILED_PASSWORD_RE = re.compile(
    r"Failed password for (?:invalid user )?(?P<user>\S+) from (?P<ip>\S+) port (?P<port>\d+)"
)
INVALID_USER_RE = re.compile(
    r"Invalid user (?P<user>\S+) from (?P<ip>\S+)"
)
SESSION_OPENED_RE = re.compile(
    r"(?:pam_unix\(sshd:session\)|session) opened for user (?P<user>\S+)"
)
SESSION_CLOSED_RE = re.compile(
    r"(?:pam_unix\(sshd:session\)|session) closed for user (?P<user>\S+)"
)
DISCONNECT_RE = re.compile(
    r"Received disconnect from (?P<ip>\S+)(?::.*?:\s*(?P<reason>.+))?"
)
LISTENING_RE = re.compile(
    r"Server listening on (?P<addr>\S+) port (?P<port>\d+)"
)
CHECK_PASS_RE = re.compile(r"check pass; user unknown")
DEPRECATED_RE = re.compile(r"Deprecated option (?P<option>\S+)")
KEY_FINGERPRINT_RE = re.compile(
    r"(?:RSA|DSA|ECDSA|ED25519)\s+(?P<fingerprint>[0-9a-f:]+|SHA256:\S+)"
)
SUBSYSTEM_RE = re.compile(r"subsystem request for (?P<subsystem>\S+)")


@dataclass(frozen=True)
class SshdRecord:
    line_number: int
    raw_line: str
    timestamp_text: str
    host: str
    process_label: str
    process_name: str
    process_id: int | None
    message: str


def parse_records(log_path: str | Path) -> list[SshdRecord]:
    records: list[SshdRecord] = []
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
                SshdRecord(
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

def is_accepted_auth(record: SshdRecord) -> bool:
    return "Accepted " in record.message

def is_accepted_password(record: SshdRecord) -> bool:
    return "Accepted password" in record.message

def is_accepted_publickey(record: SshdRecord) -> bool:
    return "Accepted publickey" in record.message

def is_auth_failure(record: SshdRecord) -> bool:
    return "authentication failure" in record.message

def is_failed_password(record: SshdRecord) -> bool:
    return "Failed password" in record.message

def is_invalid_user(record: SshdRecord) -> bool:
    return "Invalid user" in record.message

def is_session_opened(record: SshdRecord) -> bool:
    return "session opened" in record.message

def is_session_closed(record: SshdRecord) -> bool:
    return "session closed" in record.message

def is_disconnect(record: SshdRecord) -> bool:
    """Broad: any disconnect, connection closed, or connection reset."""
    msg = record.message.lower()
    return "disconnect" in msg or "connection closed" in msg or "connection reset" in msg

def is_server_listening(record: SshdRecord) -> bool:
    return "Server listening" in record.message

def is_check_pass_unknown(record: SshdRecord) -> bool:
    return "check pass; user unknown" in record.message

def is_deprecated_option(record: SshdRecord) -> bool:
    return "Deprecated option" in record.message

def is_received_signal(record: SshdRecord) -> bool:
    return "Received signal" in record.message


def is_any_auth_failure(record: SshdRecord) -> bool:
    """Broad failure: PAM auth failure, Failed password, or Invalid user."""
    return ("authentication failure" in record.message or
            "Failed password" in record.message or
            "Invalid user" in record.message)


def extract_any_failure_info(message: str) -> dict | None:
    """Extract source and user from any failure type."""
    if "authentication failure" in message:
        m = AUTH_FAILURE_RE.search(message)
        if m:
            return {"rhost": m.group("rhost"), "user": m.group("user")}
    if "Failed password" in message:
        m = FAILED_PASSWORD_RE.search(message)
        if m:
            return {"rhost": m.group("ip"), "user": m.group("user")}
    if "Invalid user" in message:
        m = INVALID_USER_RE.search(message)
        if m:
            return {"rhost": m.group("ip"), "user": m.group("user")}
    return None


# ---------------------------------------------------------------------------
# Extractors
# ---------------------------------------------------------------------------

def extract_accepted_info(message: str) -> dict | None:
    m = ACCEPTED_RE.search(message)
    if m:
        return {"method": m.group("method"), "user": m.group("user"),
                "ip": m.group("ip"), "port": int(m.group("port"))}
    return None

def extract_auth_failure_info(message: str) -> dict | None:
    m = AUTH_FAILURE_RE.search(message)
    if m:
        return {"rhost": m.group("rhost"), "user": m.group("user")}
    return None

def extract_key_fingerprint(message: str) -> str | None:
    m = KEY_FINGERPRINT_RE.search(message)
    return m.group("fingerprint") if m else None

def extract_listening_port(message: str) -> int | None:
    m = LISTENING_RE.search(message)
    return int(m.group("port")) if m else None

def extract_disconnect_ip(message: str) -> str | None:
    m = DISCONNECT_RE.search(message)
    return m.group("ip") if m else None
