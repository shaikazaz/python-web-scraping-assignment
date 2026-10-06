"""Atomic incremental fingerprint state."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def load_previous_fingerprints(path: Path) -> set[str]:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            values = data.get("fingerprints", [])
        else:
            values = data
        return {str(v) for v in values} if isinstance(values, list) else set()
    except (FileNotFoundError, OSError, json.JSONDecodeError, TypeError):
        return set()


def save_fingerprints(path: Path, fingerprints: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    payload = {"version": 1, "fingerprints": sorted(fingerprints)}
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def compare_fingerprints(
    records: list[dict[str, Any]],
    previous: set[str],
    fingerprint_fn,
) -> tuple[list[dict[str, Any]], set[str]]:
    current: set[str] = set()
    new_records: list[dict[str, Any]] = []
    for record in records:
        fp = fingerprint_fn(record)
        current.add(fp)
        if fp not in previous:
            new_records.append(record)
    return new_records, current
