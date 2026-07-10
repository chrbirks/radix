"""Single-line expression input with syntax highlighting.

QLineEdit cannot render per-token colors, so this is a QPlainTextEdit
constrained to one line: Enter submits instead of inserting a newline,
pasted newlines are stripped, and the height is locked to one text row.
"""

from __future__ import annotations

from PySide6.QtCore import QMimeData, Qt, Signal
from PySide6.QtGui import QKeyEvent, QTextCursor
from PySide6.QtWidgets import QPlainTextEdit


class InputEdit(QPlainTextEdit):
    submitted = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setTabChangesFocus(True)
        self._lock_height()

    def _lock_height(self) -> None:
        height = self.fontMetrics().height() + 24  # matches the QSS padding
        self.setFixedHeight(height)

    def changeEvent(self, event: object) -> None:  # font/style changes
        super().changeEvent(event)  # type: ignore[arg-type]
        self._lock_height()

    # -- QLineEdit-compatible helpers -----------------------------------------

    def text(self) -> str:
        return self.toPlainText()

    def setText(self, text: str) -> None:
        self.setPlainText(text)
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(cursor)

    # -- single-line behavior ----------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.submitted.emit()
            return
        super().keyPressEvent(event)

    def insertFromMimeData(self, source: QMimeData) -> None:
        self.insertPlainText(" ".join(source.text().splitlines()))
