# Radix front-panel rework — zones, channels/REF, live history, watch rack

Status: **in progress** (WP1-WP4 done; WP5 not started). This document is self-contained: an executor (human or
LLM) with no prior context can implement it. Read the repo's `CLAUDE.md` first — its constraints
are law.

## Context

Second design round (the "bench instrument" redesign already shipped and stays). User decisions
(asked & answered): **keep** the visual identity (palettes, JetBrains Mono + Plex Condensed
silkscreen), **rethink the working model**, and fix the two named pain points: **inspector
organization** and **empty space / low density** at desktop sizes. Today the model is strictly
REPL — one input, dead one-line history, an inspector that only ever shows the latest value; at
1200×800 most pixels are blank (verified by fresh offscreen screenshots).

Design (fixed, from the frontend-design pass — all inside the bench-instrument vocabulary):

1. **Inspector framed into zones** — silkscreen captions + hairline rules like screen-printed
   front-panel zones: TRACE (viz card), READOUT (lanes), REGISTER (grid), CHANNELS (new). Fixes
   organization.
2. **Channels rack (signature)** — pin values like a scope's saved traces: compact strips (slot
   label C1/C2/… or variable name, formatted value, mini one-row phosphor bit strip). One channel
   arms as **REF**: the Δ note reads "Δ vs C1 +3 -1" and the REF strip shows an XOR readout +
   amber differing-bits mini strip. **The main grid is never painted with diff overlays** — the
   per-cell amber outline was explicitly removed by the user and stays removed.
3. **History click-to-inspect** — single-click an entry → the inspector shows that value (input
   untouched); typing or Esc returns to live-follow; double-click still recalls. History rows get
   a visible selected state (accent bar — interaction channel).
4. **Wide-mode variables watch rack** — left column becomes a vertical splitter: pane stack on
   top, always-visible VARIABLES section below. Fills the dead left column with live state.

Settled reversals to respect (memory): no per-cell changed-bit outlines on the grid; no alt-base
readouts in history rows. Don't re-pitch deselected toolkit cards.

## How to execute this plan

- Work packages WP1–WP5 are **ordered**; do them one at a time, in order.
- After each WP, all three gates must pass before moving on:
  ```sh
  QT_QPA_PLATFORM=offscreen uv run pytest tests/ -q
  uv run ruff check src tests
  uv run mypy
  ```
  plus an offscreen screenshot inspected.
- Commit per completed WP (short imperative subject); no push (or per current session's git
  guidance).
- Offscreen policy: every string a splitter descendant might measure is ASCII; `QFontMetrics(font)`
  constructed manually; mini strips paint zero text.

## WP1 — Inspector zone captions ✅ done (commits 7234729, 499dca0)

- [x] New `src/radix/ui_qt/zones.py`: `ZONE_CAPTION_H = 20`; `ZoneCaption(QWidget)` paints an
      uppercase ASCII caption (LABEL_FAMILY, FONT_MICRO px via manual QFont, `palette.muted`)
      with a 1px `hairline` rule to the right edge; `set_palette()`. Separate module (not
      inspector.py) to avoid an import cycle with bit_panel. Also gained a shared `margin_wrap()`
      helper so all three captions align with the content beneath them (TRACE at `CARD_PAD`,
      READOUT/REGISTER at 12px).
- [x] `inspector.py`: `trace_caption = ZoneCaption("TRACE")` above vizpanel; new
      `show_viz_payload(payload)` toggles caption visibility with the panel — update the two
      direct `vizpanel.show_payload(...)` call sites in `main_window.py` (`_evaluate` clear
      branch ~:287, `_panel_follow` ~:364). Add `Inspector.set_palette`, called from
      `MainWindow.apply_palette` (~:652). `trace_caption.hide()` also called in `__init__` so it
      starts hidden in sync with `VizPanel`'s own constructor-time hide (fixed post-review).
