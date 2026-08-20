"""Complex Puppet query definitions and ground truth."""

from __future__ import annotations

from collections import Counter, defaultdict

from .parser import (
    PuppetRecord,
    classify_error_family,
    extract_duration_seconds,
    extract_refresh_target,
    extract_resource_identifier,
    extract_top_level_module,
    is_cached_catalog,
    is_catalog_retrieval_failure,
    is_configuration_applied,
    is_finished_run,
    is_node_definition_failure,
    is_refresh_schedule,
    is_refresh_trigger,
    is_report_failure,
    is_skipped_dependency,
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


def _round_rate(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 6)


def build_complex_queries(records: list[PuppetRecord]) -> list[dict]:
    started_streams_by_host: defaultdict[str, set[tuple[str, int]]] = defaultdict(set)
    finished_streams_by_host: defaultdict[str, set[tuple[str, int]]] = defaultdict(set)
    runtime_sums: defaultdict[str, list[float]] = defaultdict(list)
    report_failures: Counter[str] = Counter()
    catalog_failures: Counter[str] = Counter()
    skipped_modules: Counter[str] = Counter()
    host_error_family_counts: Counter[tuple[str, str]] = Counter()
    schedule_counts: Counter[tuple[str, int]] = Counter()
    trigger_counts: Counter[tuple[str, int]] = Counter()

    node_fail_to_cached_rows: list[list] = []
    fail_cached_report_rows: list[list] = []

    latest_node_failure_by_stream: dict[tuple[str, int], str] = {}
    latest_catalog_fail_by_stream: dict[tuple[str, int], str] = {}
    latest_cached_after_fail_by_stream: dict[tuple[str, int], str] = {}
    streams_with_start: set[tuple[str, int]] = set()

    for record in records:
        if is_configuration_applied(record) and record.stream_key is not None:
            streams_with_start.add(record.stream_key)
            started_streams_by_host[record.host].add(record.stream_key)
        if is_finished_run(record):
            if record.stream_key is not None and record.stream_key in streams_with_start:
                finished_streams_by_host[record.host].add(record.stream_key)
            duration = extract_duration_seconds(record.message)
            if duration is not None:
                runtime_sums[record.host].append(duration)
        if is_report_failure(record):
            report_failures[record.host] += 1
        if is_catalog_retrieval_failure(record):
            catalog_failures[record.host] += 1
        if is_skipped_dependency(record):
            module = extract_top_level_module(record.message)
            if module:
                skipped_modules[module] += 1
        if is_refresh_schedule(record) and record.stream_key is not None:
            schedule_counts[record.stream_key] += 1
        if is_refresh_trigger(record) and record.stream_key is not None:
            trigger_counts[record.stream_key] += 1

        error_family = classify_error_family(record)
        if error_family:
            host_error_family_counts[(record.host, error_family)] += 1

        stream_key = record.stream_key
        if stream_key is None:
            continue

        if is_node_definition_failure(record):
            latest_node_failure_by_stream[stream_key] = record.timestamp_text
        elif is_cached_catalog(record):
            failure_timestamp = latest_node_failure_by_stream.get(stream_key)
            if failure_timestamp:
                node_fail_to_cached_rows.append(
                    [record.host, record.process_id, failure_timestamp, record.timestamp_text]
                )
                latest_node_failure_by_stream.pop(stream_key, None)

        if is_catalog_retrieval_failure(record):
            latest_catalog_fail_by_stream[stream_key] = record.timestamp_text
            latest_cached_after_fail_by_stream.pop(stream_key, None)
        elif is_cached_catalog(record):
            catalog_timestamp = latest_catalog_fail_by_stream.get(stream_key)
            if catalog_timestamp:
                latest_cached_after_fail_by_stream[stream_key] = record.timestamp_text
        elif is_report_failure(record):
            catalog_timestamp = latest_catalog_fail_by_stream.get(stream_key)
            cached_timestamp = latest_cached_after_fail_by_stream.get(stream_key)
            if catalog_timestamp and cached_timestamp:
                fail_cached_report_rows.append(
                    [
                        record.host,
                        record.process_id,
                        catalog_timestamp,
                        cached_timestamp,
                        record.timestamp_text,
                    ]
                )
                latest_catalog_fail_by_stream.pop(stream_key, None)
                latest_cached_after_fail_by_stream.pop(stream_key, None)

    run_summary_rows = []
    for host in sorted(set(started_streams_by_host) | set(finished_streams_by_host)):
        started = len(started_streams_by_host[host])
        finished = len(finished_streams_by_host[host])
        run_summary_rows.append([host, started, finished, _round_rate(finished, started)])

    average_runtime_rows = []
    for host in sorted(runtime_sums):
        durations = runtime_sums[host]
        if durations:
            average_runtime_rows.append([host, round(sum(durations) / len(durations), 2)])

    host_failure_summary_rows = []
    for host in sorted(set(report_failures) | set(catalog_failures)):
        host_failure_summary_rows.append(
            [host, report_failures[host], catalog_failures[host]]
        )

    skipped_module_rows = [
        [module, skipped_modules[module]]
        for module in sorted(skipped_modules)
    ]

    error_family_rows = [
        [host, family, count]
        for (host, family), count in sorted(host_error_family_counts.items())
    ]

    refresh_summary_rows = []
    for stream_key in sorted(set(schedule_counts) | set(trigger_counts)):
        host, process_id = stream_key
        refresh_summary_rows.append(
            [host, process_id, schedule_counts[stream_key], trigger_counts[stream_key]]
        )

    node_fail_to_cached_rows.sort(key=lambda row: (row[0], row[1], row[2], row[3]))
    fail_cached_report_rows.sort(key=lambda row: (row[0], row[1], row[2], row[3], row[4]))

    return [
        _query(
            query_id="multiline_1",
            natural_language="For each host, count Puppet runs that begin applying a configuration version, count how many of those runs later finish, and return the completion rate.",
            output_format=["host", "started_run_stream_count", "finished_run_stream_count", "completion_rate"],
            output_data_type=["string", "integer", "integer", "float"],
            rows=run_summary_rows,
        ),
        _query(
            query_id="multiline_2",
            natural_language="For each host, average the runtime reported for finished catalog runs and return the host with the average runtime in seconds, rounded to two decimal places.",
            output_format=["host", "average_runtime_seconds"],
            output_data_type=["string", "float"],
            rows=average_runtime_rows,
        ),
        _query(
            query_id="multiline_3",
            natural_language="Find Puppet agent processes where a node-definition fetch failure is later followed by use of a cached catalog. Return the host, process id, and the original syslog timestamp text from those two events.",
            output_format=["host", "process_id", "failure_timestamp", "cached_catalog_timestamp"],
            output_data_type=["string", "integer", "string", "string"],
            rows=node_fail_to_cached_rows,
        ),
        _query(
            query_id="multiline_4",
            natural_language="For each host that saw report-send failures or remote catalog retrieval failures, count both and return those two totals.",
            output_format=["host", "report_failure_count", "catalog_retrieval_failure_count"],
            output_data_type=["string", "integer", "integer"],
            rows=host_failure_summary_rows,
        ),
        _query(
            query_id="multiline_5",
            natural_language="For each Puppet module name appearing after '/Stage[main]/' in skipped resource identifiers, count how many resources were skipped because of failed dependencies.",
            output_format=["module_name", "skipped_dependency_count"],
            output_data_type=["string", "integer"],
            rows=skipped_module_rows,
        ),
        _query(
            query_id="multiline_6",
            natural_language="For each host, group Puppet failure messages into these error families when they apply: certificate_verify_failed, getaddrinfo, network_unreachable, command_not_found, timeout, error_downloading_packages, and no_child_processes. Return the host, the error family name, and the count.",
            output_format=["host", "error_family", "occurrence_count"],
            output_data_type=["string", "string", "integer"],
            rows=error_family_rows,
        ),
        _query(
            query_id="multiline_7",
            natural_language="For each host and Puppet agent process that logged refresh activity, count how many refreshes were scheduled and how many refreshes were triggered.",
            output_format=["host", "process_id", "scheduled_refresh_count", "triggered_refresh_count"],
            output_data_type=["string", "integer", "integer", "integer"],
            rows=refresh_summary_rows,
        ),
        _query(
            query_id="multiline_8",
            natural_language="Find Puppet agent processes where a remote catalog retrieval failure is followed by use of a cached catalog and then a report-send failure. Return the host, process id, and the original syslog timestamp text from those three events.",
            output_format=[
                "host",
                "process_id",
                "catalog_failure_timestamp",
                "cached_catalog_timestamp",
                "report_failure_timestamp",
            ],
            output_data_type=["string", "integer", "string", "string", "string"],
            rows=fail_cached_report_rows,
        ),
    ]
