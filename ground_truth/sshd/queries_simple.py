"""Simple sshd query definitions and ground truth (security-focused)."""

from __future__ import annotations

from .parser import (
    SshdRecord,
    is_accepted_auth,
    is_accepted_password,
    is_accepted_publickey,
    is_any_auth_failure,
    is_auth_failure,
    is_check_pass_unknown,
    is_deprecated_option,
    is_disconnect,
    is_failed_password,
    is_invalid_user,
    is_server_listening,
    is_session_closed,
    is_session_opened,
    extract_accepted_info,
    extract_any_failure_info,
    extract_auth_failure_info,
    extract_key_fingerprint,
    extract_listening_port,
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


def build_simple_queries(records: list[SshdRecord]) -> dict[str, dict]:
    # Where queries: raw line filters
    # Use broad failure definition for auth failures
    auth_failure_lines = [r.raw_line for r in records if is_any_auth_failure(r)]
    accepted_password_lines = [r.raw_line for r in records if is_accepted_password(r)]
    accepted_publickey_lines = [r.raw_line for r in records if is_accepted_publickey(r)]
    # Broad invalid: "Invalid user" + "check pass; user unknown"
    invalid_user_lines = [r.raw_line for r in records
                          if is_invalid_user(r) or is_check_pass_unknown(r)]
    session_opened_lines = [r.raw_line for r in records if is_session_opened(r)]
    session_closed_lines = [r.raw_line for r in records if is_session_closed(r)]
    # Broad disconnect: disconnect, connection closed, connection reset
    disconnect_lines = [r.raw_line for r in records if is_disconnect(r)]
    listening_lines = [r.raw_line for r in records if is_server_listening(r)]
    deprecated_lines = [r.raw_line for r in records if is_deprecated_option(r)]

    # Select queries: use broad failure definition
    failure_sources = sorted({
        info["rhost"]
        for r in records if is_any_auth_failure(r)
        for info in [extract_any_failure_info(r.message)] if info and info["rhost"]
    })

    targeted_users = sorted({
        info["user"]
        for r in records if is_any_auth_failure(r)
        for info in [extract_any_failure_info(r.message)] if info and info.get("user")
    })

    listening_ports = sorted({
        port
        for r in records if is_server_listening(r)
        for port in [extract_listening_port(r.message)] if port is not None
    })

    return {
        "sshd_query_1": _entry(
            query_id="sshd_query_1",
            natural_language="Find log lines recording SSH authentication failures, including Failed password, Invalid user, and PAM authentication failure events.",
            query_type="where",
            description="Security-relevant: detects brute force and credential stuffing attempts.",
            must_contain=auth_failure_lines,
            output_format=["raw_line"],
        ),
        "sshd_query_2": _entry(
            query_id="sshd_query_2",
            natural_language="Find log lines showing successful SSH logins using password authentication.",
            query_type="where",
            description="Security-relevant: password auth is weaker than key-based; useful for compliance auditing.",
            must_contain=accepted_password_lines,
            output_format=["raw_line"],
        ),
        "sshd_query_3": _entry(
            query_id="sshd_query_3",
            natural_language="Find log lines showing successful SSH logins using public key authentication.",
            query_type="where",
            description="Security-relevant: identifies key-based access patterns.",
            must_contain=accepted_publickey_lines,
            output_format=["raw_line"],
        ),
        "sshd_query_4": _entry(
            query_id="sshd_query_4",
            natural_language="Find log lines where an SSH login was attempted with an invalid or unknown username.",
            query_type="where",
            description="Security-relevant: common in automated credential stuffing attacks.",
            must_contain=invalid_user_lines,
            output_format=["raw_line"],
        ),
        "sshd_query_5": _entry(
            query_id="sshd_query_5",
            natural_language="Find log lines showing SSH session openings.",
            query_type="where",
            description="Session tracking for access auditing.",
            must_contain=session_opened_lines,
            output_format=["raw_line"],
        ),
        "sshd_query_6": _entry(
            query_id="sshd_query_6",
            natural_language="Find log lines showing SSH session closings.",
            query_type="where",
            description="Session tracking for access auditing.",
            must_contain=session_closed_lines,
            output_format=["raw_line"],
        ),
        "sshd_query_7": _entry(
            query_id="sshd_query_7",
            natural_language="Find log lines showing SSH network-level disconnection events.",
            query_type="where",
            description="Tracks disconnect events which may indicate session hijacking or network issues.",
            must_contain=disconnect_lines,
            output_format=["raw_line"],
        ),
        "sshd_query_8": _entry(
            query_id="sshd_query_8",
            natural_language="Find log lines showing the SSH server starting and listening on a port.",
            query_type="where",
            description="Security-relevant: detects SSH server restarts and non-standard port configurations.",
            must_contain=listening_lines,
            output_format=["raw_line"],
        ),
        "sshd_query_9": _entry(
            query_id="sshd_query_9",
            natural_language="Find log lines reporting deprecated SSH configuration options.",
            query_type="where",
            description="Security-relevant: deprecated options may indicate outdated, vulnerable configurations.",
            must_contain=deprecated_lines,
            output_format=["raw_line"],
        ),
        "sshd_select_1": _entry(
            query_id="sshd_select_1",
            natural_language="Find the source IP addresses or hostnames that caused SSH authentication failures (including Failed password, Invalid user, and unknown user attempts).",
            query_type="select",
            description="Security-relevant: identifies attacker source IPs for blocking or investigation.",
            must_contain=[[src] for src in failure_sources],
            output_format=["source"],
            output_data_type=["string"],
        ),
        "sshd_select_2": _entry(
            query_id="sshd_select_2",
            natural_language="Find the usernames that were targeted in SSH authentication failure attempts (including Failed password, Invalid user, and unknown user attempts).",
            query_type="select",
            description="Security-relevant: identifies which accounts attackers are targeting.",
            must_contain=[[user] for user in targeted_users],
            output_format=["username"],
            output_data_type=["string"],
        ),
        "sshd_select_3": _entry(
            query_id="sshd_select_3",
            natural_language="Find the ports on which the SSH server was configured to listen.",
            query_type="select",
            description="Security-relevant: non-standard ports may indicate misconfigurations or honeypots.",
            must_contain=[[port] for port in listening_ports],
            output_format=["port"],
            output_data_type=["integer"],
        ),
    }
