# Radix

Keyboard-first scientific + programmer calculator (Python 3.11+, PySide6) for
engineers, with an FPGA/HDL toolkit. Ships as PyInstaller onedir binaries for
Windows and Linux. The full design rationale and feature spec live in
`README.md` and `CHANGELOG.md`.

## Commands

```sh
QT_QPA_PLATFORM=offscreen uv run pytest tests/ -q   # all tests (offscreen-safe)
uv run ruff check src tests                         # lint
uv run mypy                                         # strict on radix.engine.*
uv run radix                                        # launch GUI
uv run radix -e "0xFF << 2"                         # one-shot CLI (no display)
uv run pyinstaller packaging/radix.spec             # frozen build into dist/
```

All three checks must pass before committing. Everything runs through `uv` —
never pip or a bare `python`.

## Architecture

Pipeline: lexer → Pratt parser → AST → tree-walking evaluator → formatter.
Nothing is ever `eval`ed. All tokens/errors carry source `Span`s for caret
diagnostics.

- `src/radix/engine/` — headless math core (lexer, parser, evaluator,
  formatter, functions/constants tables, FPGA helpers, help generation).
  `help` text (plain + HTML variants) and the input autocomplete popup are
  generated from the same tables the evaluator dispatches through — extend
  the tables, never hand-write help entries. Every registered function must
  supply `params` (display argument names) and `category`.
- `src/radix/session.py` — `Session` façade owning all state (variables,
  `ans`, word size, signedness, deg/rad, notation). `evaluate(text,
  commit=False)` is the side-effect-free preview path.
- `src/radix/ui_qt/` — the UI only calls `Session.evaluate` and renders
  the result; it never computes math itself.
- Rich result graphics ride the `Value.viz` channel: engine functions attach
  a frozen payload from `engine/viz.py` (`FixedPointViz`/`ClockViz`/`MemViz` —
  numbers *and* pre-formatted text computed engine-side), and
  `ui_qt/viz_panel.py` only paints it. A new visualization = a new payload
  dataclass + a `_paint_*` branch; never derive math in the panel.
- `tests/` — golden tables are the executable spec; Hypothesis property
  tests; pytest-qt smoke tests.

## Design decisions (settled — do not re-litigate)

- **Fully modeless**: one grammar, no mode switch. `**` is always power, `^`
  is always XOR. Integer results always show hex/dec/bin + bit grid.
- Lexer: longest-identifier-match before SI-suffix reading (`2pi`=2·π,
  `4k`=4000 always); `e` is an exponent only before digits; literal prefixes
  (`hFF`/`xFF`/`b1010`, HDL `8'hFF`, `x"FF"`) win over identifier names.
- Bit ops are integer-only (explicit error on floats, never silent
  truncation) and masked to the session word size; plain arithmetic never
  wraps. `>>` is logical when unsigned, arithmetic when signed.
- Numeric tower: exact Python ints preserved; reals via mpmath (25 dps
  working, 12 sig digits displayed). Display formatting is separate from
  precision.
- The integer panel's `scratch` stays **unmasked**; mask only at
  display/copy time (`_masked_scratch`) so cycling word size never destroys
  upper bits. The input line always reflects bit-grid edits.
- Version is single-sourced from `radix.__version__` (hatchling dynamic
  version); it appears in the window title, help header, and `--version`.
  Versions are a plain incrementing integer (`"1"`, `"2"`, …) — not semver.

## Conventions & gotchas

- mypy is strict on `engine/`; mpmath has no stubs, so `Number: TypeAlias =
  int | Mpf` with `Mpf: TypeAlias = Any` in `values.py`.
- All UI geometry/fonts live in `ui_qt/theme.py` (QSS, px sizes) and the
  constants atop `ui_qt/bit_panel.py`; tests derive expectations from those
  constants (e.g. `BYTE_WIDTH`) — keep new tests constant-derived, not
  hardcoded pixels.
- QSS px fonts leave `QFont.pointSize()` at −1 — scale via
  `history_model._scaled`, never `setPointSizeF` directly.
- `QFontMetrics` (not just `.horizontalAdvance`) segfaults under
  `QT_QPA_PLATFORM=offscreen` for glyphs needing font fallback (e.g. `→`
  U+2192, `←` U+2190) — keep strings that get measured *or painted* (function
  summaries, plain-text labels) to ASCII plus glyphs the bundled font has.
  `HistoryEntry.prefix`/`.result` store the literal `"x ← 12"` form for
  assignments, but nothing may render that string as-is — use
  `history_model.split_assignment(result, prefix) -> (name, value)` to get
  the pieces around the arrow (the history delegate paints `name` as a
  separate badge chip; the RESULT readout joins them with `=`). Also
  construct `QFontMetrics(font)` yourself; `widget.fontMetrics()` can dangle
  in PySide6.
- Pyright "Import could not be resolved" diagnostics for PySide6 etc. are
  IDE-only noise (venv not detected); ruff/mypy/pytest via uv are
  authoritative.
- No git remote is configured, so CI (including the Windows PyInstaller leg)
  has never run; the frozen build is verified locally on Linux only.
- The app icon (radical-sign mark, `#2563eb` tile) lives at
  `src/radix/ui_qt/icons/icon.png` (runtime, via `theme.load_app_icon()`) and
  `packaging/icon.ico` (PyInstaller `EXE(icon=...)`, Windows/macOS only —
  ignored with a warning on Linux, which is expected).
- On Wayland (GNOME Shell), `QApplication.setWindowIcon()` alone is not
  enough — the compositor looks up the icon via the window's desktop-file id
  matched against an *installed* `.desktop` file, ignoring in-process
  `QIcon`s. That's what `app.setDesktopFileName("radix")` (`ui_qt/app.py`)
  plus the shipped `packaging/radix.desktop` and
  `packaging/icons/hicolor/*/apps/radix.png` are for; see README for the
  install step. Don't "fix" a missing/wrong taskbar icon by touching
  `theme.load_app_icon()` again — that path already works, this is a
  separate Linux desktop-integration concern. Two non-obvious failure modes
  if it's still not showing: (1) the install directory is `$XDG_DATA_HOME`,
  not necessarily `~/.local/share` — some setups remap it, check
  `echo $XDG_DATA_HOME` (and compare against the actual `gnome-shell`
  process's env via `/proc/<pid>/environ`, which can differ from an
  interactive shell's if the override lives in shell rc rather than a
  session-wide mechanism); (2) `Exec=` in the desktop file must resolve
  (PATH or absolute path) — GLib's `GDesktopAppInfo` refuses to construct
  *at all* from a file whose `Exec=` doesn't resolve, so an unresolvable
  `Exec=` is indistinguishable from the file not existing, which looks
  exactly like the original bug. Verify with
  `python3 -c "import gi; gi.require_version('Gio','2.0'); from gi.repository import Gio; print(Gio.DesktopAppInfo.new('radix.desktop'))"`
  — `None` means one of these two is still wrong.

## Working preferences

- The user is an FPGA programmer; keyboard-first UX and a modern, clean,
  usability-first UI are hard requirements.
- Verify UI changes visually: render an offscreen screenshot (script in the
  scratchpad that builds `MainWindow`, evaluates an expression, saves
  `window.grab()`) and inspect it — don't trust geometry math alone.
- Commit each completed request as one commit with a short imperative
  subject; don't push (no remote).
- Add user-visible changes to `CHANGELOG.md` (Keep a Changelog format) under
  a new `[Unreleased]` section when post-1.0.0 changes accumulate.
