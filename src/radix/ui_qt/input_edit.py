"""Single-line expression input with syntax highlighting.

QLineEdit cannot render per-token colors, so this is a QPlainTextEdit
constrained to one line: Enter submits instead of inserting a newline,
pasted newlines are stripped, and the height is locked to one text row.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QMimeData, Qt, Signal
from PySide6.QtGui import QFontMetrics, QKeyEvent, QTextCursor
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPlainTextEdit, QVBoxLayout, QWidget


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
        height = QFontMetrics(self.font()).height() + 24  # matches the QSS padding
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


class InputBar(QWidget):
    """Prompt glyph + expression input + live preview, styled as one control.

    Grows an accent underline while `input` has focus (the `focused` dynamic
    property), so the always-focused input line still gives visible feedback
    when focus briefly leaves it (e.g. a history double-click).
    """

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("inputBar")
        self.setProperty("focused", "false")

        self.prompt = QLabel("›")
        self.prompt.setObjectName("prompt")

        self.input = InputEdit()
        self.input.setObjectName("input")
        self.input.installEventFilter(self)

        self.preview = QLabel(" ")
        self.preview.setObjectName("preview")

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addWidget(self.prompt)
        row.addWidget(self.input, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(row)
        layout.addWidget(self.preview)

    def eventFilter(self, obj: object, event: QEvent) -> bool:
        if obj is self.input and event.type() in (
            QEvent.Type.FocusIn,
            QEvent.Type.FocusOut,
        ):
            self._set_focused(event.type() == QEvent.Type.FocusIn)
        return super().eventFilter(obj, event)  # type: ignore[arg-type]

    def _set_focused(self, focused: bool) -> None:
        self.setProperty("focused", "true" if focused else "false")
        self.style().unpolish(self)
        self.style().polish(self)
