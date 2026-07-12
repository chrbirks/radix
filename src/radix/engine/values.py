"""The engine's value model.

Two runtime value kinds flow through the evaluator:

- ``int``: exact, arbitrary precision. Stays exact until a float-producing
  operation. Bitwise/shift operators accept only this kind.
- ``mpmath.mpf``: real numbers at elevated working precision (no float64
  artifacts like 0.1 + 0.2).

A value may carry an optional *declared width* (from HDL sized literals such as
``8'hFF``) which the UI uses to decide how many bit cells to light. Width is
display metadata only — it never changes arithmetic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeAlias

import mpmath

if TYPE_CHECKING:
    from radix.engine.viz import VizPayload

# Working precision (decimal digits) for real-number math. Display precision is
# independent and much lower; see formatter.py.
WORKING_DPS = 25

# mpmath ships no type stubs, so mpf is Any to the type checker.
Mpf: TypeAlias = Any
Number: TypeAlias = int | Mpf


@dataclass(frozen=True)
class Value:
    """Evaluation result: a number plus optional display metadata."""

    number: Number
    declared_width: int | None = None  # from HDL sized literals, e.g. 8 for 8'hFF
    prefer_si: bool = False  # period()/freq(): render with an SI suffix (10n, 125M)
    note: str | None = None  # e.g. fix(): quantization error, shown next to the result
    viz: VizPayload | None = None  # structured payload for the UI's VizPanel

    @property
    def is_integer(self) -> bool:
        return isinstance(self.number, int)


def set_working_precision() -> None:
    mpmath.mp.dps = WORKING_DPS


# Engine-wide invariant: importing the engine sets the working precision.
set_working_precision()


def as_int_exact(n: Number) -> int | None:
    """Return the value as an exact int if it is one, else None (no coercion)."""
    return n if isinstance(n, int) else None
