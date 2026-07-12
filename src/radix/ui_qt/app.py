"""GUI bootstrap: Fusion style, bundled font, OS-following light/dark theme."""

from __future__ import annotations

import sys

from radix.session import Session


def run_gui(session: Session) -> int:
    from PySide6.QtWidgets import QApplication

    from radix import __version__
    from radix.history.store import HistoryStore
    from radix.ui_qt import theme
    from radix.ui_qt.main_window import MainWindow

    app = QApplication(sys.argv[:1])
    app.setApplicationName("Radix")
    app.setApplicationVersion(__version__)
    app.setStyle("Fusion")
    app.setWindowIcon(theme.load_app_icon())

    mono = theme.load_bundled_font()

    def apply_theme() -> None:
        palette = theme.current_palette(app)
        app.setStyleSheet(theme.stylesheet(palette, mono))
        window.apply_palette(palette)

    window = MainWindow(session, theme.current_palette(app), store=HistoryStore())
    app.styleHints().colorSchemeChanged.connect(lambda _scheme: apply_theme())
    apply_theme()
    window.show()
    return app.exec()
