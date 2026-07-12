# Radix UI redesign — "Bench instrument" (execution plan)

Status: **complete** (WP1-WP9 done). This document is self-contained: an executor (human or LLM) with no
prior context can implement it. Read the repo's `CLAUDE.md` first — its constraints are law;
the non-negotiable ones are repeated in §3 because violating them causes segfaults or data
loss, not style nits.

**Post-completion follow-up (2026-07-12):** WP3's "delete the BIN row" call (§ below, and the
`test_bin_lane_removed_and_ascii_lane_hides` test) was reversed at the user's request — BIN is
back as a fourth integer-mode lane (`HEX/DEC/BIN/ASC`), set bits highlighted in the grid's
phosphor color, displayed with space-separated nibble groups so the label word-wraps instead of
overflowing at 64-bit (the original truncation problem this WP was trying to fix); the copied
text still uses the canonical `_`-grouped format. Test renamed
`test_bin_lane_highlights_set_bits_but_copies_plain`. Leave the WP3 write-up below as history of
why it was removed the first time — don't re-delete BIN citing it.

## How to execute this plan

- Work packages WP1–WP9 are **ordered**; do them one at a time, in order.
- After each WP, all three gates must pass before moving on:
  ```sh
  QT_QPA_PLATFORM=offscreen uv run pytest tests/ -q
  uv run ruff check src tests
  uv run mypy
  ```
- Verify each WP **visually**: render offscreen screenshots (script pattern in §7) and
  actually inspect them. Do not trust geometry math alone.
- Commit after each completed WP (short imperative subject, e.g. `Add instrument-screen
  design tokens`). Do not push without the user's explicit go-ahead (an `origin` remote is
  configured, but push is a shared-state action — always confirm first, regardless of what
  CLAUDE.md's "no remote configured" note said when it was written). Tick the WP's checkbox
  in this file in the same commit so progress survives across sessions.
- Everything runs through `uv` — never pip or bare `python`.

Progress:

- [x] WP1 — Token system + silkscreen face
- [x] WP2 — MainWindow restructure + adaptive layout
- [x] WP3 — Inspector lanes redesign
- [x] WP4 — Register-view bit grid (collapse rail)
- [x] WP5 — History as ledger
- [x] WP6 — Mode chips
- [x] WP7 — Viz cards + timing diagram
- [x] WP8 — Input row + help/vars polish
- [x] WP9 — Final sweep (screenshot matrix, CHANGELOG)

## 1. Context

Radix is a keyboard-first scientific + programmer calculator (Python 3.11+, PySide6) for one
user, an FPGA engineer. The engine (`src/radix/engine/`) is untouched by this plan; this is a
**UI-only** redesign of `src/radix/ui_qt/` (~2 800 lines) plus deliberate updates to
`tests/test_ui_smoke.py` (40 tests, all passing at commit `cf85f7c`) and `CHANGELOG.md`.

Verified problems with the current UI (offscreen screenshots at 600×800):

- The BIN text row in the integer panel truncates mid-string at 64-bit word size.
- The bit grid always renders the full word — at 64-bit with small values, ~250 px of
  all-zero rows.
- History shows each result in only the current base; the "every integer shows
  hex/dec/bin" promise lives only in the bottom panel, for the last result only.
- Status-bar mode toggles look like inert text.
- Viz cards (clkdiv/fix/mem/float) are cramped text lines with magic pixel constants.
- Overall look is generic grey dark-IDE, indistinct from any editor panel.

User decisions (already made — do not re-ask):

1. **Full redesign** — new visual identity AND structural changes; same engine, same shortcuts.
2. **Adaptive layout** — single column when narrow, history | inspector side-by-side when wide.
3. **Bench-instrument aesthetic** — precision test equipment / waveform viewer, with a
   "datasheet paper" light theme. The design below was produced with the frontend-design
   process (brainstorm → critique against generic defaults → revise) and the rejected
   defaults are named so the executor doesn't drift back into them.

## 2. Design specification

