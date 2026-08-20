"""Shared repository path helpers."""

from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def repo_path(*parts: str) -> Path:
    return repo_root().joinpath(*parts)


def log_parser_script() -> str:
    return str(repo_path("log_parser.py"))


def default_output_dir() -> str:
    return str(repo_path("output"))


def default_eval_dir() -> str:
    return str(repo_path("eval"))


def default_batch_output_dir(timestamp: str) -> str:
    return str(repo_path("output", f"batch-output-{timestamp}"))


def default_extracted_templates_dir() -> str:
    return str(repo_path("log_query", "extracted_templates"))
