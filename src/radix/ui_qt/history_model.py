"""History list: model + delegate rendering it as a ledger.

Two lines per entry (three with a note): a muted syntax-colored
`> expression`, then the result. An assignment paints a rounded chip with
the variable name instead of the `x ← ` prefix text; an integer result
gets a right-aligned alt-base chip (the dec/hex reading `session.int_base`
isn't currently showing) so the other base is visible without cycling it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

from PySide6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    QPersistentModelIndex,
    QRect,
    QSize,
    Qt,
)
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem

from radix.engine.values import Value
from radix.ui_qt.highlight import classify, color_for
from radix.ui_qt.theme import Palette

EXPRESSION_ROLE = Qt.ItemDataRole.UserRole + 1
RESULT_ROLE = Qt.ItemDataRole.UserRole + 2
NOTE_ROLE = Qt.ItemDataRole.UserRole + 3
VALUE_ROLE = Qt.ItemDataRole.UserRole + 4
PREFIX_ROLE = Qt.ItemDataRole.UserRole + 5

ROW_PAD_H = 8
ROW_PAD_V = 4
LINE_GAP = 2
BADGE_PAD_H = 6
BADGE_GAP = 8
ALT_CHIP_MAX_W = 90
ALT_CHIP_GAP = 10


@dataclass(frozen=True)
class HistoryEntry:
    expression: str
    result: str  # formatted primary text (or "x ← 12" for assignments)
    note: str = ""
    # The raw result value lets entries re-render when a display setting
    # (base, notation, word size) changes. Entries loaded from disk have
    # value=None and simply keep their recorded text.
    value: Value | None = None
    prefix: str = ""  # "x ← " for assignments, else ""
    timestamp: float = 0.0  # persistence only; not rendered


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
        if role == VALUE_ROLE:
            return entry.value
        if role == PREFIX_ROLE:
            return entry.prefix
        return None

    def append(self, entry: HistoryEntry) -> None:
        self.beginInsertRows(QModelIndex(), len(self.entries), len(self.entries))
        self.entries.append(entry)
        self.endInsertRows()

    def clear(self) -> None:
        self.beginResetModel()
        self.entries.clear()
        self.endResetModel()

    def remove(self, row: int) -> None:
        if 0 <= row < len(self.entries):
            self.beginRemoveRows(QModelIndex(), row, row)
            del self.entries[row]
            self.endRemoveRows()

    def reformat(self, primary: Callable[[Value], str]) -> None:
        """Rewrite results after a display setting (base/notation/…) change."""
        changed = False
        for i, entry in enumerate(self.entries):
            if entry.value is None:
                continue
            result = entry.prefix + primary(entry.value)
            if result != entry.result:
                self.entries[i] = replace(entry, result=result)
                changed = True
        if changed:
            first, last = self.index(0), self.index(len(self.entries) - 1)
            self.dataChanged.emit(first, last)


def _scaled(base: QFont, factor: float) -> QFont:
    """Scale a font whether it is pixel-sized (QSS px) or point-sized."""
    font = QFont(base)
    if base.pixelSize() > 0:
        font.setPixelSize(max(1, round(base.pixelSize() * factor)))
    else:
        font.setPointSizeF(max(1.0, base.pointSizeF() * factor))
    return font


class HistoryDelegate(QStyledItemDelegate):
    """`> expression` muted, then the result — assignment badge + alt-base chip."""

    def __init__(self, palette: Palette, alt_base: Callable[[Value], str | None]) -> None:
        super().__init__()
        self.palette_tokens = palette
        self.alt_base = alt_base  # closure over Session; no math happens in here

    def set_palette(self, palette: Palette) -> None:
        self.palette_tokens = palette

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        painter.save()
        rect = option.rect.adjusted(ROW_PAD_H, ROW_PAD_V, -ROW_PAD_H, -ROW_PAD_V)
        expression = index.data(EXPRESSION_ROLE) or ""
        result = index.data(RESULT_ROLE) or ""
        note = index.data(NOTE_ROLE) or ""
        prefix = index.data(PREFIX_ROLE) or ""
        value = index.data(VALUE_ROLE)
        p = self.palette_tokens

        expr_font = _scaled(option.font, 0.9)
        result_font = _scaled(option.font, 1.1)
        result_font.setBold(True)
        note_font = _scaled(option.font, 0.85)
        expr_h = QFontMetrics(expr_font).height()
        result_h = QFontMetrics(result_font).height()

        y = rect.top()
        painter.setFont(expr_font)
        expr_rect = QRect(rect.left(), y, rect.width(), expr_h)
        self._draw_highlighted(painter, expr_rect, expression)
        y += expr_h + LINE_GAP

        result_rect = QRect(rect.left(), y, rect.width(), result_h)
        result_metrics = QFontMetrics(result_font)
        x = result_rect.left()

        display_result = result
        if prefix:
            name = prefix.partition(" ←")[0]  # "x ← " -> "x"
            badge_w = result_metrics.horizontalAdvance(name) + 2 * BADGE_PAD_H
            badge_rect = QRect(x, result_rect.top() + 2, badge_w, result_rect.height() - 4)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(p.chip_bg))
            painter.drawRoundedRect(badge_rect, 8, 8)
            painter.setPen(QColor(p.accent))
            painter.setFont(result_font)
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, name)
            x += badge_w + BADGE_GAP
            display_result = result[len(prefix) :]

        alt_text = self.alt_base(value) if value is not None else None
        avail_w = result_rect.right() - x
        if alt_text:
            avail_w -= ALT_CHIP_MAX_W + ALT_CHIP_GAP

        painter.setFont(result_font)
        painter.setPen(QColor(p.text))
        painter.drawText(
            QRect(x, result_rect.top(), max(0, avail_w), result_rect.height()),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            display_result,
        )

        if alt_text:
            painter.setFont(note_font)
            painter.setPen(QColor(p.muted))
            alt_rect = QRect(
                result_rect.right() - ALT_CHIP_MAX_W,
                result_rect.top(),
                ALT_CHIP_MAX_W,
                result_rect.height(),
            )
            elided = QFontMetrics(note_font).elidedText(
                alt_text, Qt.TextElideMode.ElideRight, ALT_CHIP_MAX_W
            )
            painter.drawText(
                alt_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, elided
            )

        if note:
            y += result_h + LINE_GAP
            note_h = QFontMetrics(note_font).height()
            painter.setFont(note_font)
            painter.setPen(QColor(p.muted))
            note_rect = QRect(rect.left(), y, rect.width(), note_h)
            painter.drawText(
                note_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                f"({note})",
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
        expr_h = QFontMetrics(_scaled(option.font, 0.9)).height()
        result_h = QFontMetrics(_scaled(option.font, 1.1)).height()
        height = 2 * ROW_PAD_V + expr_h + LINE_GAP + result_h
        if index.data(NOTE_ROLE):
            note_h = QFontMetrics(_scaled(option.font, 0.85)).height()
            height += LINE_GAP + note_h
        return QSize(option.rect.width(), height)