Rejected in design critique (do NOT reintroduce): neutral blue-black canvas with a single
blue accent (templated dark-tool look); one mono typeface for everything (flattens
hierarchy); per-lane rainbow "channel" color ticks (decoration); animation (instruments
don't decorate).

### 2.1 Palette — "instrument screen": a two-channel color system, not one accent

Color is split by meaning, the way a scope separates chrome, traces, and cursors:

| role | dark ("instrument screen") | light ("datasheet") |
|---|---|---|
| canvas / `background` | `#0E1210` (phosphor-substrate graphite, faint green cast) | `#F5F7F6` (cool technical paper) |
| `surface` | `#151B18` | `#FFFFFF` |
| `hairline` | `#242D28` | `#D8DEDA` |
| `text` | `#D6DED9` | `#18211C` (ink) |
| `muted` | `#6C7A72` | `#6E7B74` |
| `accent` = **interaction channel** (focus, selection, caret, completer highlight, links) | `#4C8DFF` (brand blue) | `#2563EB` (icon blue) |
| trace = **data channel** (`bit_on`, waveform, `ok`) | `#3DDC97` (phosphor green) | `#0F9960` |
| cursor = **measurement channel** (`bit_changed`, slice bracket, `warn`) | `#FFC24B` (amber) | `#B87D0F` |
| `error` | `#F2637E` | `#C4344F` |

Green/amber are semantic only — never decorative. Retune `syn_*` (syntax) and `float_*`
(IEEE-754 band) colors to sit on the new canvases; keep them distinguishable from
trace/cursor roles. Fine-tune exact hexes against real screenshots if contrast demands, but
keep the green-cast graphite + two-channel structure.

### 2.2 Typography — silkscreen vs. readout pairing

- **Readout face**: JetBrains Mono (already bundled in `src/radix/ui_qt/fonts/`) — every
  number, expression, lane value, input text.
- **Silkscreen face**: **IBM Plex Sans Condensed SemiBold** (OFL) — uppercase, letter-spaced
  micro-labels: lane names, mode chips, collapse rail, viz-card headers, bit indices'
  companion labels. Bundle the TTF into `src/radix/ui_qt/fonts/` (plus its OFL license
  text), register it in `theme.load_bundled_font()` alongside the mono. All strings set in
  this face must be ASCII (see §3). Fallback if the TTF cannot be sourced: mono +
  QSS `letter-spacing`.
- Scale (module constants in `theme.py`, consumed by QSS and painters):
  `FONT_MICRO=11`, `FONT_SMALL=13`, `FONT_BODY=15`, `FONT_UI=17`, `FONT_RESULT=18`,
  `FONT_INPUT=20`; spacing `SPACE_XS/S/M/L = 4/8/12/16`.

### 2.3 Signature element (the one place of boldness)

The bit grid becomes a **register view**: phosphor cells, per-nibble hex readout, amber
slice bracket, and all-zero upper rows folded into a slim expandable rail. Secondary
signature: the clkdiv viz drawn as a real timing-diagram lane. Everything else stays quiet
and disciplined.

## 3. Non-negotiable constraints (from CLAUDE.md, restated)

1. **Offscreen glyph safety**: `QFontMetrics.horizontalAdvance` segfaults under
   `QT_QPA_PLATFORM=offscreen` for glyphs needing font fallback (`→`, `←`, `Δ`, `…` etc.).
   Non-ASCII glyphs may be **drawn** (the app already draws `←`, `Δ`, `…`) but never
   **measured**. Concretely: the `›` prompt and `…` collapse-rail text are drawn into
   fixed rects / QLabels only; chips and badges measure ASCII text only; never call
   `horizontalAdvance(entry.result)` (assignment results contain `←`).
   **Found in WP2**: this bites you even without calling `horizontalAdvance` yourself —
   `QSplitter.addWidget()` eagerly computes every descendant's `sizeHint()` to place its
   handles, and Qt's own built-in `QPushButton`/`QLabel` `sizeHint()` calls font metrics
   on their text internally. A `QPushButton("→ input")` (bit_panel.py) segfaulted the
   instant it landed inside the new wide-mode splitter, even though nothing in this repo
   called `horizontalAdvance` on it — fixed by changing the label to `"-> input"`. `QLabel`
   text (`"—"`, `"Δ …"`) was empirically confirmed safe in the same splitter context, so
   this is specifically a **button-text** (and likely any eagerly-sized widget's) risk:
   before adding a widget with non-ASCII text to a `QSplitter` (or any new eager-layout
   container introduced later), test it in isolation first, the way this fix was found —
   construct the widget, `QSplitter(...).addWidget(it)`, and confirm no segfault.
2. Always construct `QFontMetrics(font)` yourself; `widget.fontMetrics()` can dangle in
   PySide6 (there is an existing violation to fix at `input_edit.py:27`).
3. QSS px fonts leave `QFont.pointSize()` at −1 — scale painter fonts via the
   `history_model._scaled` pattern or `setPixelSize(theme.FONT_*)`, never `setPointSizeF`.
4. The integer panel's `scratch` stays **unmasked**; mask only at display/copy time
   (`_masked_scratch`). Nothing in this redesign may touch that path
   (`bit_panel.py:315-356`).
5. Tests must stay **constant-derived** (e.g. from `BYTE_WIDTH`, `LINE_H`), not hardcoded
   pixels. Keep layout constants at the top of their modules.
6. The UI never computes math: viz cards paint payload fields only; the history delegate's
   alt-base text comes from `session.format_value`, not arithmetic.
7. The completer popup is a child overlay of the window (Wayland-safe) — keep it that way;
   `MainWindow.resizeEvent` must keep force-hiding it before any layout change.

## 4. Architecture decisions

- **Adaptive layout mechanism**: manual re-parent at breakpoint, splitter only in wide mode.
  Module constant `WIDE_BREAKPOINT = 900` in `main_window.py`. `_apply_layout(wide: bool)`
  is idempotent (guarded by `self._wide: bool | None`), called from `resizeEvent` *after*
  the existing completer force-hide (`main_window.py:608-611`), with `hasattr` guards
  because `resizeEvent` fires during `__init__`.
  - Wide: `QSplitter(Qt.Horizontal)` — left = pane stack, right = inspector; below it the
    input bar spans full width; status bar at bottom. `setChildrenCollapsible(False)`,
    stretch 1:1, QSS-styled handle. Persist via existing `app_settings()`:
    save `splitter_state` in `closeEvent`, restore in `__init__` (geometry first, then
    splitter state).
  - Narrow: today's column — pane stack / input bar / inspector / status bar. No splitter.
  - Re-parenting is safe: the pane stack moves as one widget; the completer is hidden
    during every resize; `Completer.refresh` already re-parents its popup if needed
    (`completer.py:169-170`).
- **Pane stack**: replace the history/help/vars show-hide triple (`main_window.py:512-538`)
  with a `QStackedWidget`. Keeps `isVisibleTo` semantics the tests rely on; keep attribute
  names `history_view`, `help_pane`, `vars_pane`.
- **Modest extraction only** (one user — no over-engineering): new
  `src/radix/ui_qt/inspector.py` with `Inspector(QWidget)` ≈30 lines (QVBoxLayout: VizPanel,
  IntegerView, stretch; forwards `set_palette`); `InputBar(QWidget)` added to
  `input_edit.py` (prompt QLabel + InputEdit + preview QLabel in a grid; `focused` dynamic
  property from focus events). MainWindow keeps direct refs `self.input`, `self.preview`,
  `self.vizpanel`, `self.intview` — tests reach for them. No layout-controller class.

## 5. Work packages

### WP1 — Token system + silkscreen face
**Files**: `src/radix/ui_qt/theme.py`, `src/radix/ui_qt/fonts/` (new TTF + license), maybe `packaging/radix.spec`.

- Keep the frozen `Palette` dataclass ×2 (`theme.py:17-76`), single QSS template
  (`stylesheet()`, `:104-232`), and OS-scheme following (`current_palette`, `:235-239`).
- Re-point palette values per §2.1. Keep all existing field names (every consumer
  references them; `bit_on` becomes trace green, `bit_changed` cursor amber). **Add**
  fields: `ok`, `warn`, `chip_bg`, `chip_bg_active`, `surface_sunken`.
- Add `FONT_*`/`SPACE_*` module constants (§2.2) and `LABEL_FAMILY`; bundle IBM Plex Sans
  Condensed SemiBold and extend `load_bundled_font()` (`:81-91`).
- New QSS selectors: `QToolButton.modeChip` (+hover/pressed), `QSplitter::handle`,
  `QLabel#prompt`, `QLabel.laneName` (silkscreen face, `letter-spacing: 1px`, uppercase
  via text), `QWidget#inputBar[focused="true"]`. All px from token constants.
- Fonts ship as package data today; touch `packaging/radix.spec` only if the frozen build
  misses the new TTF.
- **Tests**: none affected (no test asserts colors). **Verify**: dark+light screenshots of
  the otherwise-unchanged layout.

### WP2 — MainWindow restructure + adaptive layout
**Files**: `main_window.py`, new `inspector.py`, `input_edit.py`, `settings.py`, tests.

- Build the pane stack, `Inspector`, `InputBar` per §4; root layout = content area
  (stretch 1) / InputBar / status bar; `_apply_layout` swaps `pane_stack` and `inspector`
  between the column and the splitter.
- `_show_help/_hide_help/_show_vars/_toggle_vars` become `setCurrentWidget` calls.
- Splitter persistence per §4. Store-less test windows (`store=None`) skip geometry
  restore already (`main_window.py:145-158`); tests start at 600×800 → narrow path
  unchanged.
- **New tests**: `test_wide_layout_splits_and_still_evaluates` (resize 1200×800, assert
  `splitter.count() == 2`, evaluate, assert history+intview update);
  `test_layout_returns_to_single_column` (resize back to 640).
- **Verify**: screenshots narrow 600×800 and wide 1200×800, dark, `0xDEADBEEF` evaluated;
  re-run help/vars/completer tests specifically.

### WP3 — Inspector lanes redesign
**Files**: `bit_panel.py` (`IntegerView`), tests.

- Replace the 5 fixed base rows (`bit_panel.py:263-283`) with 4 generic lane rows
  (silkscreen label `class="laneName"`, value label, copy button). `self.rows` is rebuilt
  per refresh keyed by the current semantic label so tests keep the `rows["HEX"]` idiom.
- Integer mode (`_refresh`, `:358-397`): lanes `HEX`, `DEC`, `ASC`; 4th row hidden.
  - `DEC` merges unsigned+signed: show `views.dec_unsigned`, append a muted
    `(signed −1)`-style suffix **only when** `views.dec_signed != views.dec_unsigned`.
    `_copy_texts["DEC"]` stays plain unsigned; drop `SGN` and `BIN` from `_copy_texts`
    (copy-as-bin/dec survives in the history context menu, `main_window.py:395-422`).
  - `ASC` lane hidden when `views.ascii` has no printable byte (all `.`).
  - **Delete the BIN text row** — the grid is the binary rendering.
- Float mode (`_refresh_float`, `:399-429`): lanes `HEX/SGN/EXP/MAN`, texts unchanged from
  `FloatViews`.
- `show_value`/`scratch`/`_masked_scratch`/`toggle_bit`/`_emit_to_input`/signals/slice
  label format: byte-for-byte unchanged. Delta + slice notes restyled amber.
- **Tests to update**: `test_float_result_shows_ieee754_view` (assert `rows["EXP"]`,
  `rows["SGN"]`; "restored" check → `"EXP" not in rows`, `rows["DEC"]` present);
  `test_bin_row_highlights_set_bits_but_copies_plain` → replaced by
  `test_bin_lane_removed_and_ascii_lane_hides` (`"BIN" not in rows`; ASC hidden for
  `0xFFFF`, visible for `0x746F6B31`); `test_ascii_row` extended with the hidden case.
  **New**: `test_dec_lane_shows_signed_when_differs` (8-bit word, `0xFF` → text contains
  `255` and `-1`).

### WP4 — Register-view bit grid (collapse rail)
**Files**: `bit_panel.py` (`BitGrid`), `main_window.py` (shortcut), tests.

- Add top constants `RAIL_H = 22`, `COLLAPSE_THRESHOLD_ROWS = 2` (collapse only when ≥2
  full rows would be all-zero).
- New state `self.expanded: bool = False`; auto-reset to False when a shown value has
  upper bits set (auto behavior resumes).
- Collapse rule — display-only, integer mode only (never in float mode): the leading
  (MSB-side) full rows where every bit is 0 in `value`, 0 in `changed`, and outside
  `selection` fold into one slim rail: hairline box, muted
  `"… bits 63…16 = 0 — click to expand"` drawn into a fixed rect (`…` = U+2026, drawn
  only, never measured). Rail click toggles both ways (expanded state shows an ASCII
  `"^ collapse"` affordance). Keyboard: **Alt+E** → `toggle_expanded()`, added to
  `_build_shortcuts` (`main_window.py:192-208`) and `SHORTCUT_HELP` (`:45-53`).
- `_cell_rect(bit)` (`:109-117`) becomes collapse-aware: visible bits offset by `RAIL_H`
  when the rail shows; hidden bits return an **empty rect** so `_bit_at` (`:190`) can
  never hit them — a collapsed bit requires expanding first. `_apply_height`/`sizeHint`
  account for rail + visible rows. `mousePressEvent` checks the rail rect first;
  drag-select, click-toggle, tooltips otherwise unchanged (`:203-242`).
- Restyle: set bits phosphor green, changed outlines amber, **selection band amber**
  (`:145-152`, was accent), nonzero nibble hex digits phosphor, indices at `FONT_MICRO`.
- `scratch` is never touched by collapse logic (reads masked display value only).
- **Tests to update**: `test_bit_grid_wraps_to_window_width` (`set_state(0, 32, True)` now
  collapses → set `grid.expanded = True`; add separate collapsed-geometry assertions,
  constant-derived). Verify `test_bit_range_drag_selects_without_toggling` still passes
  (positions derive from `_cell_rect`). **New**:
  `test_zero_upper_rows_collapse_and_expand` (0xFF @ 64-bit: rail active,
  `_cell_rect(40).isEmpty()`, after `toggle_expanded()` `toggle_bit(40)` works and writes
  input); `test_collapse_never_masks_scratch` (collapse + word-size cycle keeps
  `scratch`); `test_changed_upper_bit_prevents_collapse`.

### WP5 — History as ledger
**Files**: `history_model.py`, `main_window.py`, tests.

- Model: add `VALUE_ROLE`/`PREFIX_ROLE` (UserRole+4/+5) returning `entry.value` /
  `entry.prefix`. Stored `entry.result` strings **unchanged** (tests assert
  `"x ← 255"`); `reformat()` contract kept (`:78-90`).
- Delegate (`:103-172`): constructor gains `alt_base: Callable[[Value], str | None]`;
  MainWindow passes a closure over `session` — hex rendering via
  `session.format_value(value, base="hex")` when `session.int_base != "hex"`, else dec;
  `None` for non-ints. No math in the delegate.
  - Assignment badge: when `PREFIX_ROLE` non-empty, paint a rounded chip with the variable
    name (ASCII, measurable) and paint the result without the `x ← ` prefix — paint-only,
    model text untouched.
  - Alt-base chip right-aligned, elided into a fixed-width right column
    (`ALT_CHIP_MAX_W` module constant) — zero measurement of non-ASCII text.
  - `sizeHint`: from self-constructed `QFontMetrics`; height = 2 lines + optional note
    line, **independent of text width** so `reformat()`'s `dataChanged` needs no
    `layoutChanged`. Export padding constants at module top.
- **New test**: `test_history_value_role_and_alt_chip_source` (VALUE_ROLE returns the
  Value; alt_base gives `0x3FC` for 1020 in dec mode, None for `sin(1)`).

### WP6 — Mode chips
**Files**: `main_window.py`, tests (type touch-ups only).

- Delete `_ClickableLabel` (`:614-620`). `_build_status_bar` (`:165-190`) builds
  `QToolButton` chips: `setProperty("class", "modeChip")`, `setAutoRaise(True)`,
  `setFocusPolicy(Qt.NoFocus)` (chips must never steal focus — keyboard-first),
  pointing-hand cursor, same handlers/tooltips; `_refresh_status` (`:490-508`) texts
  unchanged; `?` help chip likewise; toast stays a QLabel.
  `self.status_items: dict[str, QToolButton]`.
- Existing `.text()` assertions (`test_status_bar_cycles_word_size`,
  `test_result_base_applies_to_history_and_preview`) pass unchanged.

### WP7 — Viz cards + timing diagram
**Files**: `viz_panel.py`, tests.

- Replace magic px with named module constants: `CARD_PAD`, `METER_TRACK_W` (was 200),
  `METER_MIN_CLEARANCE` (was the `MARGIN+380` guard), `WAVE_STRIP_MAX_W` (was 420); derive
  the `setFixedHeight` formulas (`:63-69`) from them. Painter fonts from
  `theme.FONT_BODY`/`FONT_MICRO`.
- ClockViz (`_paint_clock`, `:123-195`) becomes a timing diagram: muted reference-clock
  row labeled `T = {period_text}s`, phosphor 2 px divided row labeled `{achieved_text}Hz`,
  hairline baselines, rising-edge tick marks, sharp edges. **Payload text only** — a true
  divided-period string doesn't exist in `ClockViz` (`engine/viz.py`); do NOT compute one
  in the panel (a `divided_period_text` payload field is a possible future engine change,
  out of scope here). Duty readout gated by a named constant; its `horizontalAdvance` is
  ASCII-only (already safe).
- Error coloring: ok → `p.ok`, warn → `p.warn`, bad → `p.error` (`:139-146`).
- **Tests to update**: `test_viz_panel_clock_wave_heights` and `test_viz_panel_float_card`
  re-derive expected heights from the new constants (keep `LINE_H`, `WAVE_STRIP_H`,
  `BAR_H` names). Payload-inspection tests pass untouched.

### WP8 — Input row + help/vars polish
**Files**: `main_window.py`, `input_edit.py` (QSS came in WP1).

- InputBar polish: `›` prompt accent-colored (QLabel, never measured);
  `[focused="true"]` → sunken surface + accent underline; preview visually attached
  (same surface, no gap); error state stays the `state` property + unpolish/polish
  pattern (`main_window.py:330-335`).
- Fix `InputEdit._lock_height` (`input_edit.py:26-28`): `QFontMetrics(self.font())`.
- Help pane: `help_pane.document().setDefaultStyleSheet(...)` from tokens in a new
  `_style_help_pane(palette)`, called from `apply_palette` (`:599-606`) and before each
  `setHtml` in `_show_help` (default stylesheets apply at setHtml time — re-render if the
  pane is visible when the OS palette flips). The engine's `general_help_html` needs no
  changes. Vars pane: QSS-only restyle.
- `test_help_command_shows_pane` (asserts on `toPlainText()`) unaffected.

### WP9 — Final sweep
- Full gates (§ "How to execute").
- **Screenshot matrix** — one scratchpad script building `MainWindow(Session(), palette)`,
  driving each state via `window.input.setPlainText(...)` + `window._evaluate()`, saving
  `window.grab()`:
  {narrow 600×800, wide 1200×800} × {DARK, LIGHT} × {`0xDEADBEEF`, `0xFF` (collapse rail),
  `2.5` (IEEE-754), `clkdiv(50M, 115200)` (timing diagram, warn-level ppm),
  `fix(0.7071, 1, 15)`, `mem(3000, 8)`, `help`} — plus an expanded-grid variant and a
  slice-selected variant. Inspect every image.
- Wide-mode vertical budget check: no starvation at 1200×800 with the clkdiv wave +
  expanded 64-bit grid visible.
- `CHANGELOG.md`: `### Changed` under `[Unreleased]` — bench-instrument redesign (adaptive
  two-pane layout, register-view bit grid with zero-row collapse + Alt+E, merged base
  lanes / BIN row removed, ledger history with alt-base chips and assignment badges, mode
  chips, timing-diagram clock card, instrument-screen dark + datasheet light palettes,
  silkscreen label face).

## 6. Consolidated test impact (40 existing tests)

**Update (6)**: `test_float_result_shows_ieee754_view`,
`test_bin_row_highlights_set_bits_but_copies_plain` (replaced),
`test_ascii_row`, `test_bit_grid_wraps_to_window_width`,
`test_viz_panel_clock_wave_heights`, `test_viz_panel_float_card` — details in WP3/4/7.

**Expected to pass unchanged (34)**: completer suite (overlay untouched), vars/help panes
(QStackedWidget preserves `isVisibleTo`), `test_settings_persist_across_windows`
(640×700 = narrow; `geometry` key semantics unchanged), drag-select (positions derive from
`_cell_rect`), status `.text()` asserts, all model result-string asserts (`"x ← 255"`
stays stored text; badges are paint-only).

**New (~8)**: wide split + evaluate; narrow return; collapse/expand + toggle-after-expand;
collapse never masks scratch; changed upper bit prevents collapse; merged DEC signed
reading; ASC lane hidden; VALUE_ROLE/alt-chip source.

## 7. Screenshot script pattern (scratchpad)

```python
import os, sys
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtWidgets import QApplication
from radix.ui_qt import theme
from radix.ui_qt.main_window import MainWindow
from radix.session import Session

app = QApplication(sys.argv)
mono, label = theme.load_bundled_font()  # returns (mono_family, label_family) since WP1
app.setStyleSheet(theme.stylesheet(theme.DARK, mono, label))

def settle():
    for _ in range(10):
        app.processEvents()

def snap(exprs, name, pal, size=(600, 800)):
    w = MainWindow(Session(), pal)
    w.resize(*size); w.show()
    settle()
    for e in exprs:
        w.input.setPlainText(e); settle()
        w._evaluate(); settle()
    w.grab().save(name); w.close()
```
(Adapt to constructor/signature changes as they land. Run with `uv run python`.)

**Found in WP4**: a single `app.processEvents()` after `_evaluate()` is not always enough once
widgets are nested a level or two deeper than the original flat layout (Inspector/pane_stack
inside root_layout) — a dynamic `setMinimumHeight()` change (e.g. the bit-grid collapse rail)
can take a couple of event-loop iterations to fully propagate up the layout chain. A screenshot
taken too early shows widgets overlapping that are actually fine — always use the `settle()`
loop above (call it after `.show()` and after every state change), not a single `processEvents()`
call, or you will chase a phantom layout bug that isn't there. Confirmed harmless: real usage
runs a continuous event loop, so this never shows up outside of scripted single-shot
screenshots.

## 8. Risk register

1. `resizeEvent` fires during `__init__` — guard `_apply_layout` with `hasattr`, keep the
   completer force-hide first.
2. QSettings: new `splitter_state` key; restore geometry before splitter state.
3. Delegate row height must stay text-width-independent, or `reformat()` needs a
   `layoutChanged` emit.
4. OS palette flip while the help pane is visible — re-`setHtml` after updating the
   document default stylesheet.
5. Offscreen glyphs / QSS px fonts / unmasked scratch — §3 items 1–4 are the review
   checklist for every WP.
