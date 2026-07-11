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


def test_bit_toggle_writes_input(qtbot, window: MainWindow) -> None:  # type: ignore[no-untyped-def]
    _submit(qtbot, window, "8")
    window.intview.toggle_bit(0)
    assert window.input.text() == "0x9"
    window.intview.toggle_bit(4)
    assert window.input.text() == "0x19"
    window._update_preview()  # the input round-trip must not disturb the scratch
    assert window.intview.scratch == 0x19


def test_bin_row_highlights_set_bits_but_copies_plain(qtbot, window: MainWindow) -> None:  # type: ignore[no-untyped-def]
    from PySide6.QtWidgets import QApplication

    _submit(qtbot, window, "0b1010")
    label_text = window.intview.rows["BIN"][1].text()
    assert '<span style="color:' in label_text  # 1s are colored
    window.intview.copy_base("BIN")
    copied = QApplication.clipboard().text()
    assert "<" not in copied and copied.endswith("1010")


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


def test_word_size_cycling_is_display_only(qtbot, window: MainWindow) -> None:  # type: ignore[no-untyped-def]
    _submit(qtbot, window, "0xFFFF")
    window._cycle_word_size()  # 64 -> 8: shows 0xFF
    assert window.intview.rows["HEX"][1].text() == "0xFF"
    window._cycle_word_size()  # 8 -> 16: upper bits must reappear
    assert window.intview.rows["HEX"][1].text() == "0xFFFF"


def test_result_base_applies_to_history_and_preview(qtbot, window: MainWindow) -> None:  # type: ignore[no-untyped-def]
    _submit(qtbot, window, "1020")
    _submit(qtbot, window, "q = 255")
    _submit(qtbot, window, "sin(1)")
    float_text = window.model.entries[-1].result

    window._cycle_int_base()  # dec -> hex
    assert window.status_items["base"].text() == "HEX"
    assert window.model.entries[-3].result == "0x3FC"
    assert window.model.entries[-2].result == "q ← 0xFF"
    assert window.model.entries[-1].result == float_text  # floats untouched

    window.input.setText("128 + 2")
    window._update_preview()
    assert window.preview.text().endswith("= 0x82")

    window._cycle_int_base()  # hex -> bin
    assert window.model.entries[-3].result == "0b11_1111_1100"
    window._cycle_int_base()  # bin -> dec restores the recorded text
    assert window.status_items["base"].text() == "DEC"
    assert window.model.entries[-3].result == "1020"
    assert window.model.entries[-2].result == "q ← 255"


def test_panel_follows_input_live(qtbot, window: MainWindow) -> None:  # type: ignore[no-untyped-def]
    window.input.setText("0xAB << 4")
    window._update_preview()
    assert window.intview.active
    assert window.intview.rows["HEX"][1].text().endswith("0AB0")  # before Enter

    window.input.setText("sin(1)")
    window._update_preview()
    assert not window.intview.active  # float greys the panel

    window.input.setText("0xAB <<")  # incomplete: panel holds its last state
    window._update_preview()
    assert not window.intview.active

    _submit(qtbot, window, "0xFF")
    window.input.setText("")
    window._update_preview()
    assert window.intview.rows["HEX"][1].text().endswith("00FF")  # falls back to ans


def test_bit_grid_wraps_to_window_width(qtbot, window: MainWindow) -> None:  # type: ignore[no-untyped-def]
    from calcutron.ui_qt.bit_panel import BYTE_WIDTH

    grid = window.intview.grid_widget
    narrow = BYTE_WIDTH + 12  # fits exactly one byte group per row
    grid.resize(narrow, 100)
    grid.set_state(0, 32, True)
    assert grid._bits_per_row() == 8
    assert grid._rows() == 4
    # Every bit must land inside the widget's width.
    assert all(grid._cell_rect(b).right() <= narrow for b in range(32))
    wide = 4 * BYTE_WIDTH + 12  # fits all four byte groups on one row
    grid.resize(wide, 100)
    assert grid._bits_per_row() == 32
    assert grid._rows() == 1
    assert all(grid._cell_rect(b).right() <= wide for b in range(32))