- [x] `bit_panel.py` `IntegerView.__init__` (~:342-405): READOUT caption before the lanes grid,
      REGISTER caption between lanes and `grid_widget`; margins match the lanes (12px); forward
      palette in `IntegerView.set_palette` (~:574).
- [x] Tests: caption texts; TRACE visibility follows vizpanel across `fix(...)` → `1+1`; heights
      derived from `zones.ZONE_CAPTION_H`; TRACE hidden on launch before any submit. Existing 202:
      no breakage (206 total after WP1).
- [x] All three gates green (206 tests, ruff clean, mypy clean) + offscreen screenshots inspected
      (light, dark via full app-level palette switch).
- [x] Committed: `7234729` "Add inspector zone captions", `499dca0` "Hide TRACE caption until a
      viz payload is shown" (post-review fix for an Important finding: caption was visible above
      an empty vizpanel on launch).

Deferred Minor polish (not blocking, noted for later): `ZoneCaption` takes placeholder colors at
construction and relies on callers to call `set_palette()` right after — could take `palette` as
a required constructor arg instead; `paintEvent` rebuilds its `QFont`/`QFontMetrics` every repaint
rather than caching (not a real perf concern given how rarely this widget repaints).

## WP2 — History click-to-inspect + inspect lock ✅ done (commit 17f244f)

- [x] `MainWindow._inspect_locked: bool` (init ~:74). `history_view.clicked.connect(
      self._inspect_from_view)` next to the doubleClicked hookup (~:93): entry with
      `value is None` (disk-loaded) → no-op; else lock + `_panel_follow(entry.value)`.
- [x] Clear paths: `_update_preview` non-empty branch clears the lock (typing resumes
      live-follow); empty branch keeps resetting highlighter/preview but skips
      `_panel_follow(session.ans)` while locked. Esc in `eventFilter` (~:402): priority bit-
      selection > inspect lock (`_clear_inspect_lock(follow_ans=True)`) > hide help. `_evaluate`
      clears the lock at the top (before `input.clear()` fires the debounce).
      `_clear_inspect_lock(follow_ans=False)`: reset flag, `history_view.clearSelection()`,
      optional ans-follow. (Qt emits clicked before doubleClicked — brief lock on recall is
      immediately cleared by textChanged; comment it.)
- [x] `history_model.py` `HistoryDelegate.paint` (~:127): when `State_Selected`, fill row with
      `chip_bg_active` + 2px accent bar at left (`SELECT_BAR_W = 2` constant).
- [x] Tests: drive `_inspect_from_view(model.index(row))` directly; assert inspector shows the
      entry, input untouched, lock set; empty-input preview keeps inspected value while locked
      (contrast `test_panel_follows_input_live` ~:508); typing clears; Esc restores ans and still
      prefers bit-range clearing. Existing Esc/panel tests safe (lock defaults False).
- [x] All three gates green (212 tests, ruff clean, mypy clean) + offscreen screenshot inspected
      (selected row shows chip_bg_active fill + accent bar; inspector shows the clicked entry,
      not `ans`; input left empty/untouched).
- [x] Committed: `17f244f` "Add history click-to-inspect with lock". Review approved on first
      pass, no fix round needed.

Deferred Minor polish (not blocking): `main_window.py`'s Qt-quirk comment near
`_recall_from_view` says the lock is cleared "immediately" by a double-click recall — actually
~100ms later via the preview debounce timer, not synchronous. Cosmetic wording nit only.

## WP3 — Channels rack (pin, persist, reformat) ✅ done (commits 9ba5fee, b7b0428)

- [x] New `src/radix/ui_qt/channels.py`. Constants: `MAX_CHANNELS = 8`, `MINI_STRIP_H = 12`,
      `MINI_CELL_GAP = 1`, `STRIP_PAD = 6`, `MINI_NIBBLE_GAP = 3`.
- [x] `Channel` dataclass: `label` ("C1"… lowest unused, never renumbered; or the assignment's
      variable name), `value: Value | None` (None for text-only restores), `text` (re-rendered
      on settings change).
