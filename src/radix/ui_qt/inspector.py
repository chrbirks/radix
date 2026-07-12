"""The inspector: live visualization card stacked over the register view.

Always-visible read-only state, as distinct from the history/help/vars pane
stack the user is actively navigating.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QVBoxLayout, QWidget

from radix.ui_qt.bit_panel import IntegerView
from radix.ui_qt.theme import Palette
from radix.ui_qt.viz_panel import VizPanel


class Inspector(QWidget):
    def __init__(self, palette: Palette, clipboard_setter: Callable[[str], None]) -> None:
        super().__init__()
        self.setObjectName("inspector")
        self.vizpanel = VizPanel(palette)
        self.intview = IntegerView(palette, clipboard_setter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.vizpanel)
        layout.addWidget(self.intview)
        layout.addStretch(1)
