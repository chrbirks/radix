"""Append-only JSONL history in the platformdirs user-data directory.

Each line: {"expression": ..., "result": ..., "note": ..., "timestamp": ...,
"value": ..., "prefix": ...}. Mostly the display text is persisted — recalled
entries re-evaluate through the current session, so stored text can never
disagree with the engine. `value` is the exception: for int-valued entries
the raw integer is also persisted (alongside `prefix`, the assignment badge
text) so they can still reformat on a base/notation change after a restart,
same as `channels.py` does for its own int channels. Floats stay
text-only. Corrupt lines are skipped, never fatal.
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
    value: int | None = None
    prefix: str = ""


def default_path() -> Path:
    return Path(platformdirs.user_data_dir("radix", appauthor=False)) / "history.jsonl"


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
                        value=int(raw["value"]) if raw.get("value") is not None else None,
                        prefix=str(raw.get("prefix", "")),
                    )
                )
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue  # skip corrupt lines rather than losing the file
        return entries[-MAX_LOADED_ENTRIES:]

    def append(
        self,
        expression: str,
        result: str,
        note: str = "",
        value: int | None = None,
        prefix: str = "",
    ) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "expression": expression,
            "result": result,
            "note": note,
            "timestamp": time.time(),
            "value": value,
            "prefix": prefix,
        }
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")

    def rewrite(self, entries: list[StoredEntry]) -> None:
        """Replace the file's contents (after deleting an entry from the UI)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as fh:
            for entry in entries:
                record = {
                    "expression": entry.expression,
                    "result": entry.result,
                    "note": entry.note,
                    "timestamp": entry.timestamp,
                    "value": entry.value,
                    "prefix": entry.prefix,
                }
                fh.write(json.dumps(record) + "\n")

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()
