"""GUI bootstrap: Fusion style, bundled font, OS-following light/dark theme."""

from __future__ import annotations

import sys

from calcutron.session import Session


def run_gui(session: Session) -> int:
    from PySide6.QtWidgets import QApplication

    from calcutron import __version__
    from calcutron.history.store import HistoryStore
    from calcutron.ui_qt import theme
    from calcutron.ui_qt.main_window import MainWindow

    app = QApplication(sys.argv[:1])
    app.setApplicationName("Calcutron-9000")
    app.setApplicationVersion(__version__)
    app.setStyle("Fusion")

    mono = theme.load_bundled_font()

    def apply_theme() -> None:
        palette = theme.current_palette(app)
        app.setStyleSheet(theme.stylesheet(palette, mono))
        window.apply_palette(palette)

    window = MainWindow(session, theme.current_palette(app), store=HistoryStore())
    app.styleHints().colorSchemeChanged.connect(lambda _scheme: apply_theme())
    apply_theme()
    window.resize(600, 800)
    window.show()
    return app.exec()
