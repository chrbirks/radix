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
    # Wayland compositors (GNOME Shell in particular) resolve a running
    # window's icon by matching this desktop-file id against an installed
    # radix.desktop's Icon= key — they ignore the QIcon above entirely.
    # See packaging/radix.desktop.
    app.setDesktopFileName("radix")

    mono, label = theme.load_bundled_font()

    def apply_theme() -> None:
        palette = theme.resolve_palette(app, window.theme_mode)
        app.setStyleSheet(theme.stylesheet(palette, mono, label))
        window.apply_palette(palette)

    window = MainWindow(session, theme.current_palette(app), store=HistoryStore())
    window.on_theme_mode_changed = apply_theme
    app.styleHints().colorSchemeChanged.connect(
        lambda _scheme: apply_theme() if window.theme_mode == "auto" else None
    )
    apply_theme()  # re-resolves once more now that a persisted theme_mode is loaded
    window.show()
    return app.exec()
