"""Design tokens and the application stylesheet.

One palette definition per scheme; the QSS is a template over the tokens so
light and dark can never drift structurally. The app follows the OS color
scheme via QStyleHints.colorScheme and re-applies on change.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication


@dataclass(frozen=True)
class Palette:
    background: str
    surface: str  # input field, panels
    text: str
    muted: str  # preview line, separators text, status bar
    hairline: str  # 1px separators
    accent: str
    accent_text: str  # text on accent
    error: str
    bit_on: str
    bit_off: str
    bit_changed: str  # outline on bits that flipped vs. the previous value
    float_sign: str  # IEEE-754 field bands in the bit grid
    float_exp: str
    float_man: str
    syn_number: str
    syn_function: str
    syn_operator: str


LIGHT = Palette(
    background="#fafafa",
    surface="#ffffff",
    text="#1a1d21",
    muted="#7a828c",
    hairline="#e3e6ea",
    accent="#2563eb",
    accent_text="#ffffff",
    error="#c92a2a",
    bit_on="#2563eb",
    bit_off="#d5dae1",
    bit_changed="#d97706",
    float_sign="#e03131",
    float_exp="#2b8a3e",
    float_man="#2563eb",
    syn_number="#0550ae",
    syn_function="#6f42c1",
    syn_operator="#b35900",
)

DARK = Palette(
    background="#16181c",
    surface="#1e2126",
    text="#e8eaed",
    muted="#8b939e",
    hairline="#2b2f36",
    accent="#5b8def",
    accent_text="#101216",
    error="#ff6b6b",
    bit_on="#5b8def",
    bit_off="#3a4048",
    bit_changed="#e8a33d",
    float_sign="#f06d6d",
    float_exp="#4fc08d",
    float_man="#5b8def",
    syn_number="#79c0ff",
    syn_function="#d2a8ff",
    syn_operator="#e0af68",
)

MONO_FAMILY = "JetBrains Mono"


def load_bundled_font() -> str:
    """Register the bundled monospace font; fall back to the system fixed font."""
    loaded = False
    for name in ("JetBrainsMono-Regular.ttf", "JetBrainsMono-Bold.ttf"):
        ref = resources.files("calcutron.ui_qt") / "fonts" / name
        with resources.as_file(ref) as path:
            if QFontDatabase.addApplicationFont(str(path)) >= 0:
                loaded = True
    if loaded:
        return MONO_FAMILY
    return QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()


def stylesheet(p: Palette, mono: str) -> str:
    return f"""
    * {{
        font-family: "{mono}";
        font-size: 18px;
    }}
    QMainWindow, QWidget#root {{
        background: {p.background};
    }}
    QListView#history {{
        background: {p.background};
        border: none;
        border-bottom: 1px solid {p.hairline};
        padding: 6px;
    }}
    QPlainTextEdit#input {{
        background: {p.surface};
        color: {p.text};
        border: none;
        border-bottom: 1px solid {p.hairline};
        padding: 10px 12px;
        font-size: 21px;
        selection-background-color: {p.accent};
        selection-color: {p.accent_text};
    }}
    QLabel#preview {{
        color: {p.muted};
        padding: 2px 12px 8px 12px;
        font-size: 17px;
    }}
    QListWidget#completerPopup {{
        background: {p.surface};
        color: {p.text};
        border: 1px solid {p.hairline};
        border-radius: 4px;
        padding: 2px;
        font-size: 17px;
        outline: none;
    }}
    QLabel#preview[state="error"] {{
        color: {p.error};
    }}
    QWidget#intview {{
        background: {p.background};
        border-top: 1px solid {p.hairline};
    }}
    QLabel.baseName {{
        color: {p.muted};
        font-size: 16px;
    }}
    QLabel.baseValue {{
        color: {p.text};
        font-size: 18px;
    }}
    QLabel.baseValue[dimmed="true"], QLabel.baseName[dimmed="true"] {{
        color: {p.muted};
    }}
    QPushButton.copyBtn {{
        background: transparent;
        color: {p.muted};
        border: 1px solid {p.hairline};
        border-radius: 3px;
        padding: 1px 6px;
        font-size: 15px;
    }}
    QPushButton.copyBtn:hover {{
        color: {p.accent};
        border-color: {p.accent};
    }}
    QLabel.deltaNote {{
        color: {p.muted};
        font-size: 15px;
        padding: 1px 6px;
    }}
    QLabel.sliceNote {{
        color: {p.accent};
        font-size: 15px;
        padding: 1px 6px;
    }}
    QStatusBar {{
        background: {p.background};
        color: {p.muted};
        border-top: 1px solid {p.hairline};
        font-size: 16px;
    }}
    QStatusBar::item {{ border: none; }}
    QLabel.statusItem {{
        color: {p.muted};
        padding: 2px 8px;
    }}
    QLabel.statusItem:hover {{
        color: {p.accent};
    }}
    QTextEdit#helpPane {{
        background: {p.surface};
        color: {p.text};
        border: none;
        padding: 12px;
        font-size: 17px;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
    }}
    QScrollBar::handle:vertical {{
        background: {p.hairline};
        border-radius: 4px;
        min-height: 24px;
    }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
    """


def current_palette(app: QApplication) -> Palette:
    from PySide6.QtCore import Qt

    scheme = app.styleHints().colorScheme()
    return DARK if scheme == Qt.ColorScheme.Dark else LIGHT