- [x] `MiniBitStrip(QWidget)`: paint-only single row, MSB left, cell width derived from widget
      width / word_size with nibble gaps; set = `bit_on`, clear = `bit_off`; fixed
      `MINI_STRIP_H`; **no text, no metrics, no mouse**.
- [x] `ChannelStrip(QWidget)`: composed QLabels (`chanSlot` silkscreen / `chanValue` / hidden
      `refTag` amber) over a MiniBitStrip (hidden for non-ints); left-click emits `clicked`
      (arms REF in WP4); custom context menu.
- [x] `ChannelsRack(QWidget)` (`#channelsRack`): owns `channels`, `ref_index`, `word_size`; empty
      state = one muted ASCII hint line "no channels -- Alt+P pins the last result". API:
      `pin(value, text, label) -> str | None` (None when full → caller toasts), `unpin(i)`,
      `refresh(fmt, word_size)` (mirrors `HistoryModel.reformat`), `set_palette`,
      `to_json()`/`restore(blob, fmt, word_size)`; signals `to_input(str)`, `copied(str)`,
      `ref_changed()`. Context menu: `-> input` (masked hex literal for ints), copy, set/clear
      REF, unpin. REF toggling is UI-live (amber tag, menu text) but fully inert outside
      `channels.py` — nothing reads `ref_index` yet, confirmed by review; WP4 wires it up.
- [x] `inspector.py`: CHANNELS caption + rack after intview, before the stretch.
- [x] Pin sources (`main_window.py`): (1) history context menu "pin as channel" when
      `entry.value is not None` — label from `entry.prefix` variable name if assignment (same
      parse as delegate ~history_model.py:160); (2) a "pin" `copyBtn` in `IntegerView`'s actions
      row (bit_panel.py ~:383-398) emitting `pin_requested(int)` with `_masked_scratch` (no-op
      when inactive); (3) `Alt+P` → `_pin_last_result` (toast when `session.ans is None`); added
      to `_build_shortcuts` and `SHORTCUT_HELP` (column alignment preserved). Shared
      `_pin_value(value, label)` formats via `session.format_value`, toasts "pinned C1" /
      "channel rack full -- unpin one". `MainWindow.channels` alias added, matching the existing
      `vizpanel`/`intview` alias pattern.
- [x] Hooks: `_after_setting_change` calls `channels.refresh(session.format_value,
      session.word_size)`; palette forwarding reaches the rack; `channels.to_input → _set_input`,
      `channels.copied → _toast`. "Copy" also writes the real system clipboard (threaded
      `clipboard_setter`, same shape as `IntegerView`'s constructor arg).
- [x] Persistence: QSettings key `"channels"` = JSON blob `{"ref": int|null, "channels":
      [{"label","kind":"int","int":…} | {"label","kind":"text","text":…}]}` (json handles big
      ints); saved in `closeEvent` inside the store guard; restored in `__init__` beside
      geometry/splitter state, swallowing `ValueError/KeyError/TypeError`. `restore()` builds
      into a local list and only assigns `self.channels`/`self.ref_index` after the full loop
      succeeds, so a corrupt blob fails atomically (never partially applied) — confirmed by a
      dedicated regression test (fix commit). Int channels reconstruct `Value(number)` so they
      reformat/diff; non-ints restore text-only.
- [x] Theme: new QSS selectors `#channelsRack`, `QLabel.chanSlot`, `.chanValue`, `.chanHint`,
      `.refTag` (amber via `bit_changed`, silkscreen), plus `QWidget.chanStrip` (hairline
      per-strip separator, beyond the brief's exact list — judged to read more like a
      scope-channel list than a heavy fill).
- [x] Tests (10): pin via `_history_action("pin", row)` (labels C1/variable name); Alt+P handler
      incl. no-`ans` no-op; MAX_CHANNELS cap (8 succeed, 9th fails); base-cycle re-renders text;
      `-> input` inserts hex literal; unpin frees the slot without renumbering survivors;
      persistence round-trip incl. a text-only float channel (two-window pattern) + a
      missing-key window; empty-rack hint; corrupt-blob-falls-back-to-empty-rack (added in the
      post-review fix).
- [x] All three gates green (222 tests, ruff clean, mypy clean) + offscreen screenshots inspected
      (light/dark, empty/pinned — mini bit strips only on int channels, CHANNELS caption aligned
      with READOUT/REGISTER).
- [x] Committed: `9ba5fee` "Add channels rack: pin, persist, reformat", `b7b0428` "Add regression
      test for corrupt channels-blob persistence" (post-review fix for an Important finding: no
      test exercised a genuinely corrupt, as opposed to merely missing, persisted blob).

