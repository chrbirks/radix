"""Structured visualization payloads attached to Values.

Toolkit functions that have something worth *drawing* (fixed-point layouts,
clock relations, memory sizing) attach one of these to their result Value.
The engine computes every number in the payload; the UI's VizPanel only
renders them and never re-derives math. Text fields are pre-formatted here
for the same reason.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias


@dataclass(frozen=True)
class FixedPointViz:
    """Qm.n layout for fix()/unfix(): m integer bits (MSB = sign), n fraction."""

    m: int
    n: int
    raw: int  # two's-complement raw word, m+n bits
    exact_text: str  # the requested real value
    stored_text: str  # the value actually representable in Qm.n
    error_text: str  # signed quantization error (e.g. "-6.87e-6")
    error_lsb: float  # |error| in LSBs; 0..0.5 for round-to-nearest


@dataclass(frozen=True)
class ClockViz:
    """Clock relations for period()/freq()/clkdiv().

    freq/period always describe the reciprocal pair. The divider fields are
    set by clkdiv() only; error_ppm stays numeric so the UI can color-code
    it against tolerance thresholds without re-deriving math.
    """

    freq_text: str  # SI-formatted frequency, e.g. "100M"
    period_text: str  # SI-formatted period, e.g. "10n"
    divisor: int | None = None
    target_text: str | None = None  # requested output frequency
    achieved_text: str | None = None  # freq / divisor
    error_text: str | None = None  # pre-formatted, e.g. "+64 ppm" or "-0.79%"
    error_ppm: float | None = None  # signed achieved-vs-target error


VizPayload: TypeAlias = FixedPointViz | ClockViz
