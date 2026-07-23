"""CSR field layouts: structural spec interpretation and decoding."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from radix.engine.errors import EvalError, Span
from radix.engine.nodes import Binary, Literal, Name, Node, Slice


@dataclass(frozen=True)
class CsrField:
    name: str
    msb: int
    lsb: int  # msb == lsb for single-bit fields

    @property
    def width(self) -> int:
        return self.msb - self.lsb + 1


@dataclass(frozen=True)
class Csr:
    name: str | None  # None for one-shot csr(...)
    fields: tuple[CsrField, ...]  # stored msb-descending

    @property
    def top_bit(self) -> int:
        return max(f.msb for f in self.fields)

    def spec_text(self) -> str:
        return " ".join(_field_repr(f.name, f.msb, f.lsb) for f in self.fields)

    def field(self, name: str) -> CsrField | None:
        for f in self.fields:
            if f.name == name:
                return f
        return None


def flatten_spec(node: Node) -> list[Node]:
    """Flatten a left-nested implicit-mul Binary('*') chain into leaves."""
    if isinstance(node, Binary) and node.op == "*":
        return flatten_spec(node.left) + flatten_spec(node.right)
    return [node]


def csr_from_nodes(nodes: list[Node], name: str | None) -> Csr:
    """Validate leaves and build a Csr. Raises EvalError with precise spans."""
    seen: dict[str, Span] = {}
    built: list[CsrField] = []
    for leaf in nodes:
        if not isinstance(leaf, Slice) or not isinstance(leaf.operand, Name):
            raise EvalError(
                "field ranges must be literal integers, e.g. ADDR[27:8]", leaf.span
            )
        lsb = _literal_nonneg_int(leaf.lsb)
        if lsb is None:
            raise EvalError(
                "field ranges must be literal integers, e.g. ADDR[27:8]", leaf.lsb.span
            )
        if leaf.msb is None:
            msb = lsb
        else:
            msb_val = _literal_nonneg_int(leaf.msb)
            if msb_val is None:
                raise EvalError(
                    "field ranges must be literal integers, e.g. ADDR[27:8]", leaf.msb.span
                )
            msb = msb_val
        if msb < lsb:
            raise EvalError(
                f"invalid field range [{msb}:{lsb}] — msb must be >= lsb", leaf.span
            )
        field_name = leaf.operand.ident
        if field_name in seen:
            raise EvalError(f"duplicate field name {field_name!r}", leaf.operand.span)
        for prev in built:
            if lsb <= prev.msb and prev.lsb <= msb:
                raise EvalError(
                    f"field {_field_repr(field_name, msb, lsb)} overlaps "
                    f"{_field_repr(prev.name, prev.msb, prev.lsb)}",
                    leaf.span,
                )
        seen[field_name] = leaf.operand.span
        built.append(CsrField(field_name, msb, lsb))
    ordered = tuple(sorted(built, key=lambda f: -f.msb))
    return Csr(name, ordered)


def csr_to_json(csr: Csr) -> dict[str, Any]:
    """JSON-safe representation of a csr, for session persistence."""
    return {
        "name": csr.name,
        "fields": [{"name": f.name, "msb": f.msb, "lsb": f.lsb} for f in csr.fields],
    }


def csr_from_json(data: dict[str, Any]) -> Csr:
    """Inverse of ``csr_to_json``. Raises on malformed data."""
    fields = tuple(
        CsrField(f["name"], f["msb"], f["lsb"]) for f in data["fields"]
    )
    return Csr(data["name"], fields)


def format_field_value(field: CsrField, value: int) -> str:
    """'1' / '0b101' / '0xC01A0' — the one formatting rule for a field's value."""
    if field.width == 1:
        return str(value)
    if field.width <= 4:
        return f"0b{value:0{field.width}b}"
    hex_digits = -(-field.width // 4)  # ceil(width / 4)
    return f"0x{value:0{hex_digits}X}"


def decode_note(csr: Csr, raw: int) -> str:
    """'EN=1 IRQ=0b000 ADDR=0xC01A0 CMD=0xF3' — formatting rules below."""
    parts = [f"{f.name}={format_field_value(f, extract(csr, f, raw))}" for f in csr.fields]
    return " ".join(parts)


def extract(csr: Csr, field: CsrField, raw: int) -> int:
    return (raw >> field.lsb) & ((1 << field.width) - 1)


def _literal_nonneg_int(node: Node) -> int | None:
    if isinstance(node, Literal) and isinstance(node.value, int) and node.value >= 0:
        return node.value
    return None


def _field_repr(name: str, msb: int, lsb: int) -> str:
    return f"{name}[{msb}]" if msb == lsb else f"{name}[{msb}:{lsb}]"
