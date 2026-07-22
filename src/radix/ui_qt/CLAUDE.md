# radix.ui_qt gotchas

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
