"""Register field layouts: spec parsing, decoding, dot access, and rendering.

Drives the engine directly (parser/evaluator/render), since this task does not
touch session.py — a later task wires layouts through Session.
"""

from __future__ import annotations

import pytest

from radix.engine import evaluator, render
from radix.engine.errors import EvalError, IncompleteError, ParseError
from radix.engine.functions import EvalContext
from radix.engine.layouts import flatten_spec, layout_from_nodes
from radix.engine.parser import parse
from radix.engine.values import Value


def _ctx(word_size: int = 32, signed: bool = False, angle_deg: bool = False) -> EvalContext:
    return EvalContext(word_size=word_size, signed=signed, angle_deg=angle_deg)


def _ev(
    text: str,
    ctx: EvalContext | None = None,
    variables: dict[str, Value] | None = None,
    ans: Value | None = None,
    layouts: dict[str, object] | None = None,
) -> Value:
    node = parse(text)
    return evaluator.evaluate(node, ctx or _ctx(), variables or {}, ans, layouts=layouts)


# -- fields(...) macro: decoding -------------------------------------------------


def test_fields_macro_decodes_and_builds_note() -> None:
    v = _ev("fields(0x8C01A0F3, EN[31] IRQ[30:28] ADDR[27:8] CMD[7:0])")
    assert v.number == 0x8C01A0F3
    assert v.note == "EN=1 IRQ=0b000 ADDR=0xC01A0 CMD=0xF3"
    assert v.layout is not None
    assert v.layout.name is None
    assert [f.name for f in v.layout.fields] == ["EN", "IRQ", "ADDR", "CMD"]


def test_comma_and_space_separators_produce_identical_layouts() -> None:
    space = _ev("fields(0xF3, HI[7:4] LO[3:0])")
    comma = _ev("fields(0xF3, HI[7:4], LO[3:0])")
    assert space.note == comma.note == "HI=0b1111 LO=0b0011"
    assert space.layout is not None and comma.layout is not None
    assert [f.name for f in space.layout.fields] == [f.name for f in comma.layout.fields]


def test_negative_value_is_masked_before_extraction() -> None:
    v = _ev("fields(-1, A[3:0])", ctx=_ctx(word_size=32))
    assert v.note == "A=0b1111"
    assert v.number == -1  # unmasked original number is preserved


def test_word_size_violation_names_the_offending_field() -> None:
    with pytest.raises(EvalError) as exc:
        _ev("fields(0, A[8])", ctx=_ctx(word_size=8))
    assert str(exc.value) == "field A[8] is outside the 8-bit word"


# -- fields(...) macro: errors ----------------------------------------------------


def test_non_literal_lsb_errors_with_span_on_offending_node() -> None:
    text = "fields(1, A[x])"
    with pytest.raises(EvalError) as exc:
        _ev(text)
    assert "field ranges must be literal integers" in str(exc.value)
    start = text.index("x")
    assert exc.value.span.start == start
    assert exc.value.span.end == start + 1


def test_non_literal_lsb_expression_errors() -> None:
    text = "fields(1, A[1+2])"
    with pytest.raises(EvalError) as exc:
        _ev(text)
    assert "field ranges must be literal integers" in str(exc.value)
    start = text.index("1+2")
    assert exc.value.span.start == start
    assert exc.value.span.end == start + len("1+2")


def test_msb_less_than_lsb_errors() -> None:
    text = "fields(1, A[3:5])"
    with pytest.raises(EvalError) as exc:
        _ev(text)
    assert str(exc.value) == "invalid field range [3:5] — msb must be >= lsb"
    start = text.index("A[3:5]")
    assert exc.value.span.start == start
    assert exc.value.span.end == start + len("A[3:5]")


def test_duplicate_field_name_errors_on_second_occurrence() -> None:
    text = "fields(1, A[3:0] A[7:4])"
    with pytest.raises(EvalError) as exc:
        _ev(text)
    assert str(exc.value) == "duplicate field name 'A'"
    second_a = text.rindex("A")
    assert exc.value.span.start == second_a
    assert exc.value.span.end == second_a + 1


def test_overlapping_ranges_error_names_both_fields() -> None:
    text = "fields(1, ADDR[27:8] CMD[9:0])"
    with pytest.raises(EvalError) as exc:
        _ev(text)
    assert str(exc.value) == "field CMD[9:0] overlaps ADDR[27:8]"
    start = text.index("CMD[9:0]")
    assert exc.value.span.start == start
    assert exc.value.span.end == start + len("CMD[9:0]")


def test_non_slice_leaf_errors() -> None:
    text = "fields(1, 2)"
    with pytest.raises(EvalError) as exc:
        _ev(text)
    assert "field ranges must be literal integers" in str(exc.value)
    start = text.index("2")
    assert exc.value.span.start == start
    assert exc.value.span.end == start + 1


