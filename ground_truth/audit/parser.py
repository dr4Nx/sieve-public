"""Parsing and extraction helpers for audit logs."""

from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path


PREFIX_RE = re.compile(
    r"^(?P<timestamp>\S+\s+\d+\s+\d\d:\d\d:\d\d)\s+"
    r"(?P<host>\S+)\s+"
    r"(?P<process>[^:]+):\s*"
    r"(?P<message>.*)$"
)
PROCESS_RE = re.compile(r"^(?P<name>.+?)\[(?P<pid>\d+)\]$")
AUDIT_RE = re.compile(r"audit\((?P<event_timestamp>[0-9.]+):(?P<event_sequence>\d+)\)")
EVENT_TYPE_RE = re.compile(r"\btype=(\d+)")
OUTCOME_RE = re.compile(r"\bres=([^\s')]+)")
BOOL_RE = re.compile(r"\bbool=([^\s]+)\s+val=([^\s]+)\s+old_val=([^\s]+)")
ENFORCING_RE = re.compile(r"\benforcing=([^\s]+)\s+old_enforcing=([^\s]+)")
AUDIT_PID_RE = re.compile(r"\baudit_pid=([^\s]+)\s+old=([^\s]+)")
SERVICE_UNIT_RE = re.compile(r"msg='unit=([^\s']+)")
PAM_ACTION_RE = re.compile(
    r"op=PAM:(?P<op_action>[A-Za-z_]+)\b|"
    r"PAM:\s*(?P<text_action>session open|session close|[A-Za-z_]+)\b"
)
EXECUTABLE_RE = re.compile(r'exe="([^"]+)"')
SOURCE_ADDR_RE = re.compile(r"\baddr=([^\s']+)")
SOURCE_HOST_RE = re.compile(r"\bhostname=([^\s']+)")
USER_RE = re.compile(r'acct="([^"]+)"')
PERMISSION_RE = re.compile(r"avc:\s+denied\s+\{\s*([^}]+?)\s*\}")
SIGNAL_RE = re.compile(r"\bsig=(\d+)")


@dataclass(frozen=True)
class AuditRecord:
    line_number: int
    raw_line: str
    log_timestamp: str | None
    host: str | None
    process_label: str | None
    process_name: str | None
    process_id: int | None
    message: str
    event_type: str | None
    event_timestamp: float | None
    event_sequence: int | None
    outcome: str | None
    boolean_name: str | None
    boolean_value: str | None
    old_boolean_value: str | None
    enforcing_status: str | None
    old_enforcing_status: str | None
    audit_process_id: str | None
    old_audit_process_id: str | None
    service_unit: str | None
    pam_action: str | None
    executable_path: str | None
    source_address: str | None
    source_host: str | None
    user_name: str | None
    permission: str | None
    signal_number: str | None


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip().strip(",)")
    if value in {"", "?"}:
        return None
    return value


