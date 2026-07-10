"""Append-only JSONL history in the platformdirs user-data directory.

Each line: {"expression": ..., "result": ..., "note": ..., "timestamp": ...}.
Only the display text is persisted — recalled entries re-evaluate through the
current session, so stored values can never go stale or disagree with the
engine. Corrupt lines are skipped, never fatal.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import platformdirs

MAX_LOADED_ENTRIES = 500


@dataclass(frozen=True)
class StoredEntry:
    expression: str
    result: str
    note: str = ""
    timestamp: float = 0.0


def default_path() -> Path:
    return Path(platformdirs.user_data_dir("calcutron", appauthor=False)) / "history.jsonl"


class HistoryStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_path()

    def load(self) -> list[StoredEntry]:
        if not self.path.exists():
            return []
        entries: list[StoredEntry] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                raw = json.loads(line)
                entries.append(
                    StoredEntry(
                        expression=str(raw["expression"]),
                        result=str(raw["result"]),
                        note=str(raw.get("note", "")),
                        timestamp=float(raw.get("timestamp", 0.0)),
                    )
                )
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue  # skip corrupt lines rather than losing the file
        return entries[-MAX_LOADED_ENTRIES:]

    def append(self, expression: str, result: str, note: str = "") -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "expression": expression,
            "result": result,
            "note": note,
            "timestamp": time.time(),
        }
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()
