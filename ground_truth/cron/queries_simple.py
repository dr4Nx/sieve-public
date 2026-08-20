"""Simple cron query definitions and ground truth (security-focused)."""

from __future__ import annotations

from .parser import (
    CronRecord,
    is_cmd_execution,
    is_inotify,
    is_scaling_factor,
    is_session_closed,
    is_session_opened,
    extract_cmd_info,
    extract_scaling_factor,
    extract_session_user,
    extract_timestamp_date,
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


def build_simple_queries(records: list[CronRecord]) -> dict[str, dict]:
    # Where queries
    cmd_lines = [r.raw_line for r in records if is_cmd_execution(r)]
    session_open_lines = [r.raw_line for r in records if is_session_opened(r)]
    session_close_lines = [r.raw_line for r in records if is_session_closed(r)]
    scaling_lines = [r.raw_line for r in records if is_scaling_factor(r)]
    inotify_lines = [r.raw_line for r in records if is_inotify(r)]

    # Filter: sessions opened for root (security relevant: root cron jobs)
    root_session_lines = [
        r.raw_line for r in records
        if is_session_opened(r) and extract_session_user(r.message) == "root"
    ]

    # Filter: CMD executions on a specific date
    date_cmd_lines = [
        r.raw_line for r in records
        if is_cmd_execution(r) and extract_timestamp_date(r.timestamp_text) == "2017-07-14"
    ]

    # Select queries
    executed_commands = sorted({
        info["command"]
        for r in records if is_cmd_execution(r)
        for info in [extract_cmd_info(r.message)] if info
    })

    cmd_users = sorted({
        info["user"]
        for r in records if is_cmd_execution(r)
        for info in [extract_cmd_info(r.message)] if info
    })

    unique_dates = sorted({
        date
        for r in records
        for date in [extract_timestamp_date(r.timestamp_text)] if date
    })

    return {
        "cron_query_1": _entry(
            query_id="cron_query_1",
            natural_language="Find log lines showing cron job command executions.",
            query_type="where",
            description="Security-relevant: identifies what scheduled tasks are running on the system.",
            must_contain=cmd_lines,
            output_format=["raw_line"],
        ),
        "cron_query_2": _entry(
            query_id="cron_query_2",
            natural_language="Find log lines showing cron session openings.",
            query_type="where",
            description="Session tracking for cron job auditing.",
            must_contain=session_open_lines,
            output_format=["raw_line"],
        ),
        "cron_query_3": _entry(
            query_id="cron_query_3",
            natural_language="Find log lines showing cron session closings.",
            query_type="where",
            description="Session tracking for cron job auditing.",
            must_contain=session_close_lines,
            output_format=["raw_line"],
        ),
        "cron_query_4": _entry(
            query_id="cron_query_4",
            natural_language="Find log lines showing cron sessions opened for the root user.",
            query_type="where",
            description="Security-relevant: root cron jobs have elevated privileges and should be audited.",
            must_contain=root_session_lines,
            output_format=["raw_line"],
        ),
        "cron_query_5": _entry(
            query_id="cron_query_5",
            natural_language="Find cron command-execution log lines on July 14, 2017.",
            query_type="where",
            description="Time-scoped query for incident investigation.",
            must_contain=date_cmd_lines,
            output_format=["raw_line"],
        ),
        "cron_query_6": _entry(
            query_id="cron_query_6",
            natural_language="Find log lines mentioning the RANDOM_DELAY scaling factor.",
            query_type="where",
            description="Configuration auditing: scaling factor affects cron job timing.",
            must_contain=scaling_lines,
            output_format=["raw_line"],
        ),
        "cron_query_7": _entry(
            query_id="cron_query_7",
            natural_language="Find log lines showing that the cron daemon started with inotify support.",
            query_type="where",
            description="System configuration: inotify support indicates cron startup events.",
            must_contain=inotify_lines,
            output_format=["raw_line"],
        ),
        "cron_query_8": _entry(
            query_id="cron_query_8",
            natural_language="Find all cron log lines from July 14, 2017 between 03:00 and 04:00.",
            query_type="where",
            description="Time-window query for incident investigation.",
            must_contain=[
                r.raw_line for r in records
                if r.timestamp_text.startswith("2017-07-14T03:")
            ],
            output_format=["raw_line"],
        ),
        "cron_query_9": _entry(
            query_id="cron_query_9",
            natural_language="Find all cron log lines with process ID 21832.",
            query_type="where",
            description="Process-level forensic query.",
            must_contain=[r.raw_line for r in records if r.process_id == 21832],
            output_format=["raw_line"],
        ),
        "cron_select_1": _entry(
            query_id="cron_select_1",
            natural_language="Find the distinct commands that were executed by cron jobs.",
            query_type="select",
            description="Security-relevant: inventory of all scheduled commands running on the system.",
            must_contain=[[cmd] for cmd in executed_commands],
            output_format=["command"],
            output_data_type=["string"],
        ),
        "cron_select_2": _entry(
            query_id="cron_select_2",
            natural_language="Find the usernames under which cron jobs were executed.",
            query_type="select",
            description="Security-relevant: identifies which user accounts have active cron jobs.",
            must_contain=[[user] for user in cmd_users],
            output_format=["username"],
            output_data_type=["string"],
        ),
        "cron_select_3": _entry(
            query_id="cron_select_3",
            natural_language="Find the distinct dates on which cron activity was logged.",
            query_type="select",
            description="Temporal scope: identifies the date range covered by the cron log.",
            must_contain=[[date] for date in unique_dates],
            output_format=["date"],
            output_data_type=["string"],
        ),
    }
