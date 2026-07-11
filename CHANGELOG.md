# Changelog

All notable changes to Calcutron-9000 are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- The clkdiv clock card now draws the reference vs divided clock waveform
  for divisors up to 16, rising edges aligned, with the divided output's
  duty cycle read out (odd divisors show their asymmetric high/low split).
- New `float32()`/`float64()`/`unfloat32()`/`unfloat64()` functions: the
  IEEE-754 bit pattern of a value as an integer (and back), with a viz card
  showing the sign/exponent/mantissa cell bands and decoded fields — usable
  at any word size, unlike the passive 32/64-bit float view, and pasteable
  into HDL as a plain integer.
- History context menu (right-click an entry): copy result, copy expression,
  copy as hex/dec/bin (for integer results, in the current word size),
  recall, and delete entry (also removed from the persisted history).
- Variables inspector: `vars` (or Alt+V) opens a pane listing every defined
  variable rendered in the current base/notation; click a row to insert the
  name, right-click to delete. New `del <name>` command removes a variable
  from the keyboard. Both commands appear in the autocomplete.
- Autocomplete in the input field: typing an identifier (or Ctrl+Space) pops
  a list of matching functions, constants, variables, and commands with
  signatures and one-line summaries. Tab inserts; Enter inserts only after
  navigating with Up/Down, so plain Enter always evaluates.
- The `help` overview now groups functions by category (trigonometry, bit
  utilities, clock & units, fixed-point, …) with the signature and summary
  of every function; `help <name>` shows real argument names. The GUI help
  pane renders it as an aligned table.

- Integer result display base (dec/hex/bin) for the history pane and the
  live preview — cycle via the status-bar item or Alt+B. Existing history
  entries re-render in the chosen base; float results are unaffected.

- History re-renders when the notation changes (floats included), not just
  on display-base changes.
- The notation setting (sci/eng/eng·si) now applies to integer results too:
  10000000 displays as `1e+7` (SCI), `10e+6` (ENG), or `10M` (ENG·SI).
  AUTO keeps integers exact, and the hex/bin display base takes precedence.
- Settings now persist across restarts: word size, signedness, deg/rad,
  notation, result base, always-on-top, and window size/position. Stored as
  a plain INI file (`AppData` on Windows, `~/.config` on Linux) via
  QSettings.

- New `clkdiv(f_clk, f_target)` toolkit function: nearest integer divider
  with the achieved rate and signed error (ppm, or % past 1%). The viz panel
  shows the clock card — reference freq/period, `/ N → achieved (target)`,
  and the error colored green/amber/red at 1% / 3% (UART tolerance).
  `period()`/`freq()` show their reciprocal pair on the same card.
- New `mem(depth, width)` toolkit function: total bits, address width
  (clog2), and capacity in B/KiB/MiB. The viz panel adds an address-space
  utilization bar that flags non-power-of-two depths (amber, with the
  wasted-address percentage).
- New visualization panel between the preview and the integer panel, driven
  by structured payloads the engine attaches to results. `fix()`/`unfix()`
  now draw the Qm.n layout: sign/integer/fraction bit bands with the binary
  point marked, the exact vs. stored value, and a quantization-error meter
  scaled against the ½ LSB round-to-nearest bound.
- Float results no longer grey the integer panel: at 32/64-bit word size the
  panel shows the IEEE-754 bit pattern with color-coded sign / exponent /
  mantissa bands and decoded HEX / SGN / EXP / MAN rows (read-only; copy
  buttons work — handy for float constants in HDL). 8/16-bit words grey the
  panel as before.
- Bit grid: drag across cells to select a bit range — a readout shows the
  field as `[15:8] = 0xBE = 190 (8 bits)`, and "→ input" then inserts the
  slice expression (`0x…[15:8]`). Esc or a plain click clears the selection.
- Bit grid: each nibble group shows its hex digit above the cells (muted when
  zero), so the grid reads directly against the HEX row.
- Bit grid: bits that flipped vs. the previously shown value are outlined
  (amber) with a `Δ +n -m` gained/lost note — makes the effect of masks,
  shifts, and rotates visible at a glance.
