"""Golden tests for the FPGA/HDL toolkit."""

from __future__ import annotations

import pytest

from calcutron.engine.errors import EvalError
from calcutron.session import Session


def run(text: str, **settings: object) -> str:
    session = Session()
    for key, value in settings.items():
        setattr(session, key, value)
    outcome = session.evaluate(text)
    assert outcome.value is not None
    return session.format_value(outcome.value)


# -- bit utilities ----------------------------------------------------------------

CASES = [
    ("clog2(300)", "9"),
    ("clog2(256)", "8"),
    ("clog2(257)", "9"),
    ("clog2(1)", "0"),
    ("flog2(300)", "8"),
    ("flog2(256)", "8"),
    ("mask(12)", "4095"),
    ("mask(0)", "0"),
    ("bit(7)", "128"),
    ("popcount(0xF0F0)", "8"),
    ("parity(0b1011)", "1"),
    ("parity(0b11)", "0"),
    ("revbits(0b1101, 4)", "11"),  # 0b1011
    ("byteswap16(0x1234)", "13330"),  # 0x3412
    ("byteswap32(0x12345678)", "2018915346"),  # 0x78563412
    ("byteswap64(1)", "72057594037927936"),  # 1 << 56
    ("zext(0x1FF, 8)", "255"),
    ("sext(0x80, 8)", "18446744073709551488"),  # sign-extended to 64 bits
    ("rol(0x80, 1)", "256"),
    ("ror(1, 1)", "9223372036854775808"),  # 1 << 63
]


@pytest.mark.parametrize(("text", "expected"), CASES)
def test_bit_utilities(text: str, expected: str) -> None:
    assert run(text) == expected


def test_rotates_use_word_size() -> None:
    assert run("rol(0x80, 1)", word_size=8) == "1"  # wraps around at 8 bits
    assert run("ror(1, 1)", word_size=8) == "128"


def test_sext_respects_word_size() -> None:
    assert run("sext(0x80, 8)", word_size=16) == "65408"  # 0xFF80


def test_bit_utility_domain_errors() -> None:
    for text in ("clog2(0)", "clog2(-1)", "flog2(0)", "mask(-1)", "clog2(1.5)",
                 "sext(1, 0)", "sext(1, 100)", "rol(1.5, 1)"):
        with pytest.raises(EvalError):
            run(text)


# -- clock & unit helpers -----------------------------------------------------------

def test_period_and_freq() -> None:
    assert run("period(100M)") == "10n"
    assert run("freq(8n)") == "125M"
    assert run("period(freq(10n))") == "10n"
    with pytest.raises(EvalError):
        run("period(0)")


def test_period_notation_override() -> None:
    # An explicit session notation beats the SI preference.
    assert run("period(100M)", notation="sci") == "1e-8"


# -- fixed point ----------------------------------------------------------------------

def test_fix_golden() -> None:
    session = Session()
    outcome = session.evaluate("fix(0.7071, 1, 15)")
    assert outcome.value is not None
    assert outcome.value.number == 0x5A82
    assert outcome.value.declared_width == 16
    assert outcome.value.note is not None and "quantization error" in outcome.value.note


def test_fix_unfix_roundtrip() -> None:
    assert run("unfix(0x5A82, 1, 15)") == "0.707092285156"  # 12 sig digits displayed
    assert run("unfix(fix(0.5, 1, 15), 1, 15)") == "0.5"
    # Negative values are two's complement raw
    session = Session()
    outcome = session.evaluate("fix(-0.5, 1, 15)")
    assert outcome.value is not None and outcome.value.number == 0xC000
    assert run("unfix(0xC000, 1, 15)") == "-0.5"


def test_clkdiv_golden_and_viz() -> None:
    from calcutron.engine.viz import ClockViz

    assert run("clkdiv(50M, 115200)") == "434"
    assert run("clkdiv(100M, 25M)") == "4"
    session = Session()
    outcome = session.evaluate("clkdiv(50M, 115200)")
    assert outcome.value is not None
    viz = outcome.value.viz
    assert isinstance(viz, ClockViz)
    assert viz.divisor == 434
    assert viz.achieved_text == "115.207373272k"
    assert viz.error_ppm is not None and abs(viz.error_ppm - 64) < 1
    assert viz.error_text == "+64 ppm"
    assert outcome.value.note is not None and "error" in outcome.value.note
    with pytest.raises(EvalError, match="positive"):
        run("clkdiv(50M, 0)")


def test_period_freq_attach_clock_viz() -> None:
    from calcutron.engine.viz import ClockViz

    session = Session()
    outcome = session.evaluate("period(100M)")
    assert outcome.value is not None
    viz = outcome.value.viz
    assert isinstance(viz, ClockViz)
    assert (viz.freq_text, viz.period_text) == ("100M", "10n")
    assert viz.divisor is None

    outcome = session.evaluate("freq(8n)")
    viz = outcome.value.viz if outcome.value else None
    assert isinstance(viz, ClockViz)
    assert (viz.freq_text, viz.period_text) == ("125M", "8n")


def test_mem_golden_and_viz() -> None:
    from calcutron.engine.viz import MemViz

    assert run("mem(4096, 36)") == "147456"
    session = Session()
    outcome = session.evaluate("mem(4096, 36)")
    assert outcome.value is not None
    viz = outcome.value.viz
    assert isinstance(viz, MemViz)
    assert (viz.addr_bits, viz.addressable) == (12, 4096)
    assert viz.bytes_text == "18 KiB"
    assert viz.utilization == 1.0
    assert outcome.value.note == "addr 12 bits, 18 KiB"

    outcome = session.evaluate("mem(3000, 8)")
    viz = outcome.value.viz if outcome.value else None
    assert isinstance(viz, MemViz)
    assert (viz.addr_bits, viz.addressable) == (12, 4096)
    assert 0.72 < viz.utilization < 0.74 and viz.util_text == "73%"

    with pytest.raises(EvalError, match="positive"):
        run("mem(0, 8)")


def test_fix_attaches_viz_payload() -> None:
    from calcutron.engine.viz import FixedPointViz

    session = Session()
    outcome = session.evaluate("fix(0.5, 1, 15)")
    assert outcome.value is not None
    viz = outcome.value.viz
    assert isinstance(viz, FixedPointViz)
    assert (viz.m, viz.n, viz.raw) == (1, 15, 0x4000)
    assert viz.error_lsb == 0.0  # 0.5 is exactly representable
    assert viz.stored_text == "0.5"

    outcome = session.evaluate("unfix(0x5A82, 1, 15)")
    assert outcome.value is not None
    viz = outcome.value.viz
    assert isinstance(viz, FixedPointViz)
    assert viz.raw == 0x5A82
    assert viz.error_lsb == 0.0 and viz.error_text == "0"


def test_fix_range_errors() -> None:
    with pytest.raises(EvalError, match="does not fit"):
        run("fix(1.5, 1, 15)")  # Q1.15 max is ~0.99997
    with pytest.raises(EvalError):
        run("fix(0.5, 0, 0)")


def test_hdl_width_and_slicing_flow() -> None:
    session = Session()
    session.evaluate("x = 8'hA5")
    assert session.evaluate("x[7:4]").primary_text == "10"
    assert session.evaluate("popcount(x)").primary_text == "4"


def test_help_covers_fpga_functions() -> None:
    session = Session()
    text = session.evaluate("help clog2").help_text
    assert text is not None and "clog2(300)" in text
    overview = session.evaluate("help").help_text
    assert overview is not None and "fix" in overview and "period" in overview