def parse_records(log_path: str | Path) -> list[AuditRecord]:
    records: list[AuditRecord] = []
    with Path(log_path).open(errors="ignore") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            stripped = raw_line.rstrip("\n")
            prefix_match = PREFIX_RE.match(stripped)
            log_timestamp = None
            host = None
            process_label = None
            process_name = None
            process_id = None
            message = stripped
            if prefix_match:
                log_timestamp = prefix_match.group("timestamp")
                host = prefix_match.group("host")
                process_label = prefix_match.group("process")
                message = prefix_match.group("message")
                proc_match = PROCESS_RE.match(process_label)
                if proc_match:
                    process_name = proc_match.group("name")
                    process_id = int(proc_match.group("pid"))
                else:
                    process_name = process_label

            audit_match = AUDIT_RE.search(stripped)
            event_timestamp = None
            event_sequence = None
            if audit_match:
                event_timestamp = float(audit_match.group("event_timestamp"))
                event_sequence = int(audit_match.group("event_sequence"))

            event_type_match = EVENT_TYPE_RE.search(stripped)
            event_type = event_type_match.group(1) if event_type_match else None

            outcome_match = OUTCOME_RE.search(stripped)
            outcome = _clean_optional(outcome_match.group(1)) if outcome_match else None

            bool_match = BOOL_RE.search(stripped)
            boolean_name = boolean_value = old_boolean_value = None
            if bool_match:
                boolean_name = _clean_optional(bool_match.group(1))
                boolean_value = _clean_optional(bool_match.group(2))
                old_boolean_value = _clean_optional(bool_match.group(3))

            enforcing_match = ENFORCING_RE.search(stripped)
            enforcing_status = old_enforcing_status = None
            if enforcing_match:
                enforcing_status = _clean_optional(enforcing_match.group(1))
                old_enforcing_status = _clean_optional(enforcing_match.group(2))

            audit_pid_match = AUDIT_PID_RE.search(stripped)
            audit_process_id = old_audit_process_id = None
            if audit_pid_match:
                audit_process_id = _clean_optional(audit_pid_match.group(1))
                old_audit_process_id = _clean_optional(audit_pid_match.group(2))

            service_unit_match = SERVICE_UNIT_RE.search(stripped)
            service_unit = _clean_optional(service_unit_match.group(1)) if service_unit_match else None

            pam_action_match = PAM_ACTION_RE.search(stripped)
            pam_action = None
            if pam_action_match:
                pam_action = _clean_optional(
                    pam_action_match.group("op_action") or pam_action_match.group("text_action")
                )
            if pam_action is not None:
                pam_action = pam_action.replace(" ", "_")

            executable_match = EXECUTABLE_RE.search(stripped)
            executable_path = _clean_optional(executable_match.group(1)) if executable_match else None

            source_addr_match = SOURCE_ADDR_RE.search(stripped)
            source_address = _clean_optional(source_addr_match.group(1)) if source_addr_match else None

            source_host_match = SOURCE_HOST_RE.search(stripped)
            source_host = _clean_optional(source_host_match.group(1)) if source_host_match else None

            user_match = USER_RE.search(stripped)
            user_name = _clean_optional(user_match.group(1)) if user_match else None

            permission_match = PERMISSION_RE.search(stripped)
            permission = _clean_optional(permission_match.group(1)) if permission_match else None

            signal_match = SIGNAL_RE.search(stripped)
            signal_number = _clean_optional(signal_match.group(1)) if signal_match else None

            records.append(
                AuditRecord(
                    line_number=line_number,
                    raw_line=stripped,
                    log_timestamp=log_timestamp,
                    host=host,
                    process_label=process_label,
                    process_name=process_name,
                    process_id=process_id,
                    message=message,
                    event_type=event_type,
                    event_timestamp=event_timestamp,
                    event_sequence=event_sequence,
                    outcome=outcome,
                    boolean_name=boolean_name,
                    boolean_value=boolean_value,
                    old_boolean_value=old_boolean_value,
                    enforcing_status=enforcing_status,
                    old_enforcing_status=old_enforcing_status,
                    audit_process_id=audit_process_id,
                    old_audit_process_id=old_audit_process_id,
                    service_unit=service_unit,
                    pam_action=pam_action,
                    executable_path=executable_path,
                    source_address=source_address,
                    source_host=source_host,
                    user_name=user_name,
                    permission=permission,
                    signal_number=signal_number,
                )
            )
    return records


def is_selinux_denied(record: AuditRecord) -> bool:
    return "avc:  denied" in record.raw_line or "avc: denied" in record.raw_line


def is_policy_loaded(record: AuditRecord) -> bool:
    return "policy loaded" in record.raw_line


def is_boolean_change(record: AuditRecord) -> bool:
    return record.boolean_name is not None


def is_enforcing_change(record: AuditRecord) -> bool:
    return record.enforcing_status is not None


def is_audit_initialized(record: AuditRecord) -> bool:
    return "initialized" in record.raw_line and record.event_type == "2000"


def is_audit_pid_set(record: AuditRecord) -> bool:
    return record.audit_process_id is not None


def is_failed_sshd_event(record: AuditRecord) -> bool:
    return record.executable_path == "/usr/sbin/sshd" and record.outcome == "failed"


def is_pam_session_open(record: AuditRecord) -> bool:
    return record.pam_action == "session_open"


def is_unit_start(record: AuditRecord) -> bool:
    return (record.event_type == "1130" or "SERVICE_START" in record.raw_line) and record.service_unit is not None


def is_unit_stop(record: AuditRecord) -> bool:
    return (record.event_type == "1131" or "SERVICE_STOP" in record.raw_line) and record.service_unit is not None
