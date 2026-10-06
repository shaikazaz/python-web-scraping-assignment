import json
from pathlib import Path

from utils.state import compare_fingerprints, load_previous_fingerprints, save_fingerprints


def fp(record):
    return record["id"]


def test_state_round_trip_is_atomic(tmp_path: Path):
    path = tmp_path / "state" / "fingerprints.json"
    save_fingerprints(path, {"b", "a"})
    assert load_previous_fingerprints(path) == {"a", "b"}
    assert not (path.with_suffix(".json.tmp")).exists()


def test_compare_fingerprints_identifies_only_new_records():
    records = [{"id": "a"}, {"id": "b"}]
    new, current = compare_fingerprints(records, {"a"}, fp)
    assert new == [{"id": "b"}]
    assert current == {"a", "b"}
