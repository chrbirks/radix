"""Error types for the expression engine.

Every error carries a source span (character offsets into the input line) so the
UI can draw a caret/underline under the offending token. The evaluator and parser
raise only CalcError subclasses; anything else escaping the engine is a bug.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Span:
    """Half-open character range [start, end) in the input string."""

    start: int
    end: int

    def caret_line(self) -> str:
        """Render a caret marker line, e.g. '    ^^^' aligned under the span."""
        width = max(1, self.end - self.start)
        return " " * self.start + "^" * width


def shift(span: Span, delta: int) -> Span:
    """Translate a span by ``delta`` characters, e.g. re-anchoring a span computed
    against a substring back into the full line it was extracted from."""
    return Span(span.start + delta, span.end + delta)


class CalcError(Exception):
    """Base class for all engine errors."""

    def __init__(self, message: str, span: Span) -> None:
        super().__init__(message)
        self.message = message
        self.span = span


class LexError(CalcError):
    """Invalid character or malformed literal."""


class ParseError(CalcError):
    """Structurally invalid expression."""


class EvalError(CalcError):
    """Type/domain/range error during evaluation."""


class IncompleteError(ParseError):
    """Input is a valid prefix of an expression (unclosed paren, trailing operator).

    The live preview treats this differently from a hard error: the user is
    probably still typing.
    """