def test_fields_arity_below_two_errors() -> None:
    text = "fields(1)"
    with pytest.raises(EvalError) as exc:
        _ev(text)
    assert "fields takes a value and at least one field" in str(exc.value)
    assert exc.value.span.start == 0
    assert exc.value.span.end == len(text)


def test_float_decode_target_errors() -> None:
    text = "fields(1.5, A[3:0])"
    with pytest.raises(EvalError) as exc:
        _ev(text)
    assert "field decode requires an integer operand" in str(exc.value)
    start = text.index("1.5")
    assert exc.value.span.start == start
    assert exc.value.span.end == start + len("1.5")


# -- layout-name calls (hand-built layouts dict, no session.py involved) --------


def test_layout_name_call_decodes_with_layout_attached() -> None:
    spec = parse("EN[31] IRQ[30:28] ADDR[27:8] CMD[7:0]")
    layout = layout_from_nodes(flatten_spec(spec), name="CTRL")
    v = _ev("CTRL(0x8C01A0F3)", layouts={"CTRL": layout})
    assert v.number == 0x8C01A0F3
    assert v.layout is not None and v.layout.name == "CTRL"
    assert v.note == "EN=1 IRQ=0b000 ADDR=0xC01A0 CMD=0xF3"


def test_layout_name_call_arity_error() -> None:
    spec = parse("EN[31]")
    layout = layout_from_nodes(flatten_spec(spec), name="CTRL")
    with pytest.raises(EvalError) as exc:
        _ev("CTRL(1, 2)", layouts={"CTRL": layout})
    assert str(exc.value) == "CTRL takes 1 argument(s), got 2"


def test_fields_macro_dispatches_before_functions_stub() -> None:
    # "fields" is registered in FUNCTIONS purely for help/autocomplete; calling it
    # must never reach that stub's AssertionError.
    v = _ev("fields(1, A[0])")
    assert v.note == "A=1"


# -- dot access ---------------------------------------------------------------


def test_dot_access_extracts_plain_int_with_declared_width() -> None:
    v = _ev("fields(0xF3, HI[7:4] LO[3:0]).HI")
    assert v.number == 15
    assert v.declared_width == 4
    assert v.layout is None  # extracting a field yields a plain int, not another layout


def test_dot_access_chains_with_shift() -> None:
    v = _ev("fields(0xF3, HI[7:4] LO[3:0]).HI << 2")
    assert v.number == 60


def test_dot_access_result_can_be_sliced() -> None:
    v = _ev("fields(0xF3, HI[7:4] LO[3:0]).HI[1:0]")
    assert v.number == 0b11


def test_dot_access_on_layout_less_value_errors() -> None:
    text = "ans.ADDR"
    with pytest.raises(EvalError) as exc:
        _ev(text, ans=Value(5))
    assert "no field layout on this value" in str(exc.value)
    assert exc.value.span.start == text.index("ans")
    assert exc.value.span.end == text.index("ans") + len("ans")


def test_unknown_field_name_lists_actual_fields() -> None:
    text = "fields(0xF3, HI[7:4] LO[3:0]).FOO"
    with pytest.raises(EvalError) as exc:
        _ev(text)
    assert str(exc.value) == "no field 'FOO' — this layout has HI, LO"
    start = text.rindex("FOO")
    assert exc.value.span.start == start
    assert exc.value.span.end == start + len("FOO")


def test_dot_at_end_of_input_is_incomplete_not_parse_error() -> None:
    with pytest.raises(IncompleteError):
        parse("ans.")
    # And confirm it is NOT a plain (non-incomplete) ParseError:
    try:
        parse("ans.")
    except IncompleteError:
        pass
    except ParseError:
        pytest.fail("expected IncompleteError, got a hard ParseError")


def test_dot_before_digit_is_still_a_decimal_literal_golden_case() -> None:
    """Documented lexer quirk, not a bug: ans.5 lexes as ans * 0.5."""
    ctx = _ctx()
    ans_val = Value(10)
    dotted = _ev("ans.5", ctx=ctx, ans=ans_val)
    explicit = _ev("ans * 0.5", ctx=ctx, ans=ans_val)
    assert dotted.number == explicit.number == 5


# -- render: spec-preserving fields(...) and dot access --------------------------


def test_render_fields_space_form_has_no_multiplication_sign() -> None:
    node = parse("fields(165, EN[31] IRQ[30:28])")
    text = render.render(node, {}, None)
    assert text == "fields(165, EN[31] IRQ[30:28])"
    assert "×" not in text


def test_render_fields_comma_form_round_trips_separator_style() -> None:
    node = parse("fields(165, EN[31], IRQ[30:28])")
    text = render.render(node, {}, None)
    assert text == "fields(165, EN[31], IRQ[30:28])"


def test_render_layout_name_call_is_an_ordinary_call() -> None:
    node = parse("CTRL(4)")
    text = render.render(node, {}, None)
    assert text == "CTRL(4)"


def test_render_dot_access_ends_with_field_name() -> None:
    node = parse("ans.ADDR")
    text = render.render(node, {}, Value(5))
    assert text.endswith(".ADDR")
