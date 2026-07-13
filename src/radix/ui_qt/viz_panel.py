"""Contextual visualization panel between the preview and the integer panel.

Shows the structured `viz` payload some toolkit results carry (fixed-point,
clock, memory, and IEEE-754 cards all ride the same channel). The engine
computes every number in the payload — this widget only draws. Hidden when
the current value has no payload.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFontMetrics, QMouseEvent, QPainter, QPaintEvent, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from radix.engine.viz import ClockViz, FixedPointViz, FloatBitsViz, MemViz, VizPayload
from radix.ui_qt.theme import FONT_BODY, FONT_MICRO, Palette

VIZ_CELL = 18
VIZ_GAP = 3
POINT_GAP = 14  # widened gap holding the binary-point tick
CARD_PAD = 12
LINE_H = 24
BAR_H = VIZ_CELL + 4
METER_W = 140  # fixed-point quantization-error meter
METER_H = 8
METER_TRACK_W = 200  # mem-sizing address-space utilization bar
METER_MIN_CLEARANCE = 380  # skip the error meter if it would collide with the text
# clkdiv error color thresholds (a UART is unhappy past ~2-3%).
CLK_ERR_WARN_PPM = 10_000  # 1%
CLK_ERR_BAD_PPM = 30_000  # 3%
# clkdiv waveform strip: drawn only while the divider is small enough to read.
WAVE_MAX_DIV = 16
WAVE_ROW_H = 20
WAVE_GAP = 4
WAVE_LABEL_W = 100  # fits "T = 100us"-length labels at FONT_MICRO without clipping
WAVE_STRIP_MAX_W = 420
WAVE_STRIP_H = 2 * WAVE_ROW_H + WAVE_GAP + 6
TICK_H = 3  # rising-edge tick marks below each trace row


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
        self._hover_tip: str | None = None
        self.setMouseTracking(True)
        self.hide()

    def set_palette(self, palette: Palette) -> None:
        self.palette_tokens = palette
        self.update()

    def show_payload(self, payload: VizPayload | None) -> None:
        self.payload = payload
        self._hover_tip = None
        self.setToolTip("")
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
        font.setPixelSize(FONT_BODY)
        painter.setFont(font)
        painter.setPen(QColor(p.text))
        line = (
            f"{viz.depth} x {viz.width} bit    addr {viz.addr_bits} bits"
            f"    {viz.total_bits} bits = {viz.bytes_text}"
        )
        painter.drawText(QRectF(CARD_PAD, 8, self.width() - 2 * CARD_PAD, LINE_H),
                         Qt.AlignmentFlag.AlignVCenter, line)
        # Address-space utilization bar: full track = 2^addr_bits entries.
        y = 8 + LINE_H + (LINE_H - METER_H) / 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(p.bit_off))
        painter.drawRoundedRect(QRectF(CARD_PAD, y, METER_TRACK_W, METER_H), 3, 3)
        full = viz.utilization >= 1.0
        painter.setBrush(QColor(p.ok if full else p.bit_on))
        painter.drawRoundedRect(
            QRectF(CARD_PAD, y, METER_TRACK_W * viz.utilization, METER_H), 3, 3
        )
        painter.setPen(QColor(p.muted))
        label = f"{viz.depth} / {viz.addressable} addressable ({viz.util_text})"
        if full:
            label += "  power of two"
        painter.drawText(
            QRectF(CARD_PAD + METER_TRACK_W + 10, 8 + LINE_H, self.width() - CARD_PAD, LINE_H),
            Qt.AlignmentFlag.AlignVCenter, label,
        )

    # -- clock / divider ---------------------------------------------------------

    def _paint_clock(self, painter: QPainter, viz: ClockViz) -> None:
        p = self.palette_tokens
        font = painter.font()
        font.setPixelSize(FONT_BODY)
        painter.setFont(font)
        painter.setPen(QColor(p.text))
        line = f"freq {viz.freq_text}Hz    period {viz.period_text}s"
        painter.drawText(QRectF(CARD_PAD, 8, self.width() - 2 * CARD_PAD, LINE_H),
                         Qt.AlignmentFlag.AlignVCenter, line)
        if viz.divisor is None:
            return
        y = 8 + LINE_H
        left = f"/ {viz.divisor}  ->  {viz.achieved_text}Hz  (target {viz.target_text}Hz)   "
        painter.drawText(QRectF(CARD_PAD, y, self.width() - 2 * CARD_PAD, LINE_H),
                         Qt.AlignmentFlag.AlignVCenter, left)
        # Error, color-coded against UART-style tolerance.
        ppm = abs(viz.error_ppm or 0.0)
        if ppm >= CLK_ERR_BAD_PPM:
            color = p.error
        elif ppm >= CLK_ERR_WARN_PPM:
            color = p.warn
        else:
            color = p.ok
        painter.setPen(QColor(color))
        # QFontMetrics on painter fonts is safe here: the strings are ASCII.
        offset = painter.fontMetrics().horizontalAdvance(left)
        painter.drawText(QRectF(CARD_PAD + offset, y, self.width() - 2 * CARD_PAD - offset, LINE_H),
                         Qt.AlignmentFlag.AlignVCenter, f"err {viz.error_text}")

        # Waveform strip: two divided-output periods, rising edges aligned at x0.
        if not _has_wave(viz):
            return
        assert viz.wave_high is not None and viz.wave_low is not None
        high, low = viz.wave_high, viz.wave_low
        x0, strip_w, half_units = self._wave_geometry(viz)
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

        def rising_edges(spans: list[int]) -> list[float]:
            """X positions where the trace goes low -> high (always starts on one)."""
            xs = [float(x0)]
            x = float(x0)
            level_high = True
            for span in spans:
                x += span * px
                level_high = not level_high
                if level_high:
                    xs.append(x)
            return xs

        label_font = painter.font()
        label_font.setPixelSize(FONT_MICRO)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        rows = (
            (f"T = {viz.period_text}s", [1] * half_units, p.muted, 1.5),
            (f"{viz.achieved_text}Hz", [high, low, high, low], p.bit_on, 2.0),
        )
        for i, (label, spans, color, width) in enumerate(rows):
            y_row = 8 + 2 * LINE_H + i * (WAVE_ROW_H + WAVE_GAP)
            y_bot = y_row + WAVE_ROW_H - 2.0
            # Hairline baseline under the trace, sharp square joins on the trace itself.
            painter.setPen(QPen(QColor(p.hairline), 1))
            painter.drawLine(QPointF(x0, y_bot), QPointF(x0 + strip_w, y_bot))
            painter.setFont(label_font)
            painter.setPen(QColor(p.muted))
            painter.drawText(QRectF(CARD_PAD, y_row, WAVE_LABEL_W - 8, WAVE_ROW_H),
                             Qt.AlignmentFlag.AlignVCenter, label)
            pen = QPen(QColor(color), width)
            pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
            painter.setPen(pen)
            painter.drawPolyline(wave(y_row, spans))
            painter.setPen(QPen(QColor(color), 1))
            for tick_x in rising_edges(spans):
                painter.drawLine(QPointF(tick_x, y_bot + 1), QPointF(tick_x, y_bot + 1 + TICK_H))
        if viz.duty_text is not None:
            duty = f"duty {viz.duty_text}"
            x_duty = x0 + strip_w + 10
            painter.setFont(label_font)
            if x_duty + painter.fontMetrics().horizontalAdvance(duty) < self.width() - CARD_PAD:
                painter.setPen(QColor(p.muted))
                y_row = 8 + 2 * LINE_H + WAVE_ROW_H + WAVE_GAP
                painter.drawText(
                    QRectF(x_duty, y_row, self.width() - CARD_PAD - x_duty, WAVE_ROW_H),
                    Qt.AlignmentFlag.AlignVCenter, duty)

    # -- fixed-point Qm.n -------------------------------------------------------

    def _paint_fixed(self, painter: QPainter, viz: FixedPointViz) -> None:
        p = self.palette_tokens
        total = viz.m + viz.n
        font = painter.font()
        font.setPixelSize(FONT_BODY)
        painter.setFont(font)

        # Title: format + raw word.
        painter.setPen(QColor(p.text))
        title = f"Q{viz.m}.{viz.n}   raw 0x{viz.raw:X}"
        painter.drawText(QRectF(CARD_PAD, 8, self.width() - 2 * CARD_PAD, LINE_H),
                         Qt.AlignmentFlag.AlignVCenter, title)

        # Bit-cell bar: integer band (MSB cell = sign) | point | fraction band.
        cell, y = self._fixed_geometry(total)
        for i in range(total):
            bit = total - 1 - i  # MSB first
            x = CARD_PAD + i * (cell + VIZ_GAP) + (POINT_GAP if bit < viz.n else 0)
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
        tick_x = CARD_PAD + viz.m * (cell + VIZ_GAP) + POINT_GAP / 2 - VIZ_GAP / 2
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
        painter.drawText(QRectF(CARD_PAD, y2, self.width() - 2 * CARD_PAD, LINE_H),
                         Qt.AlignmentFlag.AlignVCenter, text)
        meter_x = self.width() - CARD_PAD - METER_W
        meter_y = y2 + (LINE_H - METER_H) / 2
        if meter_x > CARD_PAD + METER_MIN_CLEARANCE:  # skip if it'd collide with the text
            track = QColor(p.bit_off)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(track)
            painter.drawRoundedRect(QRectF(meter_x, meter_y, METER_W, METER_H), 3, 3)
            frac = min(1.0, viz.error_lsb / 0.5)
            if frac > 0:
                painter.setBrush(QColor(p.warn if frac > 0.5 else p.ok))
                painter.drawRoundedRect(QRectF(meter_x, meter_y, METER_W * frac, METER_H), 3, 3)

    # -- IEEE-754 float32/float64 -------------------------------------------------

    def _paint_floatbits(self, painter: QPainter, viz: FloatBitsViz) -> None:
        p = self.palette_tokens
        font = painter.font()
        font.setPixelSize(FONT_BODY)
        painter.setFont(font)

        # Title: format + stored value + raw pattern (+ the pre-rounding value).
        painter.setPen(QColor(p.text))
        title = f"float{viz.width}   {viz.stored_text}   raw {viz.hex_text}"
        if viz.rounded and viz.exact_text != viz.stored_text:
            title += f"   (from {viz.exact_text})"
        painter.drawText(QRectF(CARD_PAD, 8, self.width() - 2 * CARD_PAD, LINE_H),
                         Qt.AlignmentFlag.AlignVCenter, title)

        # Bit-cell bar: sign | exponent | mantissa bands, a field gap between each.
        cell, y = self._floatbits_geometry(viz.width)
        painter.setPen(Qt.PenStyle.NoPen)
        for i in range(viz.width):
            bit = viz.width - 1 - i  # MSB first
            if bit == viz.width - 1:
                base, shift = p.float_sign, 0  # sign cell
            elif bit >= viz.man_width:
                base, shift = p.float_exp, POINT_GAP  # exponent band
            else:
                base, shift = p.float_man, 2 * POINT_GAP  # mantissa band
            x = CARD_PAD + i * (cell + VIZ_GAP) + shift
            color = QColor(base)
            if not (viz.bits >> bit) & 1:
                color.setAlphaF(0.22)
            painter.setBrush(color)
            painter.drawRoundedRect(QRectF(x, y, cell, VIZ_CELL), 2, 2)

        # Decoded fields.
        painter.setPen(QColor(p.text))
        line = f"sign {viz.sign_text}   exp {viz.exponent_text}   man {viz.mantissa_text}"
        painter.drawText(QRectF(CARD_PAD, y + BAR_H, self.width() - 2 * CARD_PAD, LINE_H),
                         Qt.AlignmentFlag.AlignVCenter, line)

    # -- hover tooltips -----------------------------------------------------------
    # Geometry helpers below are shared with the matching _paint_* method so the
    # hit-test grid never drifts from what's actually drawn.

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        tooltip = self._tooltip_at(event.position()) if self.payload is not None else None
        if tooltip == self._hover_tip:
            return
        self._hover_tip = tooltip
        self.setToolTip(tooltip or "")

    def _tooltip_at(self, pos: QPointF) -> str | None:
        if isinstance(self.payload, FixedPointViz):
            bit = self._fixed_bit_at(self.payload, pos)
            return None if bit is None else self._fixed_bit_tooltip(self.payload, bit)
        if isinstance(self.payload, FloatBitsViz):
            bit = self._floatbits_bit_at(self.payload, pos)
            return None if bit is None else self._floatbits_bit_tooltip(self.payload, bit)
        if isinstance(self.payload, ClockViz):
            return self._clock_tooltip(self.payload, pos)
        return None

    def _fixed_geometry(self, total: int) -> tuple[int, int]:
        cell = VIZ_CELL
        need = total * (cell + VIZ_GAP) + POINT_GAP + 2 * CARD_PAD
        if need > self.width():  # shrink to fit very wide formats
            cell = max(5, (self.width() - 2 * CARD_PAD - POINT_GAP) // total - VIZ_GAP)
        return cell, 8 + LINE_H

    def _fixed_bit_at(self, viz: FixedPointViz, pos: QPointF) -> int | None:
        total = viz.m + viz.n
        cell, y = self._fixed_geometry(total)
        for bit in range(total):
            i = total - 1 - bit
            x = CARD_PAD + i * (cell + VIZ_GAP) + (POINT_GAP if bit < viz.n else 0)
            if QRectF(x, y, cell, VIZ_CELL).contains(pos):
                return bit
        return None

    def _fixed_bit_tooltip(self, viz: FixedPointViz, bit: int) -> str:
        state = (viz.raw >> bit) & 1
        total = viz.m + viz.n
        if bit == total - 1:
            field = f"sign, weight -2^{viz.m - 1}"
        elif bit >= viz.n:
            field = f"integer bit, weight 2^{bit - viz.n}"
        else:
            field = f"fraction bit, weight 2^-{viz.n - bit}"
        return f"bit {bit} = {state}   {field}"

    def _floatbits_geometry(self, width: int) -> tuple[int, int]:
        cell = VIZ_CELL
        need = width * (cell + VIZ_GAP) + 2 * POINT_GAP + 2 * CARD_PAD
        if need > self.width():  # shrink so 64 cells fit the minimum window
            cell = max(4, (self.width() - 2 * CARD_PAD - 2 * POINT_GAP) // width - VIZ_GAP)
        return cell, 8 + LINE_H

    def _floatbits_bit_at(self, viz: FloatBitsViz, pos: QPointF) -> int | None:
        cell, y = self._floatbits_geometry(viz.width)
        for bit in range(viz.width):
            i = viz.width - 1 - bit
            if bit == viz.width - 1:
                shift = 0
            elif bit >= viz.man_width:
                shift = POINT_GAP
            else:
                shift = 2 * POINT_GAP
            x = CARD_PAD + i * (cell + VIZ_GAP) + shift
            if QRectF(x, y, cell, VIZ_CELL).contains(pos):
                return bit
        return None

    def _floatbits_bit_tooltip(self, viz: FloatBitsViz, bit: int) -> str:
        state = (viz.bits >> bit) & 1
        if bit == viz.width - 1:
            field = "sign"
        elif bit >= viz.man_width:
            field = f"exponent bit {bit - viz.man_width}"
        else:
            field = f"mantissa bit {bit}"
        return f"bit {bit} = {state}   {field}"

    def _clock_tooltip(self, viz: ClockViz, pos: QPointF) -> str | None:
        err_hit = viz.divisor is not None and viz.error_ppm is not None
        if err_hit and self._clock_err_rect(viz).contains(pos):
            return self._clock_err_tooltip(viz)
        if _has_wave(viz):
            assert viz.wave_high is not None and viz.wave_low is not None
            x0, strip_w, half_units = self._wave_geometry(viz)
            px = strip_w / half_units
            for i, spans, label in (
                (0, [1] * half_units, "reference clock"),
                (
                    1,
                    [viz.wave_high, viz.wave_low, viz.wave_high, viz.wave_low],
                    f"divided output ({viz.achieved_text}Hz)",
                ),
            ):
                y_row = 8 + 2 * LINE_H + i * (WAVE_ROW_H + WAVE_GAP)
                if QRectF(x0, y_row, strip_w, WAVE_ROW_H).contains(pos):
                    level = self._level_at(spans, (pos.x() - x0) / px)
                    return f"{label} — {'high' if level else 'low'}"
        return None

    def _wave_geometry(self, viz: ClockViz) -> tuple[float, float, int]:
        assert viz.divisor is not None
        half_units = 4 * viz.divisor
        x0 = CARD_PAD + WAVE_LABEL_W
        strip_w = min(self.width() - 2 * CARD_PAD - WAVE_LABEL_W, WAVE_STRIP_MAX_W)
        return x0, strip_w, half_units

    @staticmethod
    def _level_at(spans: list[int], units: float) -> bool:
        """Trace level at a given x position, in half-cycle units from the left edge."""
        x = 0.0
        level_high = True
        for span in spans:
            if units < x + span:
                return level_high
            x += span
            level_high = not level_high
        return level_high

    def _clock_err_rect(self, viz: ClockViz) -> QRectF:
        font = self.font()
        font.setPixelSize(FONT_BODY)
        fm = QFontMetrics(font)
        left = f"/ {viz.divisor}  ->  {viz.achieved_text}Hz  (target {viz.target_text}Hz)   "
        offset = fm.horizontalAdvance(left)
        y = 8 + LINE_H
        return QRectF(CARD_PAD + offset, y, self.width() - 2 * CARD_PAD - offset, LINE_H)

    def _clock_err_tooltip(self, viz: ClockViz) -> str:
        ppm = abs(viz.error_ppm or 0.0)
        warn_pct = CLK_ERR_WARN_PPM / 10_000
        bad_pct = CLK_ERR_BAD_PPM / 10_000
        if ppm >= CLK_ERR_BAD_PPM:
            level = "bad"
        elif ppm >= CLK_ERR_WARN_PPM:
            level = "warn"
        else:
            level = "ok"
        return (
            f"{level}: err {viz.error_text}   "
            f"(ok <{warn_pct:.0f}%, warn {warn_pct:.0f}-{bad_pct:.0f}%, "
            f"bad >{bad_pct:.0f}% — typical UART tolerance)"
        )
