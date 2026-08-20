"""I/O helpers for evaluation data and log resolution."""

import gzip
import json
import os
from typing import Any, Dict, List


def resolve_log_file(path: str) -> str:
    """Resolve a log file path which may be either a file or a directory."""
    if os.path.isfile(path):
        return path
    if os.path.isdir(path):
        candidates = []
        for name in ["dhcp.log", "dhcp"]:
            p = os.path.join(path, name)
            if os.path.isfile(p):
                return p
        for fname in os.listdir(path):
            full = os.path.join(path, fname)
            if os.path.isfile(full) and fname.endswith(".log"):
                candidates.append(full)
        if candidates:
            candidates.sort(key=lambda f: os.path.getsize(f), reverse=True)
            return candidates[0]
        for fname in os.listdir(path):
            full = os.path.join(path, fname)
            if os.path.isfile(full) and fname.endswith(".log.gz"):
                candidates.append(full)
        if candidates:
            candidates.sort(key=lambda f: os.path.getsize(f), reverse=True)
            return candidates[0]
        for fname in os.listdir(path):
            full = os.path.join(path, fname)
            if os.path.isfile(full) and fname.endswith(".gz"):
                candidates.append(full)
        if candidates:
            candidates.sort(key=lambda f: os.path.getsize(f), reverse=True)
            return candidates[0]
        raise FileNotFoundError(f"No log files found in directory: {path}")
    raise FileNotFoundError(f"Log path not found: {path}")


def load_eval_json(path: str) -> List[Dict[str, Any]]:
    if not os.path.isfile(path):
        if not path.endswith(".gz") and os.path.isfile(path + ".gz"):
            path = path + ".gz"
        else:
            raise FileNotFoundError(f"Evaluation JSON not found: {path}")
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ["queries", "data", "items"]:
            if key in data and isinstance(data[key], list):
                return data[key]
        if all(isinstance(v, dict) for v in data.values()):
            entries: List[Dict[str, Any]] = []
            for key, value in data.items():
                # Preserve the top-level mapping key as a stable identifier.
                entry = dict(value)
                entry.setdefault("__query_key", str(key))
                entries.append(entry)
            return entries
        raise ValueError(
            "Dict JSON must contain a list under one of: queries, data, items, or be a mapping of id->entry"
        )
    raise ValueError("Evaluation JSON must be a list or an object containing a list.")
