"""Integer view: hex/dec/bin rows with per-base copy, plus clickable bit rows.

The panel shows a *scratch* value seeded from the latest integer result.
Clicking a bit cell toggles that bit of the scratch value, re-renders all
bases, and writes the new value into the input line as a hex literal (the
"-> input" button does the same on demand). A new result reseeds the scratch.
Float results grey the panel.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent, QPen, QResizeEvent
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from radix.engine.formatter import FloatViews, format_int_base, integer_views
from radix.ui_qt.theme import FONT_MICRO, Palette

CELL = 24
GAP = 4
NIBBLE_GAP = 10
HEX_H = 18  # strip above each cell row for per-nibble hex digits
INDEX_H = 18  # strip below each cell row for bit-index labels
ROW_H = HEX_H + CELL + GAP + INDEX_H
BYTE_WIDTH = 8 * (CELL + GAP) + 2 * NIBBLE_GAP  # one byte group incl. nibble gaps
LANE_ROWS = 4  # max simultaneous lanes (HEX/DEC/BIN/ASC, or HEX/SGN/EXP/MAN)
RAIL_H = 22  # collapsed / collapse-affordance strip height
COLLAPSE_THRESHOLD_ROWS = 2  # only worth collapsing when >=2 full rows are all-zero


class BitGrid(QWidget):
    """Clickable bit cells, MSB top-left.

    The grid fills the available width and wraps at byte boundaries, so every
    bit stays visible at any window width and word size (no clipping from
    stale size hints).
    """

    bit_toggled = Signal(int)  # bit index
    selection_changed = Signal()  # read .selection for the current (hi, lo)

    def __init__(self, palette: Palette) -> None:
        super().__init__()
        self.palette_tokens = palette
        self.word_size = 64
        self.value = 0
        self.changed = 0  # bits that flipped vs. the previous value (outlined)
        self.enabled_look = True
        self.selection: tuple[int, int] | None = None  # (hi, lo) drag-selected range
        # (exp_width, man_width) when showing an IEEE-754 pattern: cells get
        # sign/exponent/mantissa band colors and become read-only.
        self.float_fields: tuple[int, int] | None = None
        self.expanded = False  # user override: show all rows despite the rail
        self._hover_bit: int | None = None
        self._press_bit: int | None = None
        self._dragging = False
        self.setMouseTracking(True)
        self._apply_height()

    def set_state(
        self,
        value: int,
        word_size: int,
        enabled: bool,
        changed: int = 0,
        float_fields: tuple[int, int] | None = None,
    ) -> None:
        self.value = value
        self.word_size = word_size
        self.enabled_look = enabled
        self.changed = changed
        self.float_fields = float_fields
        if self._leading_zero_rows() < COLLAPSE_THRESHOLD_ROWS:
            self.expanded = False  # a value with upper bits resumes auto-collapse
        self._apply_height()
        self.update()

    def toggle_expanded(self) -> None:
        self.expanded = not self.expanded
        self._apply_height()
        self.update()

    def _leading_zero_rows(self) -> int:
        """Leading (MSB-side) full rows that are all-zero in value and
        changed, and outside the selection — regardless of `expanded`."""
        if self.float_fields is not None:
            return 0
        per_row = self._bits_per_row()
        count = 0
        for row in range(self._rows()):
            hi_bit = self.word_size - 1 - row * per_row
            lo_bit = max(0, self.word_size - (row + 1) * per_row)
            row_mask = ((1 << (hi_bit - lo_bit + 1)) - 1) << lo_bit
            if (self.value & row_mask) or (self.changed & row_mask):
                break
            if self.selection is not None:
                hi, lo = self.selection
                if not (hi < lo_bit or lo > hi_bit):
                    break
            count += 1
        return count

    def _collapse_eligible(self) -> bool:
        return self._leading_zero_rows() >= COLLAPSE_THRESHOLD_ROWS

    def _hidden_rows(self) -> int:
        """Rows actually hidden behind the collapsed rail right now."""
        if self.expanded or not self._collapse_eligible():
            return 0
        return self._leading_zero_rows()

    def _rail_rect(self) -> QRectF:
        return QRectF(4, 4, max(0, self.width() - 8), RAIL_H - 4)

    def _field_of(self, bit: int) -> str:
        """"sign" / "exponent" / "mantissa" for a bit in float mode."""
        assert self.float_fields is not None
        _, man_width = self.float_fields
        if bit == self.word_size - 1:
            return "sign"
        return "exponent" if bit >= man_width else "mantissa"

    def set_palette(self, palette: Palette) -> None:
        self.palette_tokens = palette
        self.update()

    def _bits_per_row(self) -> int:
        usable = max(self.width() - 8, BYTE_WIDTH)
        bytes_fit = max(1, (usable + NIBBLE_GAP) // BYTE_WIDTH)
        return min(self.word_size, 8 * bytes_fit)

    def _rows(self) -> int:
        per_row = self._bits_per_row()
        return (self.word_size + per_row - 1) // per_row

    def _rail_extra(self) -> int:
        return RAIL_H if self._collapse_eligible() else 0

    def _apply_height(self) -> None:
        visible_rows = self._rows() - self._hidden_rows()
        self.setMinimumHeight(visible_rows * ROW_H + self._rail_extra() + 8)

    def resizeEvent(self, event: QResizeEvent) -> None:
        self._apply_height()
        super().resizeEvent(event)

    def _cell_rect(self, bit: int) -> QRectF:
        """Rect for a bit index (0 = LSB). MSB is top-left.

        Bits hidden behind the collapsed rail return an empty rect, so
        `_bit_at` can never select them — a collapsed bit requires
        expanding first.
        """
        per_row = self._bits_per_row()
        pos = self.word_size - 1 - bit  # 0 for MSB
        row, col = divmod(pos, per_row)
        hidden = self._hidden_rows()
        if row < hidden:
            return QRectF()
        visible_row = row - hidden
        nibble_gaps = col // 4
        x = 4 + col * (CELL + GAP) + nibble_gaps * NIBBLE_GAP
        y = 4 + self._rail_extra() + visible_row * ROW_H + HEX_H
        return QRectF(x, y, CELL, CELL)

    def sizeHint(self) -> QSize:
        visible_rows = self._rows() - self._hidden_rows()
        return QSize(2 * BYTE_WIDTH, visible_rows * ROW_H + self._rail_extra() + 8)

    def _paint_rail(self, painter: QPainter) -> None:
        p = self.palette_tokens
        rect = self._rail_rect()
        painter.setPen(QPen(QColor(p.hairline), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, 3, 3)
        font = painter.font()
        font.setPixelSize(FONT_MICRO)
        painter.setFont(font)
        painter.setPen(QColor(p.muted))
        if self.expanded:
            text = "^ collapse"
        else:
            hidden = self._hidden_rows()
            per_row = self._bits_per_row()
            hi = self.word_size - 1
            lo = self.word_size - hidden * per_row
            text = f"… bits {hi}…{lo} = 0 — click to expand"
        painter.drawText(rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter, text)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        p = self.palette_tokens
        if self._collapse_eligible():
            self._paint_rail(painter)
        on = QColor(p.bit_on if self.enabled_look else p.bit_off)
        off = QColor(p.bit_off)
        off.setAlphaF(0.6 if not self.enabled_look else 1.0)
        field_colors = {"sign": p.float_sign, "exponent": p.float_exp, "mantissa": p.float_man}
        for bit in range(self.word_size):
            rect = self._cell_rect(bit)
            if rect.isEmpty():
                continue
            set_ = (self.value >> bit) & 1
            if self.float_fields is not None and self.enabled_look:
                color = QColor(field_colors[self._field_of(bit)])
                if not set_:
                    color.setAlphaF(0.22)
                brush = color
            else:
                brush = on if set_ else off
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(brush)
            painter.drawRoundedRect(rect, 2, 2)
        # Drag-selected range: translucent cursor-amber band + text-color
        # outline (visible over both set and unset cells).
        if self.enabled_look and self.selection is not None:
            hi, lo = self.selection
            band = QColor(p.bit_changed)
            band.setAlphaF(0.25)
            painter.setBrush(band)
            painter.setPen(QPen(QColor(p.text), 1.5))
            for bit in range(lo, min(hi, self.word_size - 1) + 1):
                painter.drawRoundedRect(self._cell_rect(bit).adjusted(-1, -1, 1, 1), 3, 3)
        label_font = painter.font()
        label_font.setPixelSize(16)
        painter.setFont(label_font)
        # Per-nibble hex digit above each 4-cell group (muted when zero,
        # phosphor trace color when set).
        for nibble in range(self.word_size // 4):
            digit = (self.value >> (4 * nibble)) & 0xF
            msb_cell = self._cell_rect(4 * nibble + 3)
            lsb_cell = self._cell_rect(4 * nibble)
            if msb_cell.isEmpty():
                continue
            hex_rect = QRectF(
                msb_cell.left(),
                msb_cell.top() - HEX_H,
                lsb_cell.right() - msb_cell.left(),
                HEX_H - 2,
            )
            strong = self.enabled_look and digit != 0
            painter.setPen(QColor(p.bit_on if strong else p.muted))
            painter.drawText(
                hex_rect,
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom,
                f"{digit:X}",
            )
        # Bit-index labels under each nibble's MSB cell (63, 59, … 3), plus bit 0.
        index_font = painter.font()
        index_font.setPixelSize(FONT_MICRO)
        painter.setFont(index_font)
        painter.setPen(QColor(self.palette_tokens.muted))
        for bit in range(self.word_size):
            if bit % 4 == 3 or bit == 0:
                cell = self._cell_rect(bit)
                if cell.isEmpty():
                    continue
                label_rect = QRectF(cell.left() - GAP, cell.bottom() + 1, CELL + 2 * GAP, INDEX_H)
                painter.drawText(label_rect, Qt.AlignmentFlag.AlignHCenter, str(bit))
        painter.end()

    def _bit_at(self, pos: QPointF) -> int | None:
        for bit in range(self.word_size):
            if self._cell_rect(bit).contains(pos):
                return bit
        return None

    def set_selection(self, selection: tuple[int, int] | None) -> None:
        if selection == self.selection:
            return
        self.selection = selection
        self.selection_changed.emit()
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._collapse_eligible() and self._rail_rect().contains(event.position()):
            self.toggle_expanded()
            return
        if not self.enabled_look or self.float_fields is not None:  # float view: read-only
            return
        self._press_bit = self._bit_at(event.position())
        self._dragging = False
        if self._press_bit is None:
            self.set_selection(None)  # click outside the cells clears the range

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        bit = self._bit_at(event.position())
        # Drag with the left button held: extend the (hi, lo) selection.
        if (
            self.enabled_look
            and self._press_bit is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            if bit is not None and bit != self._press_bit:
                self._dragging = True
            if self._dragging and bit is not None:
                self.set_selection((max(bit, self._press_bit), min(bit, self._press_bit)))
        if bit == self._hover_bit:
            return
        self._hover_bit = bit
        if bit is None or not self.enabled_look:
            self.setToolTip("")
            return
        state = (self.value >> bit) & 1
        if self.float_fields is not None:
            self.setToolTip(f"bit {bit} = {state}    {self._field_of(bit)}")
        else:
            self.setToolTip(
                f"bit {bit} = {state}    2^{bit} = {1 << bit}    byte {bit // 8}, nibble {bit // 4}"
            )

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self.enabled_look and self._press_bit is not None and not self._dragging:
            self.set_selection(None)  # a plain click both toggles and deselects
            self.bit_toggled.emit(self._press_bit)
        self._press_bit = None
        self._dragging = False


class IntegerView(QWidget):
    """The whole bottom panel: base rows + bit grid + actions."""

    value_to_input = Signal(str)
    copied = Signal(str)  # human description for the status-bar toast

    def __init__(self, palette: Palette, clipboard_setter: Callable[[str], None]) -> None:
        super().__init__()
        self.setObjectName("intview")
        self.palette_tokens = palette
        self._clipboard = clipboard_setter
        self.scratch = 0
        self.changed = 0  # bits that flipped vs. the previously shown value
        self.word_size = 64
        self.signed = False
        self.active = False
        self.float_mode: FloatViews | None = None  # read-only IEEE-754 display

        self.rows: dict[str, tuple[QLabel, QLabel]] = {}
        self._copy_texts: dict[str, str] = {}
        self._row_keys: list[str | None] = [None] * LANE_ROWS
        self._row_widgets: list[tuple[QLabel, QLabel, QPushButton]] = []
        grid = QGridLayout()
        grid.setContentsMargins(12, 8, 12, 4)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(2)
        for i in range(LANE_ROWS):
            name = QLabel("")
            name.setProperty("class", "laneName")
            value = QLabel("")
            value.setProperty("class", "laneValue")
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            value.setWordWrap(True)  # BIN at 64-bit is ~80 chars wide; wrap at nibble gaps
            copy_btn = QPushButton("copy")
            copy_btn.setProperty("class", "copyBtn")
            copy_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            copy_btn.clicked.connect(lambda _=False, row=i: self._copy_row(row))
            grid.addWidget(name, i, 0)
            grid.addWidget(value, i, 1)
            grid.addWidget(copy_btn, i, 2)
            grid.setColumnStretch(1, 1)
            self._row_widgets.append((name, value, copy_btn))

        self.grid_widget = BitGrid(palette)
        self.grid_widget.bit_toggled.connect(self.toggle_bit)
        self.grid_widget.selection_changed.connect(self._update_slice_label)

        actions = QHBoxLayout()
        actions.setContentsMargins(12, 0, 12, 8)
        to_input = QPushButton("-> input")
        to_input.setProperty("class", "copyBtn")
        to_input.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        to_input.clicked.connect(self._emit_to_input)
        actions.addWidget(to_input)
        self.delta_label = QLabel("")
        self.delta_label.setProperty("class", "deltaNote")
        self.delta_label.setToolTip("set bits gained/lost vs. the previous value")
        actions.addWidget(self.delta_label)
        actions.addStretch(1)
        self.slice_label = QLabel("")
        self.slice_label.setProperty("class", "sliceNote")
        self.slice_label.setToolTip("drag across bit cells to read a field; Esc clears")
        actions.addWidget(self.slice_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addLayout(grid)
        layout.addWidget(self.grid_widget)
        layout.addLayout(actions)

    # -- state ---------------------------------------------------------------

    def show_value(
        self,
        value: int | None,
        word_size: int,
        signed: bool,
        float_views: FloatViews | None = None,
    ) -> None:
        # scratch is kept unmasked: cycling the word size must only change how
        # the value is *displayed*, never destroy its upper bits.
        # A range selection only survives a same-value re-render (settings
        # cycling aside, positions and the readout would go stale).
        if word_size != self.word_size or value is None or value != self.scratch:
            self.grid_widget.set_selection(None)
        self.word_size = word_size
        self.signed = signed
        self.float_mode = float_views if value is None else None
        was_active = self.active
        self.active = value is not None
        if value is not None:
            if not was_active:
                self.changed = 0  # first value after a grey spell: no diff to show
            elif value != self.scratch:
                self.changed = value ^ self.scratch
            self.scratch = value
        self._refresh()

    def toggle_bit(self, bit: int) -> None:
        self.grid_widget.set_selection(None)  # a bit edit invalidates the range readout
        self.scratch ^= 1 << bit
        self.changed = 1 << bit
        self._refresh()
        self._emit_to_input()  # the input line always reflects the edited value

    def clear_selection(self) -> bool:
        """Clear the drag-selected bit range; True if there was one (for Esc)."""
        had = self.grid_widget.selection is not None
        self.grid_widget.set_selection(None)
        return had

    @property
    def _masked_scratch(self) -> int:
        return self.scratch & ((1 << self.word_size) - 1)

    def _set_lanes(self, lanes: list[tuple[str, str]], dimmed: bool) -> None:
        """Rebuild `self.rows` from an ordered (key, value_text) list.

        Reuses the fixed pool of row widgets — extra rows beyond `len(lanes)`
        are hidden rather than destroyed.
        """
        self.rows = {}
        self._row_keys = [None] * LANE_ROWS
        for i, (name_label, value_label, copy_btn) in enumerate(self._row_widgets):
            if i >= len(lanes):
                name_label.hide()
                value_label.hide()
                copy_btn.hide()
                continue
            key, text = lanes[i]
            name_label.show()
            value_label.show()
            copy_btn.show()
            name_label.setText(key)
            value_label.setText(text)
            value_label.setToolTip(text)
            for w in (name_label, value_label):
                w.setProperty("dimmed", "true" if dimmed else "false")
                w.style().unpolish(w)
                w.style().polish(w)
            self._row_keys[i] = key
            self.rows[key] = (name_label, value_label)

    def _copy_row(self, row: int) -> None:
        key = self._row_keys[row]
        if key is not None:
            self.copy_base(key)

    def _refresh(self) -> None:
        if self.float_mode is not None:
            self._refresh_float(self.float_mode)
            return
        views = integer_views(self.scratch, self.word_size)
        dec_text = views.dec_unsigned
        if views.dec_signed != views.dec_unsigned:
            dec_text = f"{views.dec_unsigned}  ({views.dec_signed})"
        self._copy_texts = {
            "HEX": views.hex,
            "DEC": views.dec_unsigned,
            "BIN": views.binary,
            "ASC": views.ascii,
        }
        placeholder = "—"
        # Set bits rendered in the same phosphor/trace color as the bit grid's
        # asserted cells, so the two views read as one instrument, not two.
        # Displayed with space-separated nibble groups (copy keeps the
        # canonical "_" grouping) so QLabel can wrap the line at 64-bit
        # word sizes instead of overflowing the panel.
        bin_display = views.binary.replace("_", " ")
        bin_text = bin_display.replace(
            "1", f'<span style="color:{self.palette_tokens.bit_on}">1</span>'
        )
        lanes = [
            ("HEX", views.hex if self.active else placeholder),
            ("DEC", dec_text if self.active else placeholder),
            ("BIN", bin_text if self.active else placeholder),
        ]
        if any(ch != "." for ch in views.ascii):
            lanes.append(("ASC", views.ascii if self.active else placeholder))
        self._set_lanes(lanes, dimmed=not self.active)
        mask = (1 << self.word_size) - 1
        changed = self.changed & mask if self.active else 0
        if changed:
            gained = (self._masked_scratch & changed).bit_count()
            lost = (~self._masked_scratch & changed).bit_count()
            self.delta_label.setText(f"Δ +{gained} -{lost}")
        else:
            self.delta_label.setText("")
        self.grid_widget.set_state(self._masked_scratch, self.word_size, self.active, changed)
        self._update_slice_label()

    def _refresh_float(self, views: FloatViews) -> None:
        """Read-only IEEE-754 mode: bit pattern + decoded sign/exponent/mantissa.

        The scratch value is untouched — leaving float mode restores the
        integer view exactly as it was.
        """
        self._copy_texts = {
            "HEX": views.hex,
            "SGN": views.sign_text,
            "EXP": views.exponent_text,
            "MAN": views.mantissa_text,
        }
        lanes = [
            ("HEX", views.hex),
            ("SGN", views.sign_text),
            ("EXP", views.exponent_text),
            ("MAN", views.mantissa_text),
        ]
        self._set_lanes(lanes, dimmed=False)
        self.delta_label.setText("")
        self.grid_widget.set_state(
            views.bits,
            views.width,
            True,
            float_fields=(views.exp_width, views.man_width),
        )
        self._update_slice_label()

    def _selected_slice(self) -> tuple[int, int, int, int] | None:
        """(hi, lo, value, width) of the drag-selected field, if any."""
        if self.grid_widget.selection is None:
            return None
        hi, lo = self.grid_widget.selection
        width = hi - lo + 1
        value = (self._masked_scratch >> lo) & ((1 << width) - 1)
        return hi, lo, value, width

    def _update_slice_label(self) -> None:
        sliced = self._selected_slice()
        if sliced is None or not self.active:
            self.slice_label.setText("")
            return
        hi, lo, value, width = sliced
        hex_text = format_int_base(value, "hex", width)
        self.slice_label.setText(f"[{hi}:{lo}] = {hex_text} = {value} ({width} bits)")

    def set_palette(self, palette: Palette) -> None:
        self.palette_tokens = palette
        self.grid_widget.set_palette(palette)
        self._refresh()  # re-render the BIN highlight color

    # -- actions --------------------------------------------------------------

    def copy_base(self, base: str) -> None:
        if not self.active and self.float_mode is None:
            return
        self._clipboard(self._copy_texts[base])  # plain text, never the rich-text markup
        self.copied.emit(f"{base} copied")

    def _emit_to_input(self) -> None:
        if not self.active:
            return
        sliced = self._selected_slice()
        if sliced is not None:
            hi, lo, _, _ = sliced
            self.value_to_input.emit(f"0x{self._masked_scratch:X}[{hi}:{lo}]")
        else:
            self.value_to_input.emit(f"0x{self._masked_scratch:X}")
