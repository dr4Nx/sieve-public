"""Complex audit query definitions and ground truth."""

from __future__ import annotations

from collections import Counter, defaultdict

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
    is_unit_stop,
)


def _query(
    *,
    query_id: str,
    natural_language: str,
    output_format: list[str],
    output_data_type: list[str],
    rows,
) -> dict:
    return {
        "id": query_id,
        "natural_language": natural_language,
        "category": "multiline",
        "query_type": "select",
        "output_format": output_format,
        "output_data_type": output_data_type,
        "ground_truth": {
            "must_contain": rows,
            "may_contain": rows,
        },
    }


def build_complex_queries(records: list[AuditRecord]) -> list[dict]:
    avc_count_by_host: Counter[str] = Counter()
    perms_by_host: defaultdict[str, set[str]] = defaultdict(set)
    policy_load_by_host: Counter[str] = Counter()
    enforcing_change_by_host: Counter[str] = Counter()
    pam_total: Counter[tuple[str, str]] = Counter()
    pam_failed: Counter[tuple[str, str]] = Counter()
    failed_ssh_by_source: Counter[str] = Counter()
    unit_start_count: Counter[str] = Counter()
    unit_stop_count: Counter[str] = Counter()
    audit_init_by_host: Counter[str] = Counter()
    audit_pid_by_host: Counter[str] = Counter()
    crash_by_exe_sig: Counter[tuple[str, str]] = Counter()

    latest_disable_by_host_bool: dict[tuple[str, str], float] = {}
    boolean_flip_rows: list[list] = []

    for record in records:
        if is_failed_sshd_event(record) and record.source_address:
            failed_ssh_by_source[record.source_address] += 1

        if record.host is None:
            continue

        if is_selinux_denied(record):
            avc_count_by_host[record.host] += 1
            if record.permission:
                # Multi-permission denials like "read write" are split into
                # individual permissions so each is counted as distinct.
                for perm in record.permission.split():
                    perms_by_host[record.host].add(perm)

        if is_policy_loaded(record):
            policy_load_by_host[record.host] += 1

        if is_enforcing_change(record):
            enforcing_change_by_host[record.host] += 1

        if record.pam_action:
            key = (record.host, record.pam_action)
            pam_total[key] += 1
            if record.outcome == "failed":
                pam_failed[key] += 1

        if is_unit_start(record) and record.service_unit:
            unit_start_count[record.service_unit] += 1

        if is_unit_stop(record) and record.service_unit:
            unit_stop_count[record.service_unit] += 1

        if is_audit_initialized(record):
            audit_init_by_host[record.host] += 1

        if is_audit_pid_set(record):
            audit_pid_by_host[record.host] += 1

        if record.executable_path and record.signal_number:
            crash_by_exe_sig[(record.executable_path, record.signal_number)] += 1

        if is_boolean_change(record) and record.host and record.boolean_name and record.event_timestamp is not None:
            key = (record.host, record.boolean_name)
            if record.old_boolean_value == "1" and record.boolean_value == "0":
                latest_disable_by_host_bool[key] = record.event_timestamp
            elif record.old_boolean_value == "0" and record.boolean_value == "1":
                disable_ts = latest_disable_by_host_bool.get(key)
                if disable_ts is not None and disable_ts < record.event_timestamp:
                    boolean_flip_rows.append(
                        [record.host, record.boolean_name, disable_ts, record.event_timestamp]
                    )
                    latest_disable_by_host_bool.pop(key, None)

    avc_rows = [
        [host, avc_count_by_host[host], len(perms_by_host[host])]
        for host in sorted(avc_count_by_host)
    ]
    policy_rows = [
        [
            host,
            policy_load_by_host[host],
            enforcing_change_by_host[host],
        ]
        for host in sorted(set(policy_load_by_host) | set(enforcing_change_by_host))
    ]
    boolean_flip_rows.sort(key=lambda row: (row[0], row[1], row[2], row[3]))
    pam_rows = [
        [host, action, pam_total[(host, action)], pam_failed[(host, action)]]
        for host, action in sorted(pam_total)
    ]
    failed_ssh_rows = [
        [source, failed_ssh_by_source[source]]
        for source in sorted(failed_ssh_by_source)
    ]
    unit_rows = [
        [unit, unit_start_count[unit], unit_stop_count[unit]]
        for unit in sorted(set(unit_start_count) | set(unit_stop_count))
    ]
    audit_host_rows = [
        [host, audit_init_by_host[host], audit_pid_by_host[host]]
        for host in sorted(set(audit_init_by_host) | set(audit_pid_by_host))
    ]
    crash_rows = [
        [exe, signal, count]
        for (exe, signal), count in sorted(crash_by_exe_sig.items())
    ]

    return [
        _query(
            query_id="multiline_1",
            natural_language="For each host, count SELinux AVC denial events and the number of distinct denied permissions.",
            output_format=["host", "avc_denial_count", "distinct_denied_permission_count"],
            output_data_type=["string", "integer", "integer"],
            rows=avc_rows,
        ),
        _query(
            query_id="multiline_2",
            natural_language="For each host, count SELinux policy load events and enforcing mode changes.",
            output_format=["host", "policy_load_count", "enforcing_change_count"],
            output_data_type=["string", "integer", "integer"],
            rows=policy_rows,
        ),
        _query(
            query_id="multiline_3",
            natural_language="Identify hosts and SELinux booleans where the same boolean was changed from enabled to disabled and later changed back to enabled. Return host, boolean_name, disable_event_timestamp, and enable_event_timestamp.",
            output_format=["host", "boolean_name", "disable_event_timestamp", "enable_event_timestamp"],
            output_data_type=["string", "string", "float", "float"],
            rows=boolean_flip_rows,
        ),
        _query(
            query_id="multiline_4",
            natural_language="For each host and PAM action, count total PAM events and how many of those events ended in failure.",
            output_format=["host", "pam_action", "pam_event_count", "failed_pam_event_count"],
            output_data_type=["string", "string", "integer", "integer"],
            rows=pam_rows,
        ),
        _query(
            query_id="multiline_5",
            natural_language="For each source address, count failed SSH authentication attempts recorded by sshd.",
            output_format=["source_address", "failed_ssh_attempt_count"],
            output_data_type=["string", "integer"],
            rows=failed_ssh_rows,
        ),
        _query(
            query_id="multiline_6",
            natural_language="For each systemd service unit, count unit start events and unit stop events.",
            output_format=["service_unit", "unit_start_count", "unit_stop_count"],
            output_data_type=["string", "integer", "integer"],
            rows=unit_rows,
        ),
        _query(
            query_id="multiline_7",
            natural_language="For each host, count audit subsystem initialization events and audit daemon process ID set events.",
            output_format=["host", "audit_initialized_count", "audit_pid_set_count"],
            output_data_type=["string", "integer", "integer"],
            rows=audit_host_rows,
        ),
        _query(
            query_id="multiline_8",
            natural_language="For each executable path and signal number, count crash signal events.",
            output_format=["executable_path", "signal_number", "crash_event_count"],
            output_data_type=["string", "string", "integer"],
            rows=crash_rows,
        ),
    ]
