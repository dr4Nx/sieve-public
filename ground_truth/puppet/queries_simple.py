"""Simple Puppet query definitions and ground truth."""

from __future__ import annotations

from .parser import (
    PuppetRecord,
    extract_configuration_version,
    extract_resource_identifier,
    is_cached_catalog,
    is_catalog_retrieval_failure,
    is_certificate_failure,
    is_command_missing,
    is_disabled_run,
    is_enabled_run,
    is_node_definition_failure,
    is_report_failure,
    is_skipped_dependency,
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


def build_simple_queries(records: list[PuppetRecord]) -> dict[str, dict]:
    disabled_lines = [record.raw_line for record in records if is_disabled_run(record)]
    enabled_lines = [record.raw_line for record in records if is_enabled_run(record)]
    node_definition_lines = [record.raw_line for record in records if is_node_definition_failure(record)]
    catalog_failure_lines = [record.raw_line for record in records if is_catalog_retrieval_failure(record)]
    cached_catalog_lines = [record.raw_line for record in records if is_cached_catalog(record)]
    report_failure_lines = [record.raw_line for record in records if is_report_failure(record)]
    skipped_dependency_lines = [record.raw_line for record in records if is_skipped_dependency(record)]
    command_missing_lines = [record.raw_line for record in records if is_command_missing(record)]
    certificate_failure_lines = [record.raw_line for record in records if is_certificate_failure(record)]

    catalog_failure_hosts = sorted({record.host for record in records if is_catalog_retrieval_failure(record)})
    configuration_versions = sorted(
        {
            version
            for record in records
            for version in [extract_configuration_version(record.message)]
            if version
        }
    )
    skipped_resources = sorted(
        {
            resource
            for record in records
            if is_skipped_dependency(record)
            for resource in [extract_resource_identifier(record.message)]
            if resource
        }
    )

    return {
        "puppet_query_1": _entry(
            query_id="puppet_query_1",
            natural_language="Find log lines indicating Puppet runs were disabled by an administrative action.",
            query_type="where",
            description="Security-oriented raw-line query for administrative Puppet disable events.",
            must_contain=disabled_lines,
            output_format=["raw_line"],
        ),
        "puppet_query_2": _entry(
            query_id="puppet_query_2",
            natural_language="Find log lines indicating Puppet execution was re-enabled after being disabled.",
            query_type="where",
            description="Security-oriented raw-line query for Puppet enable events.",
            must_contain=enabled_lines,
            output_format=["raw_line"],
        ),
        "puppet_query_3": _entry(
            query_id="puppet_query_3",
            natural_language="Find log lines where Puppet says it could not fetch the node definition it needed.",
            query_type="where",
            description="Security-oriented raw-line query for node definition lookup failures.",
            must_contain=node_definition_lines,
            output_format=["raw_line"],
        ),
        "puppet_query_4": _entry(
            query_id="puppet_query_4",
            natural_language="Find log lines showing the agent could not retrieve its catalog from a remote source.",
            query_type="where",
            description="Security-oriented raw-line query for remote catalog retrieval failures.",
            must_contain=catalog_failure_lines,
            output_format=["raw_line"],
        ),
        "puppet_query_5": _entry(
            query_id="puppet_query_5",
            natural_language="Find log lines showing the agent fell back to a cached catalog after a remote problem.",
            query_type="where",
            description="Security-oriented raw-line query for cached catalog fallback events.",
            must_contain=cached_catalog_lines,
            output_format=["raw_line"],
        ),
        "puppet_query_6": _entry(
            query_id="puppet_query_6",
            natural_language="Find log lines showing Puppet could not deliver its report back to a remote service.",
            query_type="where",
            description="Security-oriented raw-line query for report delivery failures.",
            must_contain=report_failure_lines,
            output_format=["raw_line"],
        ),
        "puppet_query_7": _entry(
            query_id="puppet_query_7",
            natural_language="Find log lines showing resources were skipped because a dependency chain had already failed.",
            query_type="where",
            description="Security-oriented raw-line query for skipped resources caused by dependency failures.",
            must_contain=skipped_dependency_lines,
            output_format=["raw_line"],
        ),
        "puppet_query_8": _entry(
            query_id="puppet_query_8",
            natural_language="Find log lines where Puppet reports that a needed command could not be found.",
            query_type="where",
            description="Security-oriented raw-line query for missing command execution failures.",
            must_contain=command_missing_lines,
            output_format=["raw_line"],
        ),
        "puppet_query_9": _entry(
            query_id="puppet_query_9",
            natural_language="Find log lines showing certificate validation or trust failures during remote Puppet communication.",
            query_type="where",
            description="Security-oriented raw-line query for certificate verification failures.",
            must_contain=certificate_failure_lines,
            output_format=["raw_line"],
        ),
        "puppet_select_1": _entry(
            query_id="puppet_select_1",
            natural_language="Find the hosts that experienced remote catalog retrieval failures.",
            query_type="select",
            description="Select query for hosts with catalog retrieval failures.",
            must_contain=[[host] for host in catalog_failure_hosts],
            output_format=["host"],
            output_data_type=["string"],
        ),
        "puppet_select_2": _entry(
            query_id="puppet_select_2",
            natural_language="Find the configuration versions that were applied during Puppet runs.",
            query_type="select",
            description="Select query for configuration versions applied by Puppet.",
            must_contain=[[version] for version in configuration_versions],
            output_format=["configuration_version"],
            output_data_type=["string"],
        ),
        "puppet_select_3": _entry(
            query_id="puppet_select_3",
            natural_language="Find the resource identifiers that were skipped because of failed dependencies.",
            query_type="select",
            description="Select query for resource identifiers involved in failed dependency skips.",
            must_contain=[[resource] for resource in skipped_resources],
            output_format=["resource_identifier"],
            output_data_type=["string"],
        ),
    }
