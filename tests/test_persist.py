"""Round-trip tests for persisting variables/layouts/ans across restarts."""

from __future__ import annotations

import json

import mpmath

from radix.engine.layouts import RegField, RegLayout, layout_from_json, layout_to_json
from radix.engine.values import Value, value_from_json, value_to_json
from radix.session import Session


def test_value_to_json_roundtrips_int() -> None:
    v = Value(42, declared_width=8, prefer_si=True, note="a note")
    restored = value_from_json(json.loads(json.dumps(value_to_json(v))))
    assert restored.number == 42
    assert isinstance(restored.number, int)
    assert restored.declared_width == 8
    assert restored.prefer_si is True
    assert restored.note == "a note"
    assert restored.layout is None
    assert restored.viz is None


def test_value_to_json_roundtrips_real_exactly() -> None:
    x = mpmath.mpf(1) / mpmath.mpf(3)
    v = Value(x)
    restored = value_from_json(json.loads(json.dumps(value_to_json(v))))
    assert not isinstance(restored.number, int)
    assert restored.number == x
    assert restored.number._mpf_ == x._mpf_


def test_value_to_json_roundtrips_special_reals() -> None:
    for x in (mpmath.mpf(0), mpmath.mpf("-2.5"), mpmath.inf, -mpmath.inf, mpmath.mpf("1e400")):
        restored = value_from_json(json.loads(json.dumps(value_to_json(Value(x)))))
        assert restored.number == x


def test_value_to_json_roundtrips_nested_layout() -> None:
    layout = RegLayout("CTRL", (RegField("EN", 31, 31), RegField("ADDR", 27, 8)))
    v = Value(0x8C01A0F3, layout=layout)
    restored = value_from_json(json.loads(json.dumps(value_to_json(v))))
    assert restored.layout is not None
    assert restored.layout.name == "CTRL"
    assert restored.layout.fields == layout.fields


def test_layout_to_json_roundtrip() -> None:
    layout = RegLayout("CTRL", (RegField("EN", 31, 31), RegField("IRQ", 30, 28)))
    restored = layout_from_json(json.loads(json.dumps(layout_to_json(layout))))
    assert restored == layout


def test_layout_to_json_roundtrip_anonymous() -> None:
    layout = RegLayout(None, (RegField("CMD", 7, 0),))
    restored = layout_from_json(json.loads(json.dumps(layout_to_json(layout))))
    assert restored == layout


def test_session_state_roundtrip() -> None:
    session = Session()
    session.evaluate("layout CTRL = EN[31] ADDR[27:8]")
    session.evaluate("x = CTRL(0x8C01A0F3)")
    session.evaluate("y = 1/3")

    blob = json.loads(json.dumps(session.state_to_json()))

    restored = Session()
    restored.load_state_json(blob)
    assert set(restored.variables) == {"x", "y"}
    assert restored.variables["x"].number == 0x8C01A0F3
    assert restored.variables["x"].layout is not None
    assert restored.variables["x"].layout.name == "CTRL"
    assert restored.variables["y"].number == session.variables["y"].number
    assert set(restored.layouts) == {"CTRL"}
    assert restored.ans is not None
    assert session.ans is not None
    assert restored.ans.number == session.ans.number


def test_session_state_roundtrip_without_ans() -> None:
    session = Session()
    assert session.ans is None
    restored = Session()
    restored.load_state_json(session.state_to_json())
    assert restored.ans is None
    assert restored.variables == {}
    assert restored.layouts == {}


def test_load_state_json_skips_corrupt_variable_entries() -> None:
    session = Session()
    session.evaluate("x = 5")
    session.evaluate("y = 6")
    blob = session.state_to_json()
    blob["variables"]["x"] = {"not": "a valid value"}

    restored = Session()
    restored.load_state_json(blob)
    assert set(restored.variables) == {"y"}
    assert restored.variables["y"].number == 6


def test_load_state_json_skips_corrupt_layout_entries() -> None:
    session = Session()
    session.evaluate("layout CTRL = EN[31]")
    session.evaluate("layout STATUS = IRQ[3:0]")
    blob = session.state_to_json()
    blob["layouts"]["CTRL"] = {"garbage": True}

    restored = Session()
    restored.load_state_json(blob)
    assert set(restored.layouts) == {"STATUS"}


def test_load_state_json_skips_reserved_names() -> None:
    session = Session()
    blob = session.state_to_json()
    blob["variables"] = {"pi": value_to_json(Value(3))}

    restored = Session()
    restored.load_state_json(blob)
    assert "pi" not in restored.variables
