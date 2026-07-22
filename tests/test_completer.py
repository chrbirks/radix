"""Completer popup and completion generation tests."""

from __future__ import annotations

from radix.session import Session
from radix.ui_qt.completer import completions
from radix.ui_qt.highlight import color_for
from radix.ui_qt.theme import DARK, LIGHT


def test_layout_completion_appears() -> None:
    session = Session()
    session.evaluate("layout CTRL = EN[31] IRQ[30:28]", commit=True)
    items = completions(session)
    ctrl_completion = next((c for c in items if c.name == "CTRL"), None)
    assert ctrl_completion is not None
    assert ctrl_completion.kind == "layout"
    assert ctrl_completion.insert == "CTRL("
    assert "EN[31]" in ctrl_completion.summary


def test_fields_function_completion() -> None:
    items = completions(Session())
    fields_completion = next((c for c in items if c.name == "fields"), None)
    assert fields_completion is not None
    assert fields_completion.kind == "function"


def test_color_for_layout_light_palette() -> None:
    color = color_for("layout", LIGHT)
    assert color is not None


def test_color_for_layout_dark_palette() -> None:
    color = color_for("layout", DARK)
    assert color is not None
