"""Completer popup and completion generation tests."""

from __future__ import annotations

from radix.session import Session
from radix.ui_qt.completer import completions
from radix.ui_qt.highlight import color_for
from radix.ui_qt.theme import DARK, LIGHT


def test_csr_completion_appears() -> None:
    session = Session()
    session.evaluate("csr CTRL = EN[31] IRQ[30:28]", commit=True)
    items = completions(session)
    ctrl_completion = next((c for c in items if c.name == "CTRL"), None)
    assert ctrl_completion is not None
    assert ctrl_completion.kind == "csr"
    assert ctrl_completion.insert == "CTRL("
    assert "EN[31]" in ctrl_completion.summary


def test_csr_function_completion() -> None:
    items = completions(Session())
    csr_completion = next((c for c in items if c.name == "csr"), None)
    assert csr_completion is not None
    assert csr_completion.kind == "function"


def test_color_for_csr_light_palette() -> None:
    color = color_for("csr", LIGHT)
    assert color is not None


def test_color_for_csr_dark_palette() -> None:
    color = color_for("csr", DARK)
    assert color is not None
