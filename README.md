# Calcutron-9000

Keyboard-first scientific + programmer calculator for engineers, built with
Python and PySide6. Runs on Windows and Linux.

![CI](../../actions/workflows/ci.yml/badge.svg)

Everything is typed into one input field — no button grids. One unified,
modeless grammar: `**` is always power, `^` is always XOR, and any integer
result automatically shows hex, decimal, binary, and a clickable bit panel.
A live preview under the input shows the parsed interpretation and the result
on every keystroke, before you press Enter.

## Quick start

```sh
uv run calcutron                 # GUI
uv run calcutron -e "0xFF << 2"  # one-shot CLI
uv run calcutron -e help         # the built-in overview
```

Or grab a standalone build (no Python needed) from CI artifacts: unzip and run
`calcutron`/`calcutron.exe`. Windows SmartScreen will warn on the unsigned
binary — this is a known v1 limitation.

## The language

```
> 4.7k * 2                 SI suffixes: f p n u µ m k M G T   (4.7k = 4700)
  9400
> 32Ki                     binary prefixes: Ki Mi Gi
  32768
> x = 8'hA5                Verilog/VHDL literals: 8'hFF, 12'b1010_1010, x"FF"
> x[7:4]                   bit slicing and testing: x[3]
  10
> 2**10 + 0b1010           ** = power, ^ = XOR — in every context
> sin(pi/4)                sin cos tan … log ln log2 sqrt exp abs floor ceil round
> clog2(300)               FPGA toolkit: clog2 flog2 mask bit popcount parity
  9                        revbits byteswap16/32/64 sext zext rol ror
> period(100M)             clock helpers, SI-formatted output
  10n
> fix(0.7071, 1, 15)       fixed-point Qm.n with quantization error shown
  23170  (0x5A82)
> ans / 2                  ans = previous result; variables persist per session
> help <<                  help for any operator or function
```

Notable rules (all covered by tests):

- `4k` is always the literal 4000 — multiplying by a variable `k` needs `4*k`.
- `2pi` is 2·π (implicit multiplication); implicit `*` binds exactly like
  explicit `*`, so `1/2pi` is (1/2)·π.
- `e` is an exponent marker only directly before digits (`1.5e-9`); `2e` is 2·e.
- `/` is true division (stays exact for ints when even), `//` truncates toward
  zero, `%` takes the dividend's sign — C conventions.
- Bitwise/shift operators require integers and wrap register-like at the current
  word size (8/16/32/64, status bar); plain arithmetic is never masked.
- `>>` is logical when unsigned, arithmetic when signed (status-bar toggle).

## Keyboard

| Key | Action |
| --- | --- |
| Enter | evaluate |
| Up / Down | recall history |
| Ctrl+L | clear the history view |
| Ctrl+Shift+C | copy last result |
| F1 or `help` | help pane (Esc dismisses) |
| Alt+W / Alt+S | word size / signedness |
| Alt+D / Alt+N | deg-rad / float notation |
| Alt+T | always on top |

`clear` wipes variables and persistent history. History is stored as JSONL in
the platform user-data directory and recalled entries re-evaluate through the
live engine.

## Development

```sh
uv sync                                   # env + deps (uv.lock is authoritative)
uv run pytest                             # golden tables, Hypothesis, pytest-qt
uv run ruff check src tests && uv run mypy
uv run pyinstaller packaging/calcutron.spec --distpath dist --noconfirm
```

Architecture: `src/calcutron/engine/` is a headless, UI-agnostic pipeline
(lexer → Pratt parser → AST → evaluator → formatter; mpmath for reals, exact
Python ints for integer/bit math — never `eval`). `session.py` owns all state
and is the only API the UI and CLI call; `Session.evaluate(text, commit=False)`
is the side-effect-free path the live preview uses. Help text is generated from
the same function/operator tables the evaluator dispatches through, so it
cannot drift. UI lives in `ui_qt/` (bundled JetBrains Mono, OFL-licensed;
light/dark follows the OS).
