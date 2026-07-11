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


VizPayload: TypeAlias = FixedPointViz
