"""pytest-qt smoke tests for the main window (offscreen-safe)."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402

from calcutron.session import Session  # noqa: E402
from calcutron.ui_qt.main_window import MainWindow  # noqa: E402
from calcutron.ui_qt.theme import LIGHT  # noqa: E402


@pytest.fixture
def window(qtbot):  # type: ignore[no-untyped-def]
    win = MainWindow(Session(), LIGHT)
    qtbot.addWidget(win)
    return win


def _submit(qtbot, window: MainWindow, text: str) -> None:  # type: ignore[no-untyped-def]
    window.input.setText(text)
    qtbot.keyClick(window.input, Qt.Key.Key_Return)


def test_evaluate_appends_history_and_updates_panel(qtbot, window: MainWindow) -> None:  # type: ignore[no-untyped-def]
    _submit(qtbot, window, "0xFF << 2")
    assert window.model.entries[-1].result == "1020"
    assert window.intview.active
    assert window.intview.rows["HEX"][1].text().endswith("03FC")


def test_float_result_greys_panel(qtbot, window: MainWindow) -> None:  # type: ignore[no-untyped-def]
    _submit(qtbot, window, "sin(1)")
    assert not window.intview.active


def test_assignment_and_recall(qtbot, window: MainWindow) -> None:  # type: ignore[no-untyped-def]
    _submit(qtbot, window, "x = 0xFF")
    assert window.model.entries[-1].result == "x ← 255"
    _submit(qtbot, window, "x << 2")
    assert window.model.entries[-1].result == "1020"
    qtbot.keyClick(window.input, Qt.Key.Key_Up)
    assert window.input.text() == "x << 2"
    qtbot.keyClick(window.input, Qt.Key.Key_Up)
    assert window.input.text() == "x = 0xFF"


def test_live_preview_shows_xor_and_result(qtbot, window: MainWindow) -> None:  # type: ignore[no-untyped-def]
    window.input.setText("2^10")
    window._update_preview()
    assert window.preview.text() == "2 XOR 10 = 8"


def test_preview_is_side_effect_free(qtbot, window: MainWindow) -> None:  # type: ignore[no-untyped-def]
    window.input.setText("y = 42")
    window._update_preview()
    assert "y" not in window.session.variables
    assert window.session.ans is None


def test_preview_error_has_caret(qtbot, window: MainWindow) -> None:  # type: ignore[no-untyped-def]
    window.input.setText("1 + )")
    window._update_preview()
    assert window.preview.property("state") == "error"
    assert "^" in window.preview.text()


def test_help_command_shows_pane(qtbot, window: MainWindow) -> None:  # type: ignore[no-untyped-def]
    _submit(qtbot, window, "help")
    assert window.help_pane.isVisibleTo(window)
    assert "Operators" in window.help_pane.toPlainText()
    qtbot.keyClick(window.input, Qt.Key.Key_Escape)
    assert not window.help_pane.isVisibleTo(window)


def test_bit_toggle_updates_scratch(qtbot, window: MainWindow) -> None:  # type: ignore[no-untyped-def]
    _submit(qtbot, window, "8")
    window.intview.toggle_bit(0)
    assert window.intview.scratch == 9
    assert window.intview.rows["DEC"][1].text() == "9"


def test_copy_result_shortcut(qtbot, window: MainWindow) -> None:  # type: ignore[no-untyped-def]
    from PySide6.QtWidgets import QApplication

    _submit(qtbot, window, "6*7")
    window._copy_result()
    assert QApplication.clipboard().text() == "42"


def test_status_bar_cycles_word_size(qtbot, window: MainWindow) -> None:  # type: ignore[no-untyped-def]
    assert window.status_items["word"].text() == "64-bit"
    window._cycle_word_size()
    assert window.session.word_size == 8
    assert window.status_items["word"].text() == "8-bit"
