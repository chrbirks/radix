"""Session façade: the only API the UI (and CLI) talk to.

Owns all mutable state — variables, ``ans``, word size, signedness, angle unit,
notation — and exposes ``evaluate(text, commit=...)``. With ``commit=False``
evaluation is completely side-effect free, which is what the live preview uses:
``ans``, variables, and history only change when the user presses Enter.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from calcutron.engine import evaluator, render
from calcutron.engine import fpga as _fpga  # noqa: F401 — registers the FPGA toolkit
from calcutron.engine import help as help_mod
from calcutron.engine.errors import CalcError, EvalError
from calcutron.engine.formatter import IntegerViews, format_number, integer_views
from calcutron.engine.functions import CONSTANTS, FUNCTIONS, EvalContext
from calcutron.engine.nodes import Assign
from calcutron.engine.parser import parse
from calcutron.engine.values import Value

WORD_SIZES = (8, 16, 32, 64)
NOTATIONS = ("auto", "sci", "eng", "eng_si")

RESERVED_NAMES = frozenset({"ans", "help", "clear"}) | frozenset(CONSTANTS) | frozenset(FUNCTIONS)


@dataclass(frozen=True)
class Outcome:
    """Result of evaluating one input line."""

    kind: str  # "value" | "assign" | "help" | "clear" | "empty"
    value: Value | None = None
    target: str | None = None  # assignment target
    normalized: str = ""  # resolved pretty-print of the parse, for the preview
    help_text: str | None = None

    @property
    def primary_text(self) -> str:
        if self.value is None:
            return ""
        return format_number(self.value)


@dataclass
class Session:
    word_size: int = 64
    signed: bool = False
    angle_deg: bool = False
    notation: str = "auto"
    variables: dict[str, Value] = field(default_factory=dict)
    ans: Value | None = None

    # -- settings ------------------------------------------------------------

    @property
    def context(self) -> EvalContext:
        return EvalContext(self.word_size, self.signed, self.angle_deg)

    def cycle_word_size(self) -> int:
        i = WORD_SIZES.index(self.word_size)
        self.word_size = WORD_SIZES[(i + 1) % len(WORD_SIZES)]
        return self.word_size

    def cycle_notation(self) -> str:
        i = NOTATIONS.index(self.notation)
        self.notation = NOTATIONS[(i + 1) % len(NOTATIONS)]
        return self.notation

    # -- evaluation ------------------------------------------------------------

    def evaluate(self, text: str, commit: bool = True) -> Outcome:
        """Evaluate one input line. Raises CalcError subclasses on bad input."""
        line = text.strip()
        if not line:
            return Outcome("empty")
        command = self._command(line, commit)
        if command is not None:
            return command
        node = parse(line)
        preview = render.render(node, self.variables, self.ans)
        if isinstance(node, Assign):
            if node.target in RESERVED_NAMES:
                raise EvalError(
                    f"{node.target!r} is reserved and cannot be assigned", node.target_span
                )
            value = evaluator.evaluate(node.expr, self.context, self.variables, self.ans)
            value = evaluator.guard_finite(value, node.expr.span)
            if commit:
                self.variables[node.target] = value
                self.ans = value
            return Outcome("assign", value, node.target, normalized=preview)
        value = evaluator.evaluate(node, self.context, self.variables, self.ans)
        value = evaluator.guard_finite(value, node.span)
        if commit:
            self.ans = value
        return Outcome("value", value, normalized=preview)

    def _command(self, line: str, commit: bool) -> Outcome | None:
        word, _, rest = line.partition(" ")
        rest = rest.strip()
        if word == "help":
            if rest.startswith("="):
                return None  # `help = ...` is an assignment attempt → reserved-name error
            if rest:
                text = help_mod.topic_help(rest)
                if text is None:
                    text = f"no help for {rest!r} — try plain `help` for the overview"
            else:
                text = help_mod.general_help()
            return Outcome("help", help_text=text)
        if word == "clear" and not rest:
            if commit:
                self.variables.clear()
                self.ans = None
            return Outcome("clear")
        return None

    # -- display helpers -------------------------------------------------------

    def format_value(self, value: Value) -> str:
        return format_number(value, self.notation)

    def views_for(self, value: Value) -> IntegerViews | None:
        """Hex/dec/bin renderings if the value is an integer, else None."""
        if not isinstance(value.number, int):
            return None
        return integer_views(value.number, self.word_size)

    def preview(self, text: str) -> Outcome:
        """Side-effect-free evaluation for the live preview line.

        Raises CalcError like evaluate(); IncompleteError means "still typing".
        """
        return self.evaluate(text, commit=False)


__all__ = ["Session", "Outcome", "CalcError", "WORD_SIZES", "NOTATIONS"]
