"""Contextual visualization panel between the preview and the integer panel.

Shows the structured `viz` payload some toolkit results carry (fixed-point
layouts for now; clock and memory cards ride the same channel). The engine
computes every number in the payload — this widget only draws. Hidden when
the current value has no payload.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget

from calcutron.engine.viz import FixedPointViz, VizPayload
from calcutron.ui_qt.theme import Palette

VIZ_CELL = 18
VIZ_GAP = 3
POINT_GAP = 14  # widened gap holding the binary-point tick
MARGIN = 12
LINE_H = 24
BAR_H = VIZ_CELL + 4
METER_W = 140
METER_H = 8


class VizPanel(QWidget):
    def __init__(self, palette: Palette) -> None:
        super().__init__()
        self.setObjectName("vizPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.palette_tokens = palette
        self.payload: VizPayload | None = None
        self.hide()

    def set_palette(self, palette: Palette) -> None:
        self.palette_tokens = palette
        self.update()

    def show_payload(self, payload: VizPayload | None) -> None:
        self.payload = payload
        if payload is not None:
            self.setFixedHeight(8 + LINE_H + BAR_H + LINE_H + 10)
        self.setVisible(payload is not None)
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)  # QSS background/border
        if self.payload is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if isinstance(self.payload, FixedPointViz):
            self._paint_fixed(painter, self.payload)
        painter.end()

    # -- fixed-point Qm.n -------------------------------------------------------

    def _paint_fixed(self, painter: QPainter, viz: FixedPointViz) -> None:
        p = self.palette_tokens
        total = viz.m + viz.n
        font = painter.font()
        font.setPixelSize(15)
        painter.setFont(font)

        # Title: format + raw word.
        painter.setPen(QColor(p.text))
        title = f"Q{viz.m}.{viz.n}   raw 0x{viz.raw:X}"
        painter.drawText(QRectF(MARGIN, 8, self.width() - 2 * MARGIN, LINE_H),
                         Qt.AlignmentFlag.AlignVCenter, title)

        # Bit-cell bar: integer band (MSB cell = sign) | point | fraction band.
        cell = VIZ_CELL
        need = total * (cell + VIZ_GAP) + POINT_GAP + 2 * MARGIN
        if need > self.width():  # shrink to fit very wide formats
            cell = max(5, (self.width() - 2 * MARGIN - POINT_GAP) // total - VIZ_GAP)
        y = 8 + LINE_H
        for i in range(total):
            bit = total - 1 - i  # MSB first
            x = MARGIN + i * (cell + VIZ_GAP) + (POINT_GAP if bit < viz.n else 0)
            if bit == total - 1:
                base = p.float_sign  # two's-complement sign bit
            elif bit >= viz.n:
                base = p.float_exp  # integer bits
            else:
                base = p.float_man  # fraction bits
            color = QColor(base)
            if not (viz.raw >> bit) & 1:
                color.setAlphaF(0.22)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(QRectF(x, y, cell, VIZ_CELL), 2, 2)
        # Binary-point tick between integer and fraction bands.
        tick_x = MARGIN + viz.m * (cell + VIZ_GAP) + POINT_GAP / 2 - VIZ_GAP / 2
        painter.setPen(QColor(p.text))
        painter.drawLine(int(tick_x), y - 2, int(tick_x), y + VIZ_CELL + 2)

        # Decoded values + quantization-error meter (scale: 1/2 LSB = full).
        y2 = y + BAR_H
        painter.setPen(QColor(p.text))
        if viz.error_lsb == 0:
            text = f"value {viz.stored_text}  (exact)"
        else:
            text = (
                f"{viz.exact_text} -> {viz.stored_text}"
                f"   err {viz.error_text} ({viz.error_lsb:.2f} LSB)"
            )
        painter.drawText(QRectF(MARGIN, y2, self.width() - 2 * MARGIN, LINE_H),
                         Qt.AlignmentFlag.AlignVCenter, text)
        meter_x = self.width() - MARGIN - METER_W
        meter_y = y2 + (LINE_H - METER_H) / 2
        if meter_x > MARGIN + 380:  # only when it doesn't collide with the text
            track = QColor(p.bit_off)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(track)
            painter.drawRoundedRect(QRectF(meter_x, meter_y, METER_W, METER_H), 3, 3)
            frac = min(1.0, viz.error_lsb / 0.5)
            if frac > 0:
                painter.setBrush(QColor(p.bit_changed if frac > 0.5 else p.accent))
                painter.drawRoundedRect(QRectF(meter_x, meter_y, METER_W * frac, METER_H), 3, 3)
