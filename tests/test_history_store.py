"""History persistence tests (tmp_path — never the real user data dir)."""

from __future__ import annotations

import json
from pathlib import Path

from radix.history.store import HistoryStore, StoredEntry


def test_roundtrip(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "history.jsonl")
    store.append("4.7k * 2", "9400")
    store.append("fix(0.7071, 1, 15)", "23170", note="Q1.15")
    entries = store.load()
    assert [e.expression for e in entries] == ["4.7k * 2", "fix(0.7071, 1, 15)"]
    assert entries[1].note == "Q1.15"
    assert entries[0].timestamp > 0


def test_corrupt_lines_are_skipped(tmp_path: Path) -> None:
    path = tmp_path / "history.jsonl"
    store = HistoryStore(path)
    store.append("1+1", "2")
    with path.open("a", encoding="utf-8") as fh:
        fh.write("not json\n")
        fh.write('{"missing": "keys"}\n')
    store.append("2+2", "4")
    assert [e.result for e in store.load()] == ["2", "4"]


def test_clear_removes_file(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "history.jsonl")
    store.append("1", "1")
    store.clear()
    assert store.load() == []
    store.clear()  # idempotent on a missing file


def test_load_missing_file(tmp_path: Path) -> None:
    assert HistoryStore(tmp_path / "nope.jsonl").load() == []


def test_int_value_roundtrips(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "history.jsonl")
    store.append("0xFF", "255", value=255, prefix="")
    entries = store.load()
    assert entries[0].value == 255


def test_non_int_value_roundtrips_as_none(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "history.jsonl")
    store.append("sin(1)", "0.841470984808")
    entries = store.load()
    assert entries[0].value is None


def test_load_old_shape_without_value_or_prefix(tmp_path: Path) -> None:
    path = tmp_path / "history.jsonl"
    record = {"expression": "0xFF", "result": "255", "note": "", "timestamp": 123.0}
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    entries = HistoryStore(path).load()
    assert len(entries) == 1
    assert entries[0].value is None
    assert entries[0].prefix == ""


def test_rewrite_persists_value_and_prefix(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "history.jsonl")
    store.rewrite([StoredEntry("x = 0xFF", "x ← 255", value=255, prefix="x ← ")])
    entries = store.load()
    assert entries[0].value == 255
    assert entries[0].prefix == "x ← "
