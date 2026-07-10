"""Syntax coloring for expressions, driven by the real engine lexer.

classify() runs the same tokenizer the parser uses, so the colors can never
disagree with how the input is actually interpreted (e.g. `4k` colors as one
number, `4*k` as number-operator-identifier). On a lex error the valid prefix
is still colored and the rest is left plain.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat, QTextDocument

from calcutron.engine.functions import CONSTANTS, FUNCTIONS
from calcutron.engine.lexer import tokenize_prefix
from calcutron.ui_qt.theme import Palette

PARENS = {"(", ")", "[", "]"}

Segment = tuple[int, int, str]  # start, length, kind


def classify(text: str) -> list[Segment]:
    """Token segments as (start, length, kind); gaps are left uncolored.

    Kinds: "number", "function", "constant", "operator", "paren", "ident".
    On a lex error the valid prefix is still classified; the rest stays plain.
    """
    segments: list[Segment] = []
    for token in tokenize_prefix(text):
        if token.kind == "NUMBER":
            kind = "number"
        elif token.kind == "IDENT":
            if token.text in FUNCTIONS:
                kind = "function"
            elif token.text in CONSTANTS or token.text == "ans":
                kind = "constant"
            else:
                kind = "ident"
        elif token.text in PARENS:
            kind = "paren"
        else:
            kind = "operator"
        segments.append((token.span.start, token.span.end - token.span.start, kind))
    return segments


def color_for(kind: str, palette: Palette) -> QColor:
    return QColor(
        {
            "number": palette.syn_number,
            "function": palette.syn_function,
            "constant": palette.syn_function,
            "operator": palette.syn_operator,
            "paren": palette.muted,
            "ident": palette.text,
        }[kind]
    )


class ExprHighlighter(QSyntaxHighlighter):
    def __init__(self, document: QTextDocument, palette: Palette) -> None:
        super().__init__(document)
        self.palette_tokens = palette

    def set_palette(self, palette: Palette) -> None:
        self.palette_tokens = palette
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:
        for start, length, kind in classify(text):
            fmt = QTextCharFormat()
            fmt.setForeground(color_for(kind, self.palette_tokens))
            self.setFormat(start, length, fmt)
