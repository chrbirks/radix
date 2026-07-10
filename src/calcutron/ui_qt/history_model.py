"""History list: model + two-line delegate (muted expression, prominent result)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    QPersistentModelIndex,
    QRect,
    QSize,
    Qt,
)
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem

from calcutron.ui_qt.highlight import classify, color_for
from calcutron.ui_qt.theme import Palette

EXPRESSION_ROLE = Qt.ItemDataRole.UserRole + 1
RESULT_ROLE = Qt.ItemDataRole.UserRole + 2
NOTE_ROLE = Qt.ItemDataRole.UserRole + 3


@dataclass(frozen=True)
class HistoryEntry:
    expression: str
    result: str  # formatted primary text (or "x ← 12" for assignments)
    note: str = ""


class HistoryModel(QAbstractListModel):
    def __init__(self) -> None:
        super().__init__()
        self.entries: list[HistoryEntry] = []

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex | None = None) -> int:
        return len(self.entries)

    def data(self, index: QModelIndex | QPersistentModelIndex, role: int = 0) -> Any:
        if not index.isValid() or not 0 <= index.row() < len(self.entries):
            return None
        entry = self.entries[index.row()]
        if role == EXPRESSION_ROLE:
            return entry.expression
        if role in (RESULT_ROLE, Qt.ItemDataRole.DisplayRole):
            return entry.result
        if role == NOTE_ROLE:
            return entry.note
        return None

    def append(self, entry: HistoryEntry) -> None:
        self.beginInsertRows(QModelIndex(), len(self.entries), len(self.entries))
        self.entries.append(entry)
        self.endInsertRows()

    def clear(self) -> None:
        self.beginResetModel()
        self.entries.clear()
        self.endResetModel()


def _scaled(base: QFont, factor: float) -> QFont:
    """Scale a font whether it is pixel-sized (QSS px) or point-sized."""
    font = QFont(base)
    if base.pixelSize() > 0:
        font.setPixelSize(max(1, round(base.pixelSize() * factor)))
    else:
        font.setPointSizeF(max(1.0, base.pointSizeF() * factor))
    return font


class HistoryDelegate(QStyledItemDelegate):
    """Two lines per entry: `> expression` muted, result larger and stronger."""

    def __init__(self, palette: Palette) -> None:
        super().__init__()
        self.palette_tokens = palette

    def set_palette(self, palette: Palette) -> None:
        self.palette_tokens = palette

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        painter.save()
        rect = option.rect.adjusted(8, 4, -8, -4)
        expression = index.data(EXPRESSION_ROLE) or ""
        result = index.data(RESULT_ROLE) or ""
        note = index.data(NOTE_ROLE) or ""

        expr_font = _scaled(option.font, 0.9)
        result_font = _scaled(option.font, 1.1)
        result_font.setBold(True)

        painter.setFont(expr_font)
        expr_rect = QRect(rect.left(), rect.top(), rect.width(), rect.height() // 2)
        self._draw_highlighted(painter, expr_rect, expression)

        painter.setFont(result_font)
        painter.setPen(QColor(self.palette_tokens.text))
        result_rect = QRect(
            rect.left(), rect.top() + rect.height() // 2, rect.width(), rect.height() // 2
        )
        text = result if not note else f"{result}   ({note})"
        painter.drawText(
            result_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"  {text}",
        )
        painter.restore()

    def _draw_highlighted(self, painter: QPainter, rect: QRect, expression: str) -> None:
        """Paint `> expression` with the same token colors as the input field."""
        metrics = painter.fontMetrics()
        flags = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        palette = self.palette_tokens
        x = rect.left()

        def draw(text: str, color: QColor) -> None:
            nonlocal x
            if not text:
                return
            painter.setPen(color)
            painter.drawText(QRect(x, rect.top(), rect.right() - x, rect.height()), flags, text)
            x += metrics.horizontalAdvance(text)

        draw("> ", QColor(palette.muted))
        pos = 0
        for start, length, kind in classify(expression):
            draw(expression[pos:start], QColor(palette.muted))  # whitespace/unlexed gaps
            draw(expression[start : start + length], color_for(kind, palette))
            pos = start + length
        draw(expression[pos:], QColor(palette.muted))  # trailing unlexable rest

    def sizeHint(
        self, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex
    ) -> QSize:
        return QSize(option.rect.width(), 52)