Deferred Minor polish (not blocking): `MINI_CELL_GAP` constant declared but unused in
`MiniBitStrip.paintEvent` (cells render edge-to-edge, unlike `BitGrid`'s per-cell gap); no test
for the unpin-then-repin label-reuse edge case (logic verified correct by code review); restored
`ref_index` isn't range-validated against the restored channel count (safe by construction,
undocumented). **Note for WP4:** `ref_index` isn't revalidated against word_size changes or
restricted to int-only channels — WP4 should decide the policy on REF-arming a non-int channel.

## WP4 — REF arming + Δ vs REF + XOR mini strip ✅ done (commit 9b82a77)

- [x] `channels.py`: strip click / context menu toggles `ref_index`; armed strip shows the amber
      REF tag + XOR readout label (`f"XOR 0x{(live ^ ref) & mask:X}"`, setText only) + second
      MiniBitStrip painting `(live ^ ref) & mask` in `bit_changed` amber. Rack keeps `_live: int
      | None`; `set_live(value)` re-renders extras (hidden for non-int/no live). `ref_changed`
      emitted on arm/disarm.
- [x] `bit_panel.py` `IntegerView`: `set_reference(label, value)` stores `self._ref: tuple[str,
      int] | None`; `_refresh` computes gained/lost from `_masked_scratch ^ (ref &
      mask)` and sets `delta_label` to `"Δ vs {label} +g -l"`; without REF the existing
      `self.changed` text is unchanged. **`grid_widget.set_state` keeps receiving the existing
      vs-previous `changed` — the REF diff never reaches BitGrid.** Confirmed by a dedicated
      regression test. Scratch machinery untouched. XOR math is UI-presentation arithmetic (no
      engine change).
