"""The adaptive single-window UI.

Narrow (< WIDE_BREAKPOINT): history/help/vars pane (stretches) / input bar /
inspector, stacked in one column. Wide: a splitter puts the pane stack and
the inspector side by side, with the input bar spanning the full width
underneath. Keyboard-first: the input line is always focused; Up/Down
recall history; `help` and `clear` are typed commands. All math goes through
Session — the UI never computes anything itself.
"""

from __future__ import annotations

import time

from PySide6.QtCore import QEvent, QObject, QPoint, Qt, QTimer
from PySide6.QtGui import QAction, QKeyEvent, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QSplitter,
    QStackedWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from radix import __version__
from radix.engine.errors import CalcError, IncompleteError
from radix.engine.help import general_help_html
from radix.engine.values import Value
from radix.history.store import HistoryStore, StoredEntry
from radix.session import Session
from radix.ui_qt.completer import Completer
from radix.ui_qt.highlight import ExprHighlighter
from radix.ui_qt.history_model import HistoryDelegate, HistoryEntry, HistoryModel
from radix.ui_qt.input_edit import InputBar
from radix.ui_qt.inspector import Inspector
from radix.ui_qt.settings import app_settings, load_session, save_session
from radix.ui_qt.theme import LABEL_FAMILY, Palette

PREVIEW_DEBOUNCE_MS = 100
WIDE_BREAKPOINT = 900  # splitter (pane stack | inspector) above this width

SHORTCUT_HELP = """Keyboard shortcuts
  Enter        evaluate          Up / Down    recall history
  Tab          insert completion Ctrl+Space   open completions
  Ctrl+L       clear history     Ctrl+Shift+C copy last result
  F1 or help   this help         Esc          dismiss help
  Alt+W        cycle word size   Alt+S        toggle signed/unsigned
  Alt+D        toggle deg/rad    Alt+N        cycle notation
  Alt+B        result base       Alt+T        always on top
  Alt+V        variables pane    del <name>   remove a variable
  Alt+E        expand/collapse zero rows in the register view"""


