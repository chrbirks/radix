"""Formatter and preview-rendering tests."""

from __future__ import annotations

import mpmath

from calcutron.engine.formatter import format_int_base, format_real, integer_views
from calcutron.session import Session


def test_notations() -> None:
    x = mpmath.mpf("0.00001") * 47  # 4.7e-4
    assert format_real(x, "auto") == "0.00047"
    assert format_real(x, "sci") == "4.7e-4"
    assert format_real(x, "eng") == "470e-6"
    assert format_real(x, "eng_si") == "470u"


def test_auto_switches_to_scientific_for_extremes() -> None:
    assert format_real(mpmath.mpf("1.5e-9"), "auto") == "1.5e-9"
    assert format_real(mpmath.mpf("1e15"), "auto") == "1e+15"
    assert format_real(mpmath.mpf("123.25"), "auto") == "123.25"


def test_engineering_exponent_is_multiple_of_three() -> None:
    assert format_real(mpmath.mpf("1.0e-8"), "eng") == "10e-9"
    assert format_real(mpmath.mpf("1.0e-8"), "eng_si") == "10n"
    assert format_real(mpmath.mpf("2.5e7"), "eng") == "25e+6"
    assert format_real(mpmath.mpf("2.5e7"), "eng_si") == "25M"


def test_negative_and_zero() -> None:
    assert format_real(mpmath.mpf(0), "eng_si") == "0"
    assert format_real(mpmath.mpf("-4.7e3"), "eng_si") == "-4.7k"


def test_integer_views_grouping_and_signedness() -> None:
    views = integer_views(1020, 16)
    assert views.hex == "0x03FC"
    assert views.binary == "0b0000_0011_1111_1100"
    assert views.dec_unsigned == "1020"
    assert views.dec_signed == "1020"
    views = integer_views(-1, 8)
    assert views.hex == "0xFF"
    assert views.dec_unsigned == "255"
    assert views.dec_signed == "-1"


def test_preview_rendering() -> None:
    session = Session()
    assert session.preview("2^10").normalized == "2 XOR 10"
    assert session.preview("4.7k*2").normalized == "4700 × 2"
    assert session.preview("2**2").normalized == "2²"
    assert session.preview("(1+1)**2").normalized == "(1 + 1)²"
    session.evaluate("x = 0xFF")
    assert session.preview("x << 2").normalized == "255 << 2"
    assert session.preview("y = 3*4").normalized == "y ← 3 × 4"
    assert session.preview("1/2pi").normalized == "1 / 2 × pi"


def test_format_int_base_compact() -> None:
    assert format_int_base(1020, "dec", 64) == "1020"
    assert format_int_base(1020, "hex", 64) == "0x3FC"
    assert format_int_base(1020, "bin", 64) == "0b11_1111_1100"
    assert format_int_base(0, "hex", 64) == "0x0"
    assert format_int_base(0xDEADBEEF, "hex", 64) == "0xDEAD_BEEF"
    # Negatives render as word-size two's complement, matching the panel.
    assert format_int_base(-1, "hex", 8) == "0xFF"
    assert format_int_base(-1, "bin", 8) == "0b1111_1111"
    assert format_int_base(-2, "hex", 16) == "0xFFFE"


def test_session_format_value_honors_int_base() -> None:
    session = Session()
    value = session.evaluate("0xFF << 2").value
    assert value is not None
    assert session.format_value(value) == "1020"
    session.int_base = "hex"
    assert session.format_value(value) == "0x3FC"
    assert session.format_value(value, base="dec") == "1020"  # explicit override
    session.int_base = "bin"
    assert session.format_value(value) == "0b11_1111_1100"
    # Floats are untouched by the base setting.
    fval = session.evaluate("1/8").value
    assert fval is not None
    assert session.format_value(fval) == "0.125"
