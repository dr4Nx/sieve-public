"""Complex cron query definitions and ground truth (security-focused)."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime

from .parser import (
    CronRecord,
    is_cmd_execution,
    is_session_closed,
    is_session_opened,
    extract_cmd_info,
    extract_session_user,
    extract_timestamp_date,
    extract_timestamp_hour,
)


def _parse_ts(ts_text: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts_text)
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


def build_complex_queries(records: list[CronRecord]) -> list[dict]:
    # ------------------------------------------------------------------
    # 1. Per command: count executions and distinct users
    # Security: inventory of scheduled tasks and who runs them
    # ------------------------------------------------------------------
    cmd_counts: Counter[str] = Counter()
    cmd_users: defaultdict[str, set[str]] = defaultdict(set)
    for r in records:
        if is_cmd_execution(r):
            info = extract_cmd_info(r.message)
            if info:
                cmd_counts[info["command"]] += 1
                cmd_users[info["command"]].add(info["user"])

    cmd_rows = [
        [cmd, cmd_counts[cmd], len(cmd_users[cmd])]
        for cmd in sorted(cmd_counts)
    ]

    # ------------------------------------------------------------------
    # 2. Per hour (0-23): count total cron job executions
    # Security: off-hours cron activity is suspicious
    # ------------------------------------------------------------------
    hourly_counts: Counter[int] = Counter()
    for r in records:
        if is_cmd_execution(r):
            hour = extract_timestamp_hour(r.timestamp_text)
            if hour is not None:
                hourly_counts[hour] += 1

    hourly_rows = [
        [hour, hourly_counts[hour]]
        for hour in range(24)
    ]

    # ------------------------------------------------------------------
    # 3. Per date: count session opens, session closes, and CMD executions
    # Security: detect anomalous activity spikes on specific days
    # ------------------------------------------------------------------
    date_opens: Counter[str] = Counter()
    date_closes: Counter[str] = Counter()
    date_cmds: Counter[str] = Counter()
    for r in records:
        date = extract_timestamp_date(r.timestamp_text)
        if not date:
            continue
        if is_session_opened(r):
            date_opens[date] += 1
        if is_session_closed(r):
            date_closes[date] += 1
        if is_cmd_execution(r):
            date_cmds[date] += 1

    all_dates = sorted(set(date_opens) | set(date_closes) | set(date_cmds))
    daily_rows = [
        [date, date_opens[date], date_closes[date], date_cmds[date]]
        for date in all_dates
    ]

    # ------------------------------------------------------------------
    # 4. Per command: maximum elapsed time in seconds between any two
    #    consecutive executions (floored to integer seconds).
    # Security: a max gap significantly larger than the expected cadence
    # indicates a missed scheduled execution, which may signal service
    # outage, log tampering, or attacker interference with cron.
    # ------------------------------------------------------------------
    cmd_ts: defaultdict[str, list[datetime]] = defaultdict(list)
    for r in records:
        if is_cmd_execution(r):
            info = extract_cmd_info(r.message)
            ts = _parse_ts(r.timestamp_text)
            if info and ts:
                cmd_ts[info["command"]].append(ts)

    max_gap_rows: list[list] = []
    for cmd in sorted(cmd_ts):
        times = sorted(cmd_ts[cmd])
        if len(times) < 2:
            continue
        max_gap = max(
            (times[i] - times[i - 1]).total_seconds()
            for i in range(1, len(times))
        )
        max_gap_rows.append([cmd, int(max_gap)])

    # ------------------------------------------------------------------
    # 5. Find sessions where a cron session was opened but no CMD execution
    #    occurred in the same process (orphaned sessions
    # Security: may indicate failed or suppressed cron jobs
    # ------------------------------------------------------------------
    session_pids: set[tuple[str, int]] = set()
    cmd_pids: set[tuple[str, int]] = set()
    for r in records:
        if r.process_id is None:
            continue
        if is_session_opened(r):
            session_pids.add((r.host, r.process_id))
        if is_cmd_execution(r):
            cmd_pids.add((r.host, r.process_id))

    orphaned = sorted(session_pids - cmd_pids)
    orphan_rows = [[host, pid] for host, pid in orphaned]

    # ------------------------------------------------------------------
    # 6. Per command: find the earliest and latest execution timestamp
    # Security: determine the active window of each scheduled task
    # ------------------------------------------------------------------
    cmd_first: dict[str, str] = {}
    cmd_last: dict[str, str] = {}
    for r in records:
        if is_cmd_execution(r):
            info = extract_cmd_info(r.message)
            if info:
                cmd = info["command"]
                if cmd not in cmd_first:
                    cmd_first[cmd] = r.timestamp_text
                cmd_last[cmd] = r.timestamp_text

    cmd_window_rows = [
        [cmd, cmd_first[cmd], cmd_last[cmd]]
        for cmd in sorted(cmd_first)
    ]

    # ------------------------------------------------------------------
    # 7. For each 15-minute time interval on each date, count the number
    #    of CMD executions. Return only intervals with executions.
    # Security: fine-grained temporal pattern for anomaly detection
    # ------------------------------------------------------------------
    interval_counts: Counter[tuple[str, int]] = Counter()
    for r in records:
        if is_cmd_execution(r):
            ts = _parse_ts(r.timestamp_text)
            date = extract_timestamp_date(r.timestamp_text)
            if ts and date:
                # 15-min bucket: 0, 15, 30, 45
                bucket = ts.hour * 60 + (ts.minute // 15) * 15
                interval_counts[(date, bucket)] += 1

    interval_rows = [
        [date, bucket, interval_counts[(date, bucket)]]
        for (date, bucket) in sorted(interval_counts)
        if interval_counts[(date, bucket)] > 0
    ]

    # ------------------------------------------------------------------
    # 8. Per host and date: count CMD executions and session opens
    # Security: correlate session and execution activity per host per day
    # ------------------------------------------------------------------
    hd_cmds: Counter[tuple[str, str]] = Counter()
    hd_opens: Counter[tuple[str, str]] = Counter()
    for r in records:
        date = extract_timestamp_date(r.timestamp_text)
        if not date:
            continue
        if is_cmd_execution(r):
            hd_cmds[(r.host, date)] += 1
        if is_session_opened(r):
            hd_opens[(r.host, date)] += 1

    hd_rows = [
        [host, date, hd_cmds[(host, date)], hd_opens[(host, date)]]
        for (host, date) in sorted(set(hd_cmds) | set(hd_opens))
    ]

    return [
        _query(
            query_id="multiline_1",
            natural_language="For each distinct command executed by cron, count how many times it was executed and by how many distinct users.",
            output_format=["command", "execution_count", "distinct_user_count"],
            output_data_type=["string", "integer", "integer"],
            rows=cmd_rows,
        ),
        _query(
            query_id="multiline_2",
            natural_language="For each hour of the day (0 through 23), count the total number of cron job command executions.",
            output_format=["hour", "execution_count"],
            output_data_type=["integer", "integer"],
            rows=hourly_rows,
        ),
        _query(
            query_id="multiline_3",
            natural_language="For each date, count the number of cron session opens, session closes, and command executions.",
            output_format=["date", "session_opens", "session_closes", "cmd_executions"],
            output_data_type=["string", "integer", "integer", "integer"],
            rows=daily_rows,
        ),
        _query(
            query_id="multiline_4",
            natural_language="For each cron command, find the maximum elapsed time in seconds between any two consecutive executions of that same command. Floor the result to the nearest whole second (e.g. 900.99s becomes 900). Return the command and the maximum gap. This identifies missed or delayed scheduled executions.",
            output_format=["command", "max_gap_seconds"],
            output_data_type=["string", "integer"],
            rows=max_gap_rows,
        ),
        _query(
            query_id="multiline_5",
            natural_language="Find cron sessions (by host and process ID) where a session was opened but no command was executed in the same process.",
            output_format=["host", "process_id"],
            output_data_type=["string", "integer"],
            rows=orphan_rows,
        ),
        _query(
            query_id="multiline_6",
            natural_language="For each distinct command executed by cron, return the earliest and latest execution timestamp text.",
            output_format=["command", "earliest_timestamp", "latest_timestamp"],
            output_data_type=["string", "string", "string"],
            rows=cmd_window_rows,
        ),
        _query(
            query_id="multiline_7",
            natural_language="For each date and 15-minute time interval, count the number of cron command executions. The interval is represented as minutes since midnight (0, 15, 30, 45, 60, ...). Return only intervals that had at least one execution.",
            output_format=["date", "interval_minutes", "execution_count"],
            output_data_type=["string", "integer", "integer"],
            rows=interval_rows,
        ),
        _query(
            query_id="multiline_8",
            natural_language="For each host and date, count the number of cron command executions and session opens.",
            output_format=["host", "date", "cmd_executions", "session_opens"],
            output_data_type=["string", "string", "integer", "integer"],
            rows=hd_rows,
        ),
    ]