- Bit grid: hovering a cell shows the bit index, its weight (2^n), and its
  byte/nibble position.
- New ASC row in the integer panel: the value's bytes as ASCII (dots for
  non-printable), with its own copy button — quick decode of magic numbers
  and packed strings.

### Fixed

- Errors now underline the offending span directly in the input field (red
  wavy underline) instead of a `·····^` caret in the preview line, which
  drifted off-target because the preview and input use different font sizes.
- Window size was saved on close but never actually restored (the startup
  default overrode it).

### Removed

- The "copy Verilog" / "copy VHDL" / "copy C" buttons in the integer panel.

### Changed

- Larger bit-grid cells (24 px) for readability.
- Clicking a bit in the grid now writes the edited value straight into the
  input field as a hex literal (previously only via the "→ input" button).

## [1.0.0] - 2026-07-11

First release.

### Added

- **Expression engine** — hand-written lexer + Pratt parser, fully modeless:
  `**` is always power, `^` is always XOR, one grammar for scientific and
  programmer math. Exact integers preserved; reals via mpmath (25-digit
  working precision, 12 significant digits displayed; auto/sci/eng/SI
  notations).
- **Literals** — decimal/float with `_` separators, `0x`/`0b`/`0o`,
  `h`/`x`/`b` prefixed numbers (`hFF`, `xFF`, `b1010`), scientific `1.5e-9`,
  SI suffixes (`4.7k`, `100n`; `f p n u µ m k M G T`), binary prefixes
  (`32Ki`, `Mi`, `Gi`), HDL sized literals (`8'hFF`, `12'b1010_1010`, `4'd9`,
  `8'o17`) and VHDL hex strings (`x"FF"`).
- **Operators** — full C-like ladder (`| ^ & << >> + - * / // % ~ **`),
  implicit multiplication (`2pi`, `3(x+1)`), Verilog-style bit slicing
  (`x[7:4]`, `x[3]`). Bit operators are integer-only, masked to the session
  word size (8/16/32/64, signed/unsigned); plain arithmetic never wraps.
- **Variables and `ans`** — `x = 4.7k`, previous result via `ans`.
- **FPGA toolkit** — `clog2 flog2 mask bit popcount parity revbits
  byteswap16/32/64 sext zext rol ror`, clock helpers `period`/`freq` with
  SI-suffix output, fixed-point `fix`/`unfix` (Qm.n) with quantization error.
- **Scientific functions** — `sin cos tan asin acos atan sinh cosh tanh log
  ln log2 sqrt exp abs floor ceil round`; constants `pi`, `e`; deg/rad toggle.
- **Qt GUI (PySide6)** — stacked single-column layout: history, input with
  live syntax highlighting and debounced live preview (side-effect free,
  updates while typing), integer panel (hex/dec/signed/bin rows with per-base
  copy, set bits highlighted, copy as Verilog/VHDL/C), clickable bit grid
  with index labels that wraps to the window width, clickable status bar
  (deg/rad, word size, signedness, notation). The integer panel follows the
  input field live and greys out for float results.
- **Keyboard-first UX** — Enter evaluates, Up/Down recall, Ctrl+L clear,
  Ctrl+Shift+C copy result, F1/`help` help pane, Alt+W/S/D/N cycle settings,
  Alt+T always-on-top.
- **Theming** — OS-following light/dark palettes, flat QSS design, bundled
  JetBrains Mono (OFL).
- **Help** — `help` / `help <name>` generated from the evaluator's own
  function and operator tables; also available as `calcutron -e help`.
- **CLI** — `calcutron -e "0xFF << 2"` one-shot evaluation (prints
  hex/dec/bin for integers), `--version`.
- **Persistence** — history in JSONL via platformdirs, window geometry via
  QSettings.
- **Packaging** — PyInstaller onedir builds for Windows and Linux with CI
  (GitHub Actions matrix) running tests, ruff, mypy, and a frozen-binary
  smoke test.
