"""Pretty-printer for the live preview line.

Renders an AST back to text with everything *resolved*: literals normalized
(``4.7k`` → ``4700``), variables and constants substituted with their current
values, ``*`` (explicit or implicit) shown as ``×``, and ``^`` spelled ``XOR``
so its meaning is unmistakable. Small integer exponents render as superscripts
(``(0.002)²``).
"""

from __future__ import annotations

from collections.abc import Mapping

from radix.engine.formatter import format_number
from radix.engine.layouts import flatten_spec
from radix.engine.nodes import (
    Assign,
    Binary,
    Call,
    Field,
    Literal,
    Name,
    Node,
    Slice,
    Unary,
)
from radix.engine.parser import BINARY_BP, SLICE_BP, UNARY_BP
from radix.engine.values import Value

_SUPERSCRIPTS = {"0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
                 "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹"}

_OP_DISPLAY = {"*": "×", "^": "XOR"}


def render(
    node: Node, variables: Mapping[str, Value], ans: Value | None
) -> str:
    return _render(node, variables, ans, parent_bp=0)


def _render(
    node: Node, variables: Mapping[str, Value], ans: Value | None, parent_bp: int
) -> str:
    if isinstance(node, Literal):
        return format_number(Value(node.value))
    if isinstance(node, Name):
        if node.ident == "ans" and ans is not None:
            return format_number(ans)
        if node.ident in variables:
            return format_number(variables[node.ident])
        return node.ident  # pi, e, undefined names: keep symbolic
    if isinstance(node, Unary):
        inner = _render(node.operand, variables, ans, UNARY_BP)
        return _paren(f"{node.op}{inner}", UNARY_BP, parent_bp)
    if isinstance(node, Binary):
        return _render_binary(node, variables, ans, parent_bp)
    if isinstance(node, Call):
        if node.func == "fields" and node.args:
            value_text = _render(node.args[0], variables, ans, 0)
            parts = [value_text] + [_render_spec(a) for a in node.args[1:]]
            return f"fields({', '.join(parts)})"
        args = ", ".join(_render(a, variables, ans, 0) for a in node.args)
        return f"{node.func}({args})"
    if isinstance(node, Slice):
        operand = _render(node.operand, variables, ans, SLICE_BP)
        lsb = _render(node.lsb, variables, ans, 0)
        if node.msb is None:
            return f"{operand}[{lsb}]"
        msb = _render(node.msb, variables, ans, 0)
        return f"{operand}[{msb}:{lsb}]"
    if isinstance(node, Field):
        operand = _render(node.operand, variables, ans, SLICE_BP)
        return f"{operand}.{node.name}"
    if isinstance(node, Assign):
        return f"{node.target} ← {_render(node.expr, variables, ans, 0)}"
    return "?"  # pragma: no cover


def _render_binary(
    node: Binary, variables: Mapping[str, Value], ans: Value | None, parent_bp: int
) -> str:
    bp = BINARY_BP[node.op]
    if node.op == "**":
        exponent = node.right
        if (
            isinstance(exponent, Literal)
            and isinstance(exponent.value, int)
            and 0 <= exponent.value <= 9
        ):
            inner = _render(node.left, variables, ans, 0)
            base = inner if _is_atom(node.left) else f"({inner})"
            return _paren(base + _SUPERSCRIPTS[str(exponent.value)], bp, parent_bp)
        left = _render(node.left, variables, ans, bp)
        right = _render(exponent, variables, ans, bp)  # right-assoc
        return _paren(f"{left}**{right}", bp, parent_bp)
    left = _render(node.left, variables, ans, bp)
    right = _render(node.right, variables, ans, bp + 1)
    op = _OP_DISPLAY.get(node.op, node.op)
    return _paren(f"{left} {op} {right}", bp, parent_bp)


def _render_spec(node: Node) -> str:
    """Render a fields()-spec argument as literal field syntax (no substitution)."""
    parts = []
    for leaf in flatten_spec(node):
        if isinstance(leaf, Slice) and isinstance(leaf.operand, Name):
            name = leaf.operand.ident
            lsb = _render_spec_bound(leaf.lsb)
            if leaf.msb is None:
                parts.append(f"{name}[{lsb}]")
            else:
                parts.append(f"{name}[{_render_spec_bound(leaf.msb)}:{lsb}]")
        else:
            parts.append(_render(leaf, {}, None, 0))
    return " ".join(parts)


def _render_spec_bound(node: Node) -> str:
    if isinstance(node, Literal) and isinstance(node.value, int):
        return str(node.value)
    return _render(node, {}, None, 0)


def _is_atom(node: Node) -> bool:
    return isinstance(node, (Literal, Name, Call, Slice))


def _paren(text: str, bp: int, parent_bp: int) -> str:
    return f"({text})" if bp < parent_bp else text
