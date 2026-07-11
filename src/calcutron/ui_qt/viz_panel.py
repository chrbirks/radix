"""Contextual visualization panel between the preview and the integer panel.

Shows the structured `viz` payload some toolkit results carry (fixed-point,
clock, memory, and IEEE-754 cards all ride the same channel). The engine
computes every number in the payload — this widget only draws. Hidden when
the current value has no payload.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from calcutron.engine.viz import ClockViz, FixedPointViz, FloatBitsViz, MemViz, VizPayload
from calcutron.ui_qt.theme import Palette

VIZ_CELL = 18
VIZ_GAP = 3
POINT_GAP = 14  # widened gap holding the binary-point tick
MARGIN = 12
LINE_H = 24
BAR_H = VIZ_CELL + 4
METER_W = 140
METER_H = 8
# clkdiv error color thresholds (a UART is unhappy past ~2-3%).
CLK_ERR_WARN_PPM = 10_000  # 1%
CLK_ERR_BAD_PPM = 30_000  # 3%
# clkdiv waveform strip: drawn only while the divider is small enough to read.
WAVE_MAX_DIV = 16
WAVE_ROW_H = 18
WAVE_GAP = 4
WAVE_LABEL_W = 48
WAVE_STRIP_H = 2 * WAVE_ROW_H + WAVE_GAP + 6


def _has_wave(viz: ClockViz) -> bool:
    """True when the clock card draws the divided-clock waveform strip."""
    return (
        viz.divisor is not None
        and viz.divisor <= WAVE_MAX_DIV
        and viz.wave_high is not None
        and viz.wave_low is not None
    )


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
        if isinstance(payload, (FixedPointViz, FloatBitsViz)):
            self.setFixedHeight(8 + LINE_H + BAR_H + LINE_H + 10)
        elif isinstance(payload, ClockViz):
            lines = 2 if payload.divisor is not None else 1
            wave = WAVE_STRIP_H if _has_wave(payload) else 0
            self.setFixedHeight(8 + lines * LINE_H + wave + 10)
        elif isinstance(payload, MemViz):
            self.setFixedHeight(8 + 2 * LINE_H + 10)
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
        elif isinstance(self.payload, ClockViz):
            self._paint_clock(painter, self.payload)
        elif isinstance(self.payload, MemViz):
            self._paint_mem(painter, self.payload)
        elif isinstance(self.payload, FloatBitsViz):
            self._paint_floatbits(painter, self.payload)
        painter.end()

    # -- memory sizing ------------------------------------------------------------

    def _paint_mem(self, painter: QPainter, viz: MemViz) -> None:
        p = self.palette_tokens
        font = painter.font()
        font.setPixelSize(15)
        painter.setFont(font)
        painter.setPen(QColor(p.text))
        line = (
            f"{viz.depth} x {viz.width} bit    addr {viz.addr_bits} bits"
            f"    {viz.total_bits} bits = {viz.bytes_text}"
        )
        painter.drawText(QRectF(MARGIN, 8, self.width() - 2 * MARGIN, LINE_H),
                         Qt.AlignmentFlag.AlignVCenter, line)
        # Address-space utilization bar: full track = 2^addr_bits entries.
        y = 8 + LINE_H + (LINE_H - METER_H) / 2
        track_w = 200
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(p.bit_off))
        painter.drawRoundedRect(QRectF(MARGIN, y, track_w, METER_H), 3, 3)
        full = viz.utilization >= 1.0
        painter.setBrush(QColor(p.accent if full else p.bit_changed))
        painter.drawRoundedRect(QRectF(MARGIN, y, track_w * viz.utilization, METER_H), 3, 3)
        painter.setPen(QColor(p.muted))
        label = f"{viz.depth} / {viz.addressable} addressable ({viz.util_text})"
        if full:
            label += "  power of two"
        painter.drawText(
            QRectF(MARGIN + track_w + 10, 8 + LINE_H, self.width() - MARGIN, LINE_H),
            Qt.AlignmentFlag.AlignVCenter, label,
        )

    # -- clock / divider ---------------------------------------------------------

    def _paint_clock(self, painter: QPainter, viz: ClockViz) -> None:
        p = self.palette_tokens
        font = painter.font()
        font.setPixelSize(15)
        painter.setFont(font)
        painter.setPen(QColor(p.text))
        line = f"freq {viz.freq_text}Hz    period {viz.period_text}s"
        painter.drawText(QRectF(MARGIN, 8, self.width() - 2 * MARGIN, LINE_H),
                         Qt.AlignmentFlag.AlignVCenter, line)
        if viz.divisor is None:
            return
        y = 8 + LINE_H
        left = f"/ {viz.divisor}  ->  {viz.achieved_text}Hz  (target {viz.target_text}Hz)   "
        painter.drawText(QRectF(MARGIN, y, self.width() - 2 * MARGIN, LINE_H),
                         Qt.AlignmentFlag.AlignVCenter, left)
        # Error, color-coded against UART-style tolerance.
        ppm = abs(viz.error_ppm or 0.0)
        if ppm >= CLK_ERR_BAD_PPM:
            color = p.error
        elif ppm >= CLK_ERR_WARN_PPM:
            color = p.bit_changed
        else:
            color = p.float_exp
        painter.setPen(QColor(color))
        # QFontMetrics on painter fonts is safe here: the strings are ASCII.
        offset = painter.fontMetrics().horizontalAdvance(left)
        painter.drawText(QRectF(MARGIN + offset, y, self.width() - 2 * MARGIN - offset, LINE_H),
                         Qt.AlignmentFlag.AlignVCenter, f"err {viz.error_text}")

        # Waveform strip: two divided-output periods, rising edges aligned at x0.
        if not _has_wave(viz):
            return
        assert viz.wave_high is not None and viz.wave_low is not None
        high, low = viz.wave_high, viz.wave_low
        half_units = 4 * viz.divisor  # ref half-cycles across the strip
        x0 = MARGIN + WAVE_LABEL_W
        strip_w = min(self.width() - 2 * MARGIN - WAVE_LABEL_W, 420)
        px = strip_w / half_units

        def wave(y_row: float, spans: list[int]) -> QPolygonF:
            y_top, y_bot = y_row + 2.0, y_row + WAVE_ROW_H - 2.0
            pts = [QPointF(x0, y_bot)]
            x = float(x0)
            level_high = True
            for span in spans:
                y_level = y_top if level_high else y_bot
                pts.append(QPointF(x, y_level))
                x += span * px
                pts.append(QPointF(x, y_level))
                level_high = not level_high
            return QPolygonF(pts)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        rows = (
            ("clk", [1] * half_units, QPen(QColor(p.muted), 1.5)),
            (f"/{viz.divisor}", [high, low, high, low], QPen(QColor(p.accent), 2.0)),
        )
        for i, (label, spans, pen) in enumerate(rows):
            y_row = 8 + 2 * LINE_H + i * (WAVE_ROW_H + WAVE_GAP)
            painter.setPen(QColor(p.muted))
            painter.drawText(QRectF(MARGIN, y_row, WAVE_LABEL_W - 8, WAVE_ROW_H),
                             Qt.AlignmentFlag.AlignVCenter, label)
            painter.setPen(pen)
            painter.drawPolyline(wave(y_row, spans))
        if viz.duty_text is not None:
            duty = f"duty {viz.duty_text}"
            x_duty = x0 + strip_w + 10
            if x_duty + painter.fontMetrics().horizontalAdvance(duty) < self.width() - MARGIN:
                painter.setPen(QColor(p.muted))
                y_row = 8 + 2 * LINE_H + WAVE_ROW_H + WAVE_GAP
                painter.drawText(
                    QRectF(x_duty, y_row, self.width() - MARGIN - x_duty, WAVE_ROW_H),
                    Qt.AlignmentFlag.AlignVCenter, duty)

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

    # -- IEEE-754 float32/float64 -------------------------------------------------

    def _paint_floatbits(self, painter: QPainter, viz: FloatBitsViz) -> None:
        p = self.palette_tokens
        font = painter.font()
        font.setPixelSize(15)
        painter.setFont(font)

        # Title: format + stored value + raw pattern (+ the pre-rounding value).
        painter.setPen(QColor(p.text))
        title = f"float{viz.width}   {viz.stored_text}   raw {viz.hex_text}"
        if viz.rounded and viz.exact_text != viz.stored_text:
            title += f"   (from {viz.exact_text})"
        painter.drawText(QRectF(MARGIN, 8, self.width() - 2 * MARGIN, LINE_H),
                         Qt.AlignmentFlag.AlignVCenter, title)

        # Bit-cell bar: sign | exponent | mantissa bands, a field gap between each.
        cell = VIZ_CELL
        need = viz.width * (cell + VIZ_GAP) + 2 * POINT_GAP + 2 * MARGIN
        if need > self.width():  # shrink so 64 cells fit the minimum window
            cell = max(4, (self.width() - 2 * MARGIN - 2 * POINT_GAP) // viz.width - VIZ_GAP)
        y = 8 + LINE_H
        painter.setPen(Qt.PenStyle.NoPen)
        for i in range(viz.width):
            bit = viz.width - 1 - i  # MSB first
            if bit == viz.width - 1:
                base, shift = p.float_sign, 0  # sign cell
            elif bit >= viz.man_width:
                base, shift = p.float_exp, POINT_GAP  # exponent band
            else:
                base, shift = p.float_man, 2 * POINT_GAP  # mantissa band
            x = MARGIN + i * (cell + VIZ_GAP) + shift
            color = QColor(base)
            if not (viz.bits >> bit) & 1:
                color.setAlphaF(0.22)
            painter.setBrush(color)
            painter.drawRoundedRect(QRectF(x, y, cell, VIZ_CELL), 2, 2)

        # Decoded fields.
        painter.setPen(QColor(p.text))
        line = f"sign {viz.sign_text}   exp {viz.exponent_text}   man {viz.mantissa_text}"
        painter.drawText(QRectF(MARGIN, y + BAR_H, self.width() - 2 * MARGIN, LINE_H),
                         Qt.AlignmentFlag.AlignVCenter, line)
