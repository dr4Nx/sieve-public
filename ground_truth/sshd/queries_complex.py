"""Complex sshd query definitions and ground truth (security-focused)."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime

from .parser import (
    SshdRecord,
    is_accepted_auth,
    is_accepted_password,
    is_any_auth_failure,
    is_auth_failure,
    is_disconnect,
    is_session_closed,
    is_session_opened,
    is_server_listening,
    extract_accepted_info,
    extract_any_failure_info,
    extract_auth_failure_info,
    extract_disconnect_ip,
    extract_key_fingerprint,
    extract_listening_port,
)


_MONTHS = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
           "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}


def _parse_ts(ts_text: str) -> datetime | None:
    try:
        parts = ts_text.split()
        return datetime(2000, _MONTHS[parts[0]], int(parts[1]),
                        *map(int, parts[2].split(":")))
    except Exception:
        return None


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


def build_complex_queries(records: list[SshdRecord]) -> list[dict]:
    # ------------------------------------------------------------------
    # 1. Per source IP: count auth failures and distinct targeted usernames
    # Uses broad failure definition (PAM + Failed password + Invalid user)
    # ------------------------------------------------------------------
    failures_by_source: Counter[str] = Counter()
    users_by_source: defaultdict[str, set[str]] = defaultdict(set)
    for r in records:
        if is_any_auth_failure(r):
            info = extract_any_failure_info(r.message)
            if info and info["rhost"]:
                failures_by_source[info["rhost"]] += 1
                if info.get("user"):
                    users_by_source[info["rhost"]].add(info["user"])

    brute_force_rows = [
        [src, failures_by_source[src], len(users_by_source[src])]
        for src in sorted(failures_by_source)
    ]

    # ------------------------------------------------------------------
    # 2. Find source IPs with 10+ failures within any 5-minute window
    # Uses broad failure definition
    # ------------------------------------------------------------------
    fail_times: defaultdict[str, list[datetime]] = defaultdict(list)
    for r in records:
        if is_any_auth_failure(r):
            info = extract_any_failure_info(r.message)
            ts = _parse_ts(r.timestamp_text)
            if info and info["rhost"] and ts:
                fail_times[info["rhost"]].append(ts)

    burst_rows = []
    for src, times in sorted(fail_times.items()):
        times.sort()
        best_count = 0
        for i in range(len(times)):
            j = i
            while j < len(times) and (times[j] - times[i]).total_seconds() <= 300:
                j += 1
            count = j - i
            if count >= 10 and count > best_count:
                best_count = count
        if best_count >= 10:
            burst_rows.append([src, best_count])
    burst_rows.sort(key=lambda r: (r[0]))

    # ------------------------------------------------------------------
    # 3. Find source IPs that attempted 5+ distinct usernames
    # Uses broad failure definition
    # ------------------------------------------------------------------
    multi_user_rows = [
        [src, len(users_by_source[src])]
        for src in sorted(users_by_source)
        if len(users_by_source[src]) >= 5
    ]

    # ------------------------------------------------------------------
    # 4. Find users who logged in from 2+ different IPs within 60 seconds
    # Hint: timestamps use syslog format, assume year 2000
    # ------------------------------------------------------------------
    user_logins: defaultdict[str, list[tuple[datetime, str]]] = defaultdict(list)
    for r in records:
        if is_accepted_auth(r):
            info = extract_accepted_info(r.message)
            ts = _parse_ts(r.timestamp_text)
            if info and ts:
                user_logins[info["user"]].append((ts, info["ip"]))

    dual_ip_seen: set[tuple[str, str, str]] = set()
    for user, logins in user_logins.items():
        logins.sort()
        for i in range(len(logins)):
            for j in range(i + 1, len(logins)):
                if (logins[j][0] - logins[i][0]).total_seconds() > 60:
                    break
                if logins[j][1] != logins[i][1]:
                    dual_ip_seen.add((user, logins[i][1], logins[j][1]))
    dual_ip_rows = [list(t) for t in sorted(dual_ip_seen)]

    # ------------------------------------------------------------------
    # 5. Per host: count session opens and closes, compute unclosed
    # ------------------------------------------------------------------
    opens_by_host: Counter[str] = Counter()
    closes_by_host: Counter[str] = Counter()
    for r in records:
        if is_session_opened(r):
            opens_by_host[r.host] += 1
        if is_session_closed(r):
            closes_by_host[r.host] += 1

    session_balance_rows = [
        [host, opens_by_host[host], closes_by_host[host],
         opens_by_host[host] - closes_by_host[host]]
        for host in sorted(set(opens_by_host) | set(closes_by_host))
    ]

    # ------------------------------------------------------------------
    # 6. Per source IP: count failures targeting root
    # Uses broad failure definition
    # ------------------------------------------------------------------
    root_failures_by_source: Counter[str] = Counter()
    for r in records:
        if is_any_auth_failure(r):
            info = extract_any_failure_info(r.message)
            if info and info["rhost"] and info.get("user") == "root":
                root_failures_by_source[info["rhost"]] += 1

    root_brute_rows = [
        [src, root_failures_by_source[src]]
        for src in sorted(root_failures_by_source)
        if root_failures_by_source[src] > 0
    ]

    # ------------------------------------------------------------------
    # 7. Per host and user: count accepted logins and distinct key fingerprints
    # ------------------------------------------------------------------
    host_user_logins: Counter[tuple[str, str]] = Counter()
    host_user_keys: defaultdict[tuple[str, str], set[str]] = defaultdict(set)
    for r in records:
        if is_accepted_auth(r):
            info = extract_accepted_info(r.message)
            if info:
                key = (r.host, info["user"])
                host_user_logins[key] += 1
                fp = extract_key_fingerprint(r.message)
                if fp:
                    host_user_keys[key].add(fp)

    user_access_rows = [
        [host, user, host_user_logins[(host, user)], len(host_user_keys[(host, user)])]
        for (host, user) in sorted(host_user_logins)
    ]

    # ------------------------------------------------------------------
    # 8. Per host: count distinct attacker IPs vs distinct legitimate IPs
    # Uses broad failure definition
    # ------------------------------------------------------------------
    fail_ips_by_host: defaultdict[str, set[str]] = defaultdict(set)
    success_ips_by_host: defaultdict[str, set[str]] = defaultdict(set)
    for r in records:
        if is_any_auth_failure(r):
            info = extract_any_failure_info(r.message)
            if info and info["rhost"]:
                fail_ips_by_host[r.host].add(info["rhost"])
        if is_accepted_auth(r):
            info = extract_accepted_info(r.message)
            if info:
                success_ips_by_host[r.host].add(info["ip"])

    attack_surface_rows = [
        [host, len(fail_ips_by_host[host]), len(success_ips_by_host[host])]
        for host in sorted(set(fail_ips_by_host) | set(success_ips_by_host))
    ]

    return [
        _query(
            query_id="multiline_1",
            natural_language="For each source IP that attempted SSH authentication and failed one or more times, count the total number of failed authentication events and the number of distinct usernames tried. Exclude connection-level events (port scans, protocol probes, connection resets) where no authentication was attempted.",
            output_format=["source_ip", "failure_count", "distinct_usernames_targeted"],
            output_data_type=["string", "integer", "integer"],
            rows=brute_force_rows,
        ),
        _query(
            query_id="multiline_2",
            natural_language="Find source IPs that attempted SSH authentication and failed 10 or more times within any 5-minute window. Return the source IP and the peak failure count within a single 5-minute window. Exclude connection-level events where no authentication was attempted.",
            output_format=["source_ip", "peak_failures_in_5min"],
            output_data_type=["string", "integer"],
            rows=burst_rows,
        ),
        _query(
            query_id="multiline_3",
            natural_language="Find source IPs that attempted SSH authentication and failed using 5 or more distinct usernames. Return the source IP and the number of distinct usernames tried. Exclude connection-level events where no authentication was attempted.",
            output_format=["source_ip", "distinct_usernames"],
            output_data_type=["string", "integer"],
            rows=multi_user_rows,
        ),
        _query(
            query_id="multiline_4",
            natural_language="Find users who had successful SSH logins from two different source IP addresses within 60 seconds of each other. Assume year 2000 for timestamps. Return the username and the two IP addresses.",
            output_format=["username", "first_ip", "second_ip"],
            output_data_type=["string", "string", "string"],
            rows=dual_ip_rows,
        ),
        _query(
            query_id="multiline_5",
            natural_language="For each host, count SSH session opens and session closes, and compute the number of unclosed sessions (opens minus closes).",
            output_format=["host", "session_opens", "session_closes", "unclosed_sessions"],
            output_data_type=["string", "integer", "integer", "integer"],
            rows=session_balance_rows,
        ),
        _query(
            query_id="multiline_6",
            natural_language="For each source IP, count the number of failed SSH authentication events that specifically targeted the root account. Exclude connection-level events where no authentication was attempted.",
            output_format=["source_ip", "root_failure_count"],
            output_data_type=["string", "integer"],
            rows=root_brute_rows,
        ),
        _query(
            query_id="multiline_7",
            natural_language="For each host and username with successful SSH logins, count the total logins and the number of distinct key fingerprints used. Only count 'Accepted' login events, not session events.",
            output_format=["host", "username", "login_count", "distinct_key_count"],
            output_data_type=["string", "string", "integer", "integer"],
            rows=user_access_rows,
        ),
        _query(
            query_id="multiline_8",
            natural_language="For each host, count the number of distinct source IPs that attempted SSH authentication and failed, and the number of distinct source IPs with successful SSH logins. Exclude connection-level events (port scans, protocol probes, connection resets) where no authentication was attempted.",
            output_format=["host", "distinct_attacker_ips", "distinct_legitimate_ips"],
            output_data_type=["string", "integer", "integer"],
            rows=attack_surface_rows,
        ),
    ]
