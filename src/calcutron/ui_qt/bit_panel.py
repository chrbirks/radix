"""Integer view: hex/dec/bin rows with per-base copy, plus clickable bit rows.

The panel shows a *scratch* value seeded from the latest integer result.
Clicking a bit cell toggles that bit of the scratch value and re-renders all
bases; the "→ input" button places the scratch value into the input line as a
hex literal. A new result reseeds the scratch. Float results grey the panel.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent, QResizeEvent
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from calcutron.engine.formatter import integer_views
from calcutron.ui_qt.theme import Palette

CELL = 24
GAP = 4
NIBBLE_GAP = 10
INDEX_H = 18  # strip below each cell row for bit-index labels
ROW_H = CELL + GAP + INDEX_H
BYTE_WIDTH = 8 * (CELL + GAP) + 2 * NIBBLE_GAP  # one byte group incl. nibble gaps


class BitGrid(QWidget):
    """Clickable bit cells, MSB top-left.

    The grid fills the available width and wraps at byte boundaries, so every
    bit stays visible at any window width and word size (no clipping from
    stale size hints).
    """

    bit_toggled = Signal(int)  # bit index

    def __init__(self, palette: Palette) -> None:
        super().__init__()
        self.palette_tokens = palette
        self.word_size = 64
        self.value = 0
        self.enabled_look = True
        self._apply_height()

    def set_state(self, value: int, word_size: int, enabled: bool) -> None:
        self.value = value
        self.word_size = word_size
        self.enabled_look = enabled
        self._apply_height()
        self.update()

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

    def _apply_height(self) -> None:
        self.setMinimumHeight(self._rows() * ROW_H + 8)

    def resizeEvent(self, event: QResizeEvent) -> None:
        self._apply_height()
        super().resizeEvent(event)

    def _cell_rect(self, bit: int) -> QRectF:
        """Rect for a bit index (0 = LSB). MSB is top-left."""
        per_row = self._bits_per_row()
        pos = self.word_size - 1 - bit  # 0 for MSB
        row, col = divmod(pos, per_row)
        nibble_gaps = col // 4
        x = 4 + col * (CELL + GAP) + nibble_gaps * NIBBLE_GAP
        y = 4 + row * ROW_H
        return QRectF(x, y, CELL, CELL)

    def sizeHint(self) -> QSize:
        return QSize(2 * BYTE_WIDTH, self._rows() * ROW_H + 8)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        p = self.palette_tokens
        on = QColor(p.bit_on if self.enabled_look else p.bit_off)
        off = QColor(p.bit_off)
        off.setAlphaF(0.6 if not self.enabled_look else 1.0)
        for bit in range(self.word_size):
            rect = self._cell_rect(bit)
            set_ = (self.value >> bit) & 1
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(on if set_ else off)
            painter.drawRoundedRect(rect, 2, 2)
        # Bit-index labels under each nibble's MSB cell (63, 59, … 3), plus bit 0.
        label_font = painter.font()
        label_font.setPixelSize(14)
        painter.setFont(label_font)
        painter.setPen(QColor(self.palette_tokens.muted))
        for bit in range(self.word_size):
            if bit % 4 == 3 or bit == 0:
                cell = self._cell_rect(bit)
                label_rect = QRectF(cell.left() - GAP, cell.bottom() + 1, CELL + 2 * GAP, INDEX_H)
                painter.drawText(label_rect, Qt.AlignmentFlag.AlignHCenter, str(bit))
        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if not self.enabled_look:
            return
        pos = event.position()
        for bit in range(self.word_size):
            if self._cell_rect(bit).contains(pos):
                self.bit_toggled.emit(bit)
                return


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
        self.word_size = 64
        self.signed = False
        self.active = False

        self.rows: dict[str, tuple[QLabel, QLabel]] = {}
        self._copy_texts: dict[str, str] = {}
        grid = QGridLayout()
        grid.setContentsMargins(12, 8, 12, 4)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(2)
        for i, base in enumerate(("HEX", "DEC", "SGN", "BIN")):
            name = QLabel(base)
            name.setProperty("class", "baseName")
            value = QLabel("—")
            value.setProperty("class", "baseValue")
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            copy_btn = QPushButton("copy")
            copy_btn.setProperty("class", "copyBtn")
            copy_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            copy_btn.clicked.connect(lambda _=False, b=base: self.copy_base(b))
            grid.addWidget(name, i, 0)
            grid.addWidget(value, i, 1)
            grid.addWidget(copy_btn, i, 2)
            grid.setColumnStretch(1, 1)
            self.rows[base] = (name, value)

        self.grid_widget = BitGrid(palette)
        self.grid_widget.bit_toggled.connect(self.toggle_bit)

        actions = QHBoxLayout()
        actions.setContentsMargins(12, 0, 12, 8)
        for label, fn in (
            ("→ input", self._emit_to_input),
            ("copy Verilog", lambda: self.copy_hdl("verilog")),
            ("copy VHDL", lambda: self.copy_hdl("vhdl")),
            ("copy C", lambda: self.copy_hdl("c")),
        ):
            btn = QPushButton(label)
            btn.setProperty("class", "copyBtn")
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.clicked.connect(fn)
            actions.addWidget(btn)
        actions.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addLayout(grid)
        layout.addWidget(self.grid_widget)
        layout.addLayout(actions)

    # -- state ---------------------------------------------------------------

    def show_value(self, value: int | None, word_size: int, signed: bool) -> None:
        # scratch is kept unmasked: cycling the word size must only change how
        # the value is *displayed*, never destroy its upper bits.
        self.word_size = word_size
        self.signed = signed
        self.active = value is not None
        if value is not None:
            self.scratch = value
        self._refresh()

    def toggle_bit(self, bit: int) -> None:
        self.scratch ^= 1 << bit
        self._refresh()

    @property
    def _masked_scratch(self) -> int:
        return self.scratch & ((1 << self.word_size) - 1)

    def _refresh(self) -> None:
        views = integer_views(self.scratch, self.word_size)
        texts = {
            "HEX": views.hex,
            "DEC": views.dec_unsigned,
            "SGN": views.dec_signed,
            "BIN": views.binary,
        }
        self._copy_texts = texts
        for base, (name, value_label) in self.rows.items():
            if not self.active:
                value_label.setText("—")
            elif base == "BIN":
                # Set bits in the bit-grid blue so 1s stand out from 0s.
                highlighted = texts[base].replace(
                    "1", f'<span style="color:{self.palette_tokens.bit_on}">1</span>'
                )
                value_label.setText(highlighted)
            else:
                value_label.setText(texts[base])
            value_label.setToolTip(texts[base] if self.active else "")  # full text when clipped
            for w in (name, value_label):
                w.setProperty("dimmed", "false" if self.active else "true")
                w.style().unpolish(w)
                w.style().polish(w)
        self.grid_widget.set_state(self._masked_scratch, self.word_size, self.active)

    def set_palette(self, palette: Palette) -> None:
        self.palette_tokens = palette
        self.grid_widget.set_palette(palette)
        self._refresh()  # re-render the BIN highlight color

    # -- actions --------------------------------------------------------------

    def copy_base(self, base: str) -> None:
        if not self.active:
            return
        self._clipboard(self._copy_texts[base])  # plain text, never the rich-text markup
        self.copied.emit(f"{base} copied")

    def copy_hdl(self, flavor: str) -> None:
        if not self.active:
            return
        width = self.word_size
        hex_digits = f"{self._masked_scratch:0{width // 4}X}"
        if flavor == "verilog":
            text = f"{width}'h{hex_digits}"
        elif flavor == "vhdl":
            text = f'x"{hex_digits}"'
        else:
            text = f"0x{hex_digits}"
        self._clipboard(text)
        self.copied.emit(f"{flavor} literal copied: {text}")

    def _emit_to_input(self) -> None:
        if self.active:
            self.value_to_input.emit(f"0x{self._masked_scratch:X}")
