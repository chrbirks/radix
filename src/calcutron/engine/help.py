"""Help text, generated from the same tables the evaluator dispatches through."""

from __future__ import annotations

from calcutron.engine.functions import CONSTANTS, FUNCTIONS

_OPERATOR_HELP: list[tuple[str, str, str]] = [
    # (operator, summary, example) — lowest to highest precedence
    ("|", "Bitwise OR (integers; masked to the word size).", "0xF0 | 0x0F"),
    ("^", "Bitwise XOR — NOT power! Use ** for power.", "2^10 = 8"),
    ("&", "Bitwise AND (integers; masked to the word size).", "0xFF & 0x0F"),
    ("<<", "Shift left (masked to the word size).", "1 << 8"),
    (">>", "Shift right: logical when unsigned, arithmetic when signed.", "0x80 >> 4"),
    ("+", "Addition.", "1 + 2"),
    ("-", "Subtraction (also unary minus).", "5 - 3"),
    ("*", "Multiplication. Adjacency works too: 2pi, 3(x+1).", "6 * 7"),
    ("/", "True division (exact int when it divides evenly).", "10 / 4"),
    ("//", "Integer division, truncating toward zero.", "-7 // 2 = -3"),
    ("%", "Remainder with the sign of the dividend (C-like).", "-7 % 2 = -1"),
    ("~", "Bitwise NOT within the word size.", "~0 = 0xFF…"),
    ("**", "Power, right-associative.", "2**10 = 1024"),
    ("[]", "Bit slice/test: x[7:4] extracts bits, x[3] tests one.", "0xAB[7:4] = 0xA"),
]

_BASICS = """\
Type an expression and press Enter. Everything is keyboard-first — no buttons.

Literals   123   1.5   1.5e-9   0xFF   0b1010   0o17   0xFFFF_0000
           SI suffixes: 4.7k = 4700, 100n = 1e-7   (f p n u µ m k M G T)
           Binary prefixes: 32Ki = 32768   (Ki Mi Gi)
           HDL: 8'hFF   12'b1010_1010   4'd9   x"FF"
           Note: 4k is always 4000 — write 4*k to multiply by a variable k.
Variables  x = 4.7k    then    x * 2      `ans` is the previous result.
Integers   Results that are integers also show hex/dec/bin and the bit panel.
           Word size and signedness affect bit operators and that display only.
Commands   help        this overview            help <name>   one operator/function
           clear       wipe variables & history
"""


def general_help(shortcuts: str | None = None) -> str:
    lines = [_BASICS]
    lines.append("Operators (lowest to highest precedence)")
    for op, summary, example in _OPERATOR_HELP:
        lines.append(f"  {op:4} {summary}  e.g. {example}")
    lines.append("")
    lines.append("Functions")
    names = sorted(FUNCTIONS)
    row: list[str] = []
    for name in names:
        row.append(name)
        if len(row) == 8:
            lines.append("  " + "  ".join(row))
            row = []
    if row:
        lines.append("  " + "  ".join(row))
    lines.append("Constants: " + ", ".join(sorted(CONSTANTS)))
    lines.append('Use help <name> for details, e.g. "help sin" or "help <<".')
    if shortcuts:
        lines.append("")
        lines.append(shortcuts)
    return "\n".join(lines)


def topic_help(topic: str) -> str | None:
    """Help for one function or operator; None if the topic is unknown."""
    spec = FUNCTIONS.get(topic)
    if spec is not None:
        lo, hi = spec.arity
        arity = str(lo) if lo == hi else f"{lo}–{hi}"
        return f"{spec.name}(…) — {spec.summary}  ({arity} argument(s))\nExample: {spec.example}"
    if topic in CONSTANTS:
        return f"{topic} — {CONSTANTS[topic][1]}"
    for op, summary, example in _OPERATOR_HELP:
        if topic == op:
            return f"{op} — {summary}\nExample: {example}"
    return None