- [x] `main_window.py`: `ref_changed → _on_ref_changed` (pushes `set_reference` into intview,
      re-pushes `set_live` into rack from the panel's current state); `_panel_follow` also calls
      `channels.set_live(number if isinstance(number, int) else None)` on every path. A restored
      `ref_index` syncs into `intview` right after a successful `channels.restore(...)`, inside
      the same exception-suppressing block, so REF state doesn't need a UI interaction to take
      effect after reload.
- [x] Tests (6): arm REF on pinned 0xFF, evaluate → Δ-vs text with counts computed in-test from
      the XOR; **regression guard: `grid_widget.changed` still equals vs-previous diff** (the
      reversed decision didn't sneak back); XOR readout text; disarm restores plain "Δ +n -m"
      (guards `test_changed_bits_diff_against_previous_value`); float live hides extras; REF
      survives persistence and actually syncs into `intview._ref`, not just `ref_index`.
- [x] All three gates green (228 tests, ruff clean, mypy clean) + offscreen screenshot inspected
      (REF tag, XOR readout, amber diff mini-strip, and intview's "Δ vs C1 +0 -4" all visible
      together; REGISTER grid still shows the unrelated vs-previous diff, confirming it was never
      touched by the REF diff).
- [x] Committed: `9b82a77` "Add REF arming with XOR diff and Δ-vs-REF". Reviewed and approved on
      the first pass, no fix round needed.

Deferred Minor polish (not blocking): REF-armed-on-a-non-int-channel has no dedicated test
(verified safe instead via a code-level "two independent gates" proof — reviewer confirmed
neither gate depends on the other); `xor_label` shares the top row with `value_label`/`ref_tag`
and gets visually dense at narrow widths (cosmetic); the `refTag` QSS class is reused verbatim
for `xor_label` rather than a distinct class (fine while both are the same amber; would need
splitting if their styling ever diverges).

## WP5 — Wide-mode variables watch rack (nested vertical splitter)

- [ ] `main_window.py`: `self.vsplitter = QSplitter(Vertical)` (childrenCollapsible False) +
      `self.watch_section` (ZoneCaption("VARIABLES") + slot for vars_pane); widgets added lazily
      on first wide layout (mirrors the existing splitter pattern); `_pending_vsplitter_state`
      restored alongside `splitter_state` (~:167).
- [ ] `_apply_layout` (~:226-252) rework — wide: vsplitter(pane_stack | watch_section) inside
      splitter(vsplitter | inspector); on every narrow→wide transition move `vars_pane` from the
      QStackedWidget into watch_section (fix `pane_stack.currentWidget()` to history first), and
      `vsplitter.insertWidget(0, pane_stack)` when returning from narrow. Narrow:
      `root_layout.addWidget(pane_stack)` pulls it out; `pane_stack.addWidget(vars_pane)`
      reparents it back. All moves via Qt addWidget/insertWidget (atomic reparent, never
      `setParent(None)`); permanent Python refs on self; `hasattr(self, "_wide")` guard stays.
- [ ] Alt+V / `vars` command: narrow behavior unchanged; wide → toggle/ensure `watch_section`
      visibility (never `setCurrentWidget(vars_pane)` in wide — not a stack member there).
      Persist `watch_visible` + `vsplitter_state` in `closeEvent`.
- [ ] `_refresh_vars_pane()` on narrow→wide transition; existing refresh triggers already fire in
      wide mode (`isVisibleTo` now normally true).
- [ ] Compact restyle via dynamic property `compact` on vars_pane +
      `QListWidget#varsPane[compact="true"]` QSS (unpolish/polish on change).
- [ ] **Pre-step (offscreen)**: change the vars placeholder em-dash (~:594) to ASCII `--` before
      any splitter work — `QSplitter.addWidget` eagerly measures descendants (the documented
      segfault class). No test asserts that text.
- [ ] Tests: update `test_wide_layout_splits_panes_and_evaluates` (~:549) and
      `test_narrow_return_reverts_to_single_column` (~:565) for the new structure; new:
      wide→narrow→wide round trip keeps vars functional; `vars` command in wide; Alt+V branch
      behavior; setting change re-renders watch values in wide; vsplitter persistence. Other
      vars tests run narrow — unaffected.
- [ ] All three gates green + offscreen screenshot inspected.
- [ ] Committed.

## Cross-cutting

- [ ] CHANGELOG `[Unreleased]`: Added (channels rack + REF diff, click-to-inspect, watch rack) /
      Changed (inspector zones).
- [ ] Memory + this doc updated at the end; update `docs/ui-redesign-plan.md` with a pointer note
      (post-completion follow-up section).
- [ ] Final screenshot matrix: {narrow 600×800, wide 1200×800} × {dark, light} × {two pinned
      channels + REF armed + live diff, empty rack, float live value, vars watch populated, help
      pane} — inspect every grab.

## Risks

1. Nested splitter reparenting on breakpoint crossings — mitigations above (WP5).
2. Offscreen font-fallback — ASCII-only measured strings; MiniBitStrip paints no text.
3. Inspect lock vs preview debounce — `_evaluate` clears lock before `input.clear()`.
4. Channels persistence corruption — JSON in one string key, exceptions swallowed to an empty
   rack.
5. Rack overflow — MAX_CHANNELS=8 cap + toast; fixed-height strips; width-derived mini cells
   never wrap.
