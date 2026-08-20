"""Simple audit query definitions and ground truth."""

from __future__ import annotations

from .parser import (
    AuditRecord,
    is_audit_initialized,
    is_audit_pid_set,
    is_boolean_change,
    is_enforcing_change,
    is_failed_sshd_event,
    is_policy_loaded,
    is_pam_session_open,
    is_selinux_denied,
    is_unit_start,
)


def _entry(
    *,
    query_id: str,
    natural_language: str,
    query_type: str,
    description: str,
    must_contain,
    output_format: list[str],
    output_data_type: list[str] | None = None,
) -> dict:
    entry = {
        "id": query_id,
        "natural_language": natural_language,
        "category": "matryoshka",
        "query_type": query_type,
        "description": description,
        "ground_truth": {
            "must_contain": must_contain,
            "may_contain": must_contain,
        },
        "output_format": output_format,
    }
    if output_data_type:
        entry["output_data_type"] = output_data_type
    return entry


def build_simple_queries(records: list[AuditRecord]) -> dict[str, dict]:
    avc_denied_lines = [record.raw_line for record in records if is_selinux_denied(record)]
    policy_loaded_lines = [record.raw_line for record in records if is_policy_loaded(record)]
    boolean_change_lines = [record.raw_line for record in records if is_boolean_change(record)]
    enforcing_change_lines = [record.raw_line for record in records if is_enforcing_change(record)]
    audit_initialized_lines = [record.raw_line for record in records if is_audit_initialized(record)]
    audit_pid_lines = [record.raw_line for record in records if is_audit_pid_set(record)]
    ssh_failed_lines = [record.raw_line for record in records if is_failed_sshd_event(record)]
    pam_open_lines = [record.raw_line for record in records if is_pam_session_open(record)]
    unit_start_lines = [record.raw_line for record in records if is_unit_start(record)]

    denial_hosts = sorted({record.host for record in records if is_selinux_denied(record) and record.host})
    boolean_names = sorted({record.boolean_name for record in records if record.boolean_name})
    service_units = sorted({record.service_unit for record in records if is_unit_start(record) and record.service_unit})

    return {
        "audit_query_1": _entry(
            query_id="audit_query_1",
            natural_language="Find audit log lines that report SELinux AVC denials.",
            query_type="where",
            description="Raw-line query for SELinux denial events.",
            must_contain=avc_denied_lines,
            output_format=["raw_line"],
        ),
        "audit_query_2": _entry(
            query_id="audit_query_2",
            natural_language="Find audit log lines that show SELinux policy loads.",
            query_type="where",
            description="Raw-line query for policy load events.",
            must_contain=policy_loaded_lines,
            output_format=["raw_line"],
        ),
        "audit_query_3": _entry(
            query_id="audit_query_3",
            natural_language="Find audit log lines that show SELinux boolean changes.",
            query_type="where",
            description="Raw-line query for SELinux boolean changes.",
            must_contain=boolean_change_lines,
            output_format=["raw_line"],
        ),
        "audit_query_4": _entry(
            query_id="audit_query_4",
            natural_language="Find audit log lines that show SELinux enforcing mode changes.",
            query_type="where",
            description="Raw-line query for enforcing-mode changes.",
            must_contain=enforcing_change_lines,
            output_format=["raw_line"],
        ),
        "audit_query_5": _entry(
            query_id="audit_query_5",
            natural_language="Find audit log lines showing kernel audit initialization events.",
            query_type="where",
            description="Raw-line query for audit initialization events.",
            must_contain=audit_initialized_lines,
            output_format=["raw_line"],
        ),
        "audit_query_6": _entry(
            query_id="audit_query_6",
            natural_language="Find audit log lines that record the audit daemon process ID being set or changed.",
            query_type="where",
            description="Raw-line query for audit_pid changes.",
            must_contain=audit_pid_lines,
            output_format=["raw_line"],
        ),
        "audit_query_7": _entry(
            query_id="audit_query_7",
            natural_language="Find audit log lines for failed SSH authentication attempts handled by sshd.",
            query_type="where",
            description="Raw-line query for failed SSH events.",
            must_contain=ssh_failed_lines,
            output_format=["raw_line"],
        ),
        "audit_query_8": _entry(
            query_id="audit_query_8",
            natural_language="Find audit log lines for PAM session open events.",
            query_type="where",
            description="Raw-line query for PAM session-open events.",
            must_contain=pam_open_lines,
            output_format=["raw_line"],
        ),
        "audit_query_9": _entry(
            query_id="audit_query_9",
            natural_language="Find audit log lines for systemd unit start events that name a service unit.",
            query_type="where",
            description="Raw-line query for unit start events.",
            must_contain=unit_start_lines,
            output_format=["raw_line"],
        ),
        "audit_select_1": _entry(
            query_id="audit_select_1",
            natural_language="Find the hosts that logged SELinux AVC denials.",
            query_type="select",
            description="Select query for hosts with AVC denials.",
            must_contain=[[host] for host in denial_hosts],
            output_format=["host"],
            output_data_type=["string"],
        ),
        "audit_select_2": _entry(
            query_id="audit_select_2",
            natural_language="Find the SELinux boolean names that were changed.",
            query_type="select",
            description="Select query for changed SELinux booleans.",
            must_contain=[[name] for name in boolean_names],
            output_format=["boolean_name"],
            output_data_type=["string"],
        ),
        "audit_select_3": _entry(
            query_id="audit_select_3",
            natural_language="Find the service unit names reported in systemd unit start events.",
            query_type="select",
            description="Select query for systemd unit names.",
            must_contain=[[unit] for unit in service_units],
            output_format=["service_unit"],
            output_data_type=["string"],
        ),
    }
