"""Entry point: `calcutron` launches the GUI, `calcutron -e EXPR` evaluates once.

The -e form is also the frozen-binary smoke test in CI, so it must not require
a display.
"""

from __future__ import annotations

import argparse
import sys

from calcutron import __version__
from calcutron.engine.errors import CalcError
from calcutron.session import Session


def run_expression(session: Session, text: str) -> int:
    if text.strip() == "help":
        outcome = session.evaluate("help")
        print(outcome.help_text)
        return 0
    try:
        outcome = session.evaluate(text)
    except CalcError as exc:
        print(text, file=sys.stderr)
        print(exc.span.caret_line(), file=sys.stderr)
        print(f"error: {exc.message}", file=sys.stderr)
        return 1
    if outcome.kind == "help":
        print(outcome.help_text)
        return 0
    if outcome.value is None:
        return 0
    primary = session.format_value(outcome.value)
    views = session.views_for(outcome.value)
    if views is not None:
        line = f"{primary}  ({views.hex} | {views.dec_signed} | {views.binary})"
    else:
        line = primary
    if outcome.value.note:
        line += f"  [{outcome.value.note}]"
    print(line)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="calcutron", description="Calcutron-9000 calculator")
    parser.add_argument("-e", "--evaluate", metavar="EXPR", help="evaluate once and exit")
    parser.add_argument(
        "--version", action="version", version=f"Calcutron-9000 {__version__}"
    )
    args = parser.parse_args(argv)
    session = Session()
    if args.evaluate is not None:
        return run_expression(session, args.evaluate)
    from calcutron.ui_qt.app import run_gui

    return run_gui(session)


if __name__ == "__main__":
    sys.exit(main())