class MainWindow(QMainWindow):
    _wide: bool  # set by _apply_layout; absent until the first call

    def __init__(
        self, session: Session, palette: Palette, store: HistoryStore | None = None
    ) -> None:
        super().__init__()
        self.session = session
        self.palette_tokens = palette
        self.store = store  # None = no persistence (tests)
        self.recall_index: int | None = None
        self._help_overview_shown = False
        self.last_result_text = ""

        self.setWindowTitle(f"Radix v{__version__}")
        self.setMinimumSize(520, 600)

        root = QWidget()
        root.setObjectName("root")
        self.root_layout = QVBoxLayout(root)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)

        self.model = HistoryModel()
        self.delegate = HistoryDelegate(palette)
        self.history_view = QListView()
        self.history_view.setObjectName("history")
        self.history_view.setModel(self.model)
        self.history_view.setItemDelegate(self.delegate)
        self.history_view.setSelectionMode(QListView.SelectionMode.SingleSelection)
        self.history_view.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.history_view.doubleClicked.connect(self._recall_from_view)
        self.history_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.history_view.customContextMenuRequested.connect(self._history_context_menu)

        self.help_pane = QTextEdit()
        self.help_pane.setObjectName("helpPane")
        self.help_pane.setReadOnly(True)
        # No wrapping: aligned columns beat wrapped lines for readability;
        # a horizontal scrollbar appears when the window is narrower.
        self.help_pane.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)

        self.vars_pane = QListWidget()
        self.vars_pane.setObjectName("varsPane")
        self.vars_pane.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.vars_pane.itemClicked.connect(self._insert_var_name)
        self.vars_pane.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.vars_pane.customContextMenuRequested.connect(self._vars_context_menu)

        self.pane_stack = QStackedWidget()
        self.pane_stack.addWidget(self.history_view)
        self.pane_stack.addWidget(self.help_pane)
        self.pane_stack.addWidget(self.vars_pane)
        self.pane_stack.setCurrentWidget(self.history_view)

        self.input_bar = InputBar()
        self.input = self.input_bar.input
        self.preview = self.input_bar.preview
        self.input.setPlaceholderText("type an expression — help for the basics")
        self.input.submitted.connect(self._evaluate)
        self.input.textChanged.connect(self._schedule_preview)
        self.input.installEventFilter(self)
        self.highlighter = ExprHighlighter(self.input.document(), palette)
        self.completer = Completer(self.input, session, palette)

        self.inspector = Inspector(palette, lambda text: QApplication.clipboard().setText(text))
        self.vizpanel = self.inspector.vizpanel
        self.intview = self.inspector.intview
        self.intview.value_to_input.connect(self._set_input)
        self.intview.copied.connect(self._toast)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self._pending_splitter_state: object | None = None
        self._apply_layout(wide=False)
        self.setCentralWidget(root)

        self._build_status_bar()
        self._build_shortcuts()

        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(PREVIEW_DEBOUNCE_MS)
        self.preview_timer.timeout.connect(self._update_preview)

        self.toast_timer = QTimer(self)
        self.toast_timer.setSingleShot(True)
        self.toast_timer.setInterval(1800)
        self.toast_timer.timeout.connect(lambda: self.toast_label.setText(""))

        self.resize(600, 800)  # default size; replaced by restored geometry below
        if self.store is not None:
            load_session(self.session)
            self._refresh_status()
            for old in self.store.load():
                self.model.append(
                    HistoryEntry(old.expression, old.result, old.note, timestamp=old.timestamp)
                )
            self.history_view.scrollToBottom()
            s = app_settings()
            geometry = s.value("geometry")
            if geometry is not None:
                self.restoreGeometry(geometry)
            if s.value("always_on_top", False, type=bool):
                self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            self._pending_splitter_state = s.value("splitter_state")

        self.intview.show_value(None, session.word_size, session.signed)
        self.input.setFocus()

    # -- construction helpers ---------------------------------------------------

    def _build_status_bar(self) -> None:
        bar = self.statusBar()
        self.toast_label = QLabel("")
        self.toast_label.setProperty("class", "statusItem")
        bar.addWidget(self.toast_label, 1)

        self.status_items: dict[str, QToolButton] = {}
        for key, handler in (
            ("angle", self._toggle_angle),
            ("word", self._cycle_word_size),
            ("sign", self._toggle_signed),
            ("base", self._cycle_int_base),
            ("notation", self._cycle_notation),
        ):
            chip = QToolButton()
            chip.setProperty("class", "modeChip")
            chip.setAutoRaise(True)
            chip.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # chips never steal focus
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.clicked.connect(handler)
            bar.addPermanentWidget(chip)
            self.status_items[key] = chip
        help_hint = QToolButton()
        help_hint.setText("?")
        help_hint.setProperty("class", "modeChip")
        help_hint.setAutoRaise(True)
        help_hint.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        help_hint.setCursor(Qt.CursorShape.PointingHandCursor)
        help_hint.setToolTip("help  (F1)")
        help_hint.clicked.connect(lambda _=False: self._show_help())
        bar.addPermanentWidget(help_hint)
        self._refresh_status()

    def _build_shortcuts(self) -> None:
        for keys, handler in (
            ("Ctrl+L", self._clear_history_view),
            ("Ctrl+Shift+C", self._copy_result),
            ("F1", self._show_help),
            ("Alt+W", self._cycle_word_size),
            ("Alt+S", self._toggle_signed),
            ("Alt+D", self._toggle_angle),
            ("Alt+N", self._cycle_notation),
            ("Alt+B", self._cycle_int_base),
            ("Alt+T", self._toggle_always_on_top),
            ("Alt+V", self._toggle_vars),
            ("Alt+E", self._toggle_bit_grid_expanded),
        ):
            action = QAction(self)
            action.setShortcut(QKeySequence(keys))
            action.triggered.connect(handler)
            self.addAction(action)

    def _apply_layout(self, wide: bool) -> None:
        """Narrow: stack / input bar / inspector, one column. Wide: a
        splitter puts the stack and inspector side by side, with the input
        bar spanning the full width underneath.

        Idempotent (resizeEvent calls it on every resize) and safe to call
        before the window is ever shown (the first call always applies,
        since `_wide` doesn't exist yet).
        """
        if hasattr(self, "_wide") and wide == self._wide:
            return
        self._wide = wide
        for w in (self.pane_stack, self.inspector, self.input_bar, self.splitter):
            self.root_layout.removeWidget(w)
        if wide:
            first_time = self.splitter.count() == 0
            if first_time:
                self.splitter.addWidget(self.pane_stack)
                self.splitter.addWidget(self.inspector)
            self.root_layout.addWidget(self.splitter, 1)
            self.root_layout.addWidget(self.input_bar)
            if first_time and self._pending_splitter_state is not None:
                self.splitter.restoreState(self._pending_splitter_state)  # type: ignore[arg-type]
        else:
            self.root_layout.addWidget(self.pane_stack, 1)
            self.root_layout.addWidget(self.input_bar)
            self.root_layout.addWidget(self.inspector)

    # -- evaluate / preview -------------------------------------------------------

    def _evaluate(self) -> None:
        text = self.input.text()
        if not text.strip():
            return
        self._hide_help()
        try:
            outcome = self.session.evaluate(text)
        except CalcError as exc:
            self._show_error(exc)
            return
        if outcome.kind == "help":
            # Bare `help` gets the rich overview; `help <name>` the topic text.
            self._show_help(outcome.help_text if outcome.target else None)
            self.input.clear()
            return
        if outcome.kind == "vars":
            self._show_vars()
            self.input.clear()
            return
        if outcome.kind == "del":
            self.input.clear()
            self._toast(f"deleted {outcome.target}")
            self._refresh_vars_pane()
            return
        if outcome.kind == "clear":
            self.model.clear()
            if self.store is not None:
                self.store.clear()
            self.input.clear()
            self._toast("cleared")
            self.intview.show_value(None, self.session.word_size, self.session.signed)
            self.inspector.show_viz_payload(None)
            self._refresh_vars_pane()
            return
        if outcome.value is None:
            return
        primary = self.session.format_value(outcome.value)
        prefix = f"{outcome.target} ← " if outcome.kind == "assign" else ""
        display = prefix + primary
        self.last_result_text = primary
        self.model.append(
            HistoryEntry(
                text.strip(),
                display,
                outcome.value.note or "",
                value=outcome.value,
                prefix=prefix,
                timestamp=time.time(),
            )
        )
        if self.store is not None:
            self.store.append(text.strip(), display, outcome.value.note or "")
        self.history_view.scrollToBottom()
        self.recall_index = None
        self.input.clear()
        self.preview.setText(" ")
        self._panel_follow(outcome.value)
        if outcome.kind == "assign":
            self._refresh_vars_pane()

    def _schedule_preview(self) -> None:
        self.preview_timer.start()

    def _update_preview(self) -> None:
        text = self.input.text()
        if not text.strip():
            self.highlighter.set_error_span(None)
            self._set_preview(" ", error=False)
            self._panel_follow(self.session.ans)  # back to the last result
            return
        try:
            outcome = self.session.preview(text)
        except IncompleteError:
            self.highlighter.set_error_span(None)
            self._set_preview("…", error=False)
            return  # keep the panel steady while typing continues
        except CalcError as exc:
            self._show_error(exc)
            return
        self.highlighter.set_error_span(None)
        if outcome.kind == "help":
            self._set_preview("press Enter for help", error=False)
            return
        if outcome.kind == "vars":
            self._set_preview("press Enter to list variables", error=False)
            return
        if outcome.kind == "del":
            self._set_preview(f"press Enter to delete {outcome.target}", error=False)
            return
        if outcome.kind == "clear":
            self._set_preview("press Enter to clear variables and history", error=False)
            return
        if outcome.value is None:
            self._set_preview(" ", error=False)
            return
        result = self.session.format_value(outcome.value)
        if outcome.kind == "assign":
            self._set_preview(outcome.normalized, error=False)
        else:
            self._set_preview(f"{outcome.normalized} = {result}", error=False)
        self._panel_follow(outcome.value)

    def _panel_follow(self, value: Value | None) -> None:
        """Point the integer panel at a previewed/committed value.

        Integers drive the editable bit grid; reals show the read-only
        IEEE-754 view (word size 32/64) or grey the panel (8/16).
        """
        self.inspector.show_viz_payload(value.viz if value is not None else None)
        number = value.number if value is not None else None
        if isinstance(number, int):
            self.intview.show_value(number, self.session.word_size, self.session.signed)
            return
        float_views = self.session.float_views_for(value) if value is not None else None
        self.intview.show_value(
            None, self.session.word_size, self.session.signed, float_views=float_views
        )

    def _set_preview(self, text: str, error: bool) -> None:
        self.preview.setText(text)
        self.preview.setProperty("state", "error" if error else "ok")
        style = self.preview.style()
        style.unpolish(self.preview)
        style.polish(self.preview)

    def _show_error(self, exc: CalcError) -> None:
        # The offending span gets a wavy underline in the input itself (a
        # text caret under a differently-sized preview font never lines up).
        self.highlighter.set_error_span((exc.span.start, exc.span.end))
        self._set_preview(exc.message, error=True)

    # -- history recall ---------------------------------------------------------

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if obj is self.input and event.type() == QEvent.Type.FocusOut:
            self.completer.hide()
        if obj is self.input and event.type() == QEvent.Type.KeyPress:
            assert isinstance(event, QKeyEvent)
            if self.completer.handle_key(event):
                return True
            if event.key() == Qt.Key.Key_Up:
                self._recall(-1)
                return True
            if event.key() == Qt.Key.Key_Down:
                self._recall(+1)
                return True
            if event.key() == Qt.Key.Key_Escape:
                if not self.intview.clear_selection():  # bit-range selection first
                    self._hide_help()
                return True
        return super().eventFilter(obj, event)

    def _recall(self, direction: int) -> None:
        entries = self.model.entries
        if not entries:
            return
        if self.recall_index is None:
            if direction > 0:
                return
            self.recall_index = len(entries) - 1
        else:
            self.recall_index += direction
        if self.recall_index < 0:
            self.recall_index = 0
        if self.recall_index >= len(entries):
            self.recall_index = None
            self.input.clear()
            return
        self.completer.suppress_next()  # recalled text must not pop completions
        self.input.setText(entries[self.recall_index].expression)

    def _history_context_menu(self, pos: QPoint) -> None:
        index = self.history_view.indexAt(pos)
        if not index.isValid():
            return
        row = index.row()
        entry = self.model.entries[row]
        menu = QMenu(self)
        actions: dict[QAction, str] = {}

        def add(label: str, action_id: str) -> None:
            actions[menu.addAction(label)] = action_id

        add("copy result", "copy_result")
        add("copy expression", "copy_expression")
        if entry.value is not None and isinstance(entry.value.number, int):
            menu.addSeparator()
            add("copy as hex", "copy_hex")
            add("copy as dec", "copy_dec")
            add("copy as bin", "copy_bin")
        menu.addSeparator()
        add("recall", "recall")
        add("delete entry", "delete")
        chosen = menu.exec(self.history_view.viewport().mapToGlobal(pos))
        if chosen is not None:
            self._history_action(actions[chosen], row)

    def _history_action(self, action: str, row: int) -> None:
        entry = self.model.entries[row]
        clipboard = QApplication.clipboard()
        if action == "copy_result":
            text = entry.result[len(entry.prefix):] if entry.prefix else entry.result
            clipboard.setText(text)
            self._toast(f"copied {text}")
        elif action == "copy_expression":
            clipboard.setText(entry.expression)
            self._toast("expression copied")
        elif action in ("copy_hex", "copy_dec", "copy_bin") and entry.value is not None:
            text = self.session.format_value(entry.value, base=action.removeprefix("copy_"))
            clipboard.setText(text)
            self._toast(f"copied {text}")
        elif action == "recall":
            self._set_input(entry.expression)
        elif action == "delete":
            self.model.remove(row)
            self._persist_history()
            self._toast("entry deleted")

    def _persist_history(self) -> None:
        if self.store is None:
            return
        self.store.rewrite(
            [
                StoredEntry(e.expression, e.result, e.note, e.timestamp)
                for e in self.model.entries
            ]
        )

    def _recall_from_view(self, index: object) -> None:
        row = index.row()  # type: ignore[attr-defined]
        self._set_input(self.model.entries[row].expression)

    def _set_input(self, text: str) -> None:
        self.completer.suppress_next()
        self.input.setText(text)
        self.input.setFocus()

    # -- settings toggles --------------------------------------------------------

    def _cycle_word_size(self) -> None:
        self.session.cycle_word_size()
        self._after_setting_change()

    def _toggle_signed(self) -> None:
        self.session.signed = not self.session.signed
        self._after_setting_change()

    def _toggle_angle(self) -> None:
        self.session.angle_deg = not self.session.angle_deg
        self._after_setting_change()

    def _cycle_notation(self) -> None:
        self.session.cycle_notation()
        self._after_setting_change()

    def _cycle_int_base(self) -> None:
        self.session.cycle_int_base()
        self._after_setting_change()

    def _after_setting_change(self) -> None:
        self._refresh_status()
        self._reformat_history()
        if self.vars_pane.isVisibleTo(self):
            self._refresh_vars_pane()  # values honor the new base/notation
        if self.store is not None:
            save_session(self.session)
        # Re-render the current panel value under the new settings; never re-evaluate.
        self.intview.show_value(
            self.intview.scratch if self.intview.active else None,
            self.session.word_size,
            self.session.signed,
        )
        self._update_preview()

    def _reformat_history(self) -> None:
        """Re-render history results under the current display settings."""
        self.model.reformat(self.session.format_value)

    def _refresh_status(self) -> None:
        session = self.session
        texts = {
            "angle": "DEG" if session.angle_deg else "RAD",
            "word": f"{session.word_size}-bit",
            "sign": "signed" if session.signed else "unsigned",
            "base": session.int_base.upper(),
            "notation": session.notation.replace("eng_si", "eng·si").upper(),
        }
        tips = {
            "angle": "angle unit — click or Alt+D",
            "word": "word size for bit ops — click or Alt+W",
            "sign": "signedness of >> and SGN row — click or Alt+S",
            "base": "integer result base for history & preview — click or Alt+B",
            "notation": "result notation — click or Alt+N",
        }
        for key, label in self.status_items.items():
            label.setText(texts[key])
            label.setToolTip(tips[key])

    # -- help / misc -----------------------------------------------------------------

    def _style_help_pane(self, palette: Palette) -> None:
        """Section headers in the silkscreen face — set before every setHtml,
        since Qt applies a document's default stylesheet at that call."""
        self.help_pane.document().setDefaultStyleSheet(
            f"h3 {{ color: {palette.accent}; font-family: '{LABEL_FAMILY}'; "
            f"letter-spacing: 1px; }}"
        )

    def _show_help(self, text: str | None = None) -> None:
        self._help_overview_shown = text is None
        if text is None:
            self._style_help_pane(self.palette_tokens)
            self.help_pane.setHtml(general_help_html(SHORTCUT_HELP))
        else:
            self.help_pane.setPlainText(text)
        self.pane_stack.setCurrentWidget(self.help_pane)

    def _hide_help(self) -> None:
        self.pane_stack.setCurrentWidget(self.history_view)

    # -- variables pane ---------------------------------------------------------

    def _show_vars(self) -> None:
        self._refresh_vars_pane()
        self.pane_stack.setCurrentWidget(self.vars_pane)

    def _toggle_vars(self) -> None:
        if self.vars_pane.isVisibleTo(self):
            self._hide_help()
        else:
            self._show_vars()

    def _toggle_bit_grid_expanded(self) -> None:
        self.intview.grid_widget.toggle_expanded()

    def _refresh_vars_pane(self) -> None:
        self.vars_pane.clear()
        if not self.session.variables:
            placeholder = QListWidgetItem("no variables — assign with  x = 42")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self.vars_pane.addItem(placeholder)
            return
        for name, value in self.session.variables.items():
            item = QListWidgetItem(f"{name} = {self.session.format_value(value)}")
            item.setData(Qt.ItemDataRole.UserRole, name)
            item.setToolTip("click to insert; right-click or `del <name>` to remove")
            self.vars_pane.addItem(item)

    def _insert_var_name(self, item: QListWidgetItem) -> None:
        name = item.data(Qt.ItemDataRole.UserRole)
        if name:
            self.completer.suppress_next()
            self.input.insertPlainText(name)
            self.input.setFocus()

    def _vars_context_menu(self, pos: QPoint) -> None:
        item = self.vars_pane.itemAt(pos)
        name = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if not name:
            return
        menu = QMenu(self)
        delete = menu.addAction(f"delete {name}")
        if menu.exec(self.vars_pane.mapToGlobal(pos)) is delete:
            del self.session.variables[name]
            self._refresh_vars_pane()
            self._toast(f"deleted {name}")

    def _clear_history_view(self) -> None:
        self.model.clear()
        self._toast("history view cleared (variables kept — type clear to wipe)")

    def _copy_result(self) -> None:
        if self.last_result_text:
            QApplication.clipboard().setText(self.last_result_text)
            self._toast(f"copied {self.last_result_text}")

    def _toggle_always_on_top(self) -> None:
        on_top = not bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, on_top)
        self.show()
        if self.store is not None:
            app_settings().setValue("always_on_top", on_top)
        self._toast("always on top" if on_top else "normal stacking")

    def closeEvent(self, event: object) -> None:
        if self.store is not None:
            save_session(self.session)
            app_settings().setValue("geometry", self.saveGeometry())
            if self.splitter.count() > 0:
                app_settings().setValue("splitter_state", self.splitter.saveState())
        super().closeEvent(event)  # type: ignore[arg-type]

    def _toast(self, message: str) -> None:
        self.toast_label.setText(message)
        self.toast_timer.start()

    def apply_palette(self, palette: Palette) -> None:
        self.palette_tokens = palette
        self.delegate.set_palette(palette)
        self.inspector.set_palette(palette)
        self.highlighter.set_palette(palette)
        self.completer.set_palette(palette)
        self.history_view.viewport().update()
        if self._help_overview_shown and self.help_pane.isVisibleTo(self):
            self._show_help()  # setHtml applies the stylesheet at parse time

    def resizeEvent(self, event: object) -> None:  # popup geometry would go stale
        if hasattr(self, "completer"):
            self.completer.hide()
        if hasattr(self, "_wide"):
            self._apply_layout(self.width() >= WIDE_BREAKPOINT)
        super().resizeEvent(event)  # type: ignore[arg-type]
