"""Integer view: hex/dec/bin rows with per-base copy, plus clickable bit rows.

The panel shows a *scratch* value seeded from the latest integer result.
Clicking a bit cell toggles that bit of the scratch value and re-renders all
bases; the "→ input" button places the scratch value into the input line as a
hex literal. A new result reseeds the scratch. Float results grey the panel.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent
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

CELL = 14
GAP = 2
NIBBLE_GAP = 6
BITS_PER_ROW = 32


class BitGrid(QWidget):
    """Clickable bit cells, MSB left, one or two rows of 32."""

    bit_toggled = Signal(int)  # bit index

    def __init__(self, palette: Palette) -> None:
        super().__init__()
        self.palette_tokens = palette
        self.word_size = 64
        self.value = 0
        self.enabled_look = True
        self.setMinimumHeight(2 * (CELL + GAP) + 8)

    def set_state(self, value: int, word_size: int, enabled: bool) -> None:
        self.value = value
        self.word_size = word_size
        self.enabled_look = enabled
        rows = (word_size + BITS_PER_ROW - 1) // BITS_PER_ROW
        self.setMinimumHeight(rows * (CELL + GAP) + 8)
        self.update()

    def set_palette(self, palette: Palette) -> None:
        self.palette_tokens = palette
        self.update()

    def _cell_rect(self, bit: int) -> QRectF:
        """Rect for a bit index (0 = LSB). MSB is top-left."""
        pos = self.word_size - 1 - bit  # 0 for MSB
        row, col = divmod(pos, BITS_PER_ROW)
        nibble_gaps = col // 4
        x = 4 + col * (CELL + GAP) + nibble_gaps * NIBBLE_GAP
        y = 4 + row * (CELL + GAP)
        return QRectF(x, y, CELL, CELL)

    def sizeHint(self) -> QSize:
        cols = min(self.word_size, BITS_PER_ROW)
        rows = (self.word_size + BITS_PER_ROW - 1) // BITS_PER_ROW
        width = 8 + cols * (CELL + GAP) + (cols // 4) * NIBBLE_GAP
        return QSize(width, rows * (CELL + GAP) + 8)

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
        layout.addWidget(self.grid_widget, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addLayout(actions)

    # -- state ---------------------------------------------------------------

    def show_value(self, value: int | None, word_size: int, signed: bool) -> None:
        self.word_size = word_size
        self.signed = signed
        self.active = value is not None
        if value is not None:
            self.scratch = value & ((1 << word_size) - 1)
        self._refresh()

    def toggle_bit(self, bit: int) -> None:
        self.scratch ^= 1 << bit
        self._refresh()

    def _refresh(self) -> None:
        views = integer_views(self.scratch, self.word_size)
        texts = {
            "HEX": views.hex,
            "DEC": views.dec_unsigned,
            "SGN": views.dec_signed,
            "BIN": views.binary,
        }
        for base, (name, value_label) in self.rows.items():
            value_label.setText(texts[base] if self.active else "—")
            for w in (name, value_label):
                w.setProperty("dimmed", "false" if self.active else "true")
                w.style().unpolish(w)
                w.style().polish(w)
        self.grid_widget.set_state(self.scratch, self.word_size, self.active)

    def set_palette(self, palette: Palette) -> None:
        self.palette_tokens = palette
        self.grid_widget.set_palette(palette)

    # -- actions --------------------------------------------------------------

    def copy_base(self, base: str) -> None:
        if not self.active:
            return
        text = self.rows[base][1].text()
        self._clipboard(text)
        self.copied.emit(f"{base} copied")

    def copy_hdl(self, flavor: str) -> None:
        if not self.active:
            return
        width = self.word_size
        hex_digits = f"{self.scratch:0{width // 4}X}"
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
            self.value_to_input.emit(f"0x{self.scratch:X}")
