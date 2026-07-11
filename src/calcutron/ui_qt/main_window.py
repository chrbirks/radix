"""The single-window, stacked single-column UI.

Layout (top to bottom): history (stretches) / input + live preview / integer
view / status bar. Keyboard-first: the input line is always focused; Up/Down
recall history; `help` and `clear` are typed commands. All math goes through
Session — the UI never computes anything itself.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QAction, QKeyEvent, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QListView,
    QMainWindow,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from calcutron import __version__
from calcutron.engine.errors import CalcError, IncompleteError
from calcutron.engine.help import general_help_html
from calcutron.history.store import HistoryStore
from calcutron.session import Session
from calcutron.ui_qt.bit_panel import IntegerView
from calcutron.ui_qt.completer import Completer
from calcutron.ui_qt.highlight import ExprHighlighter
from calcutron.ui_qt.history_model import HistoryDelegate, HistoryEntry, HistoryModel
from calcutron.ui_qt.input_edit import InputEdit
from calcutron.ui_qt.settings import app_settings, load_session, save_session
from calcutron.ui_qt.theme import Palette

PREVIEW_DEBOUNCE_MS = 100

SHORTCUT_HELP = """Keyboard shortcuts
  Enter        evaluate          Up / Down    recall history
  Tab          insert completion Ctrl+Space   open completions
  Ctrl+L       clear history     Ctrl+Shift+C copy last result
  F1 or help   this help         Esc          dismiss help
  Alt+W        cycle word size   Alt+S        toggle signed/unsigned
  Alt+D        toggle deg/rad    Alt+N        cycle notation
  Alt+B        result base       Alt+T        always on top"""


class MainWindow(QMainWindow):
    def __init__(
        self, session: Session, palette: Palette, store: HistoryStore | None = None
    ) -> None:
        super().__init__()
        self.session = session
        self.palette_tokens = palette
        self.store = store  # None = no persistence (tests)
        self.recall_index: int | None = None
        self.last_result_text = ""

        self.setWindowTitle(f"Calcutron-9000 v{__version__}")
        self.setMinimumSize(520, 600)

        root = QWidget()
        root.setObjectName("root")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.model = HistoryModel()
        self.delegate = HistoryDelegate(palette)
        self.history_view = QListView()
        self.history_view.setObjectName("history")
        self.history_view.setModel(self.model)
        self.history_view.setItemDelegate(self.delegate)
        self.history_view.setSelectionMode(QListView.SelectionMode.SingleSelection)
        self.history_view.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.history_view.doubleClicked.connect(self._recall_from_view)

        self.help_pane = QTextEdit()
        self.help_pane.setObjectName("helpPane")
        self.help_pane.setReadOnly(True)
        self.help_pane.hide()

        self.input = InputEdit()
        self.input.setObjectName("input")
        self.input.setPlaceholderText("type an expression — help for the basics")
        self.input.submitted.connect(self._evaluate)
        self.input.textChanged.connect(self._schedule_preview)
        self.input.installEventFilter(self)
        self.highlighter = ExprHighlighter(self.input.document(), palette)
        self.completer = Completer(self.input, session, palette)

        self.preview = QLabel(" ")
        self.preview.setObjectName("preview")

        self.intview = IntegerView(palette, lambda text: QApplication.clipboard().setText(text))
        self.intview.value_to_input.connect(self._set_input)
        self.intview.copied.connect(self._toast)

        layout.addWidget(self.history_view, stretch=1)
        layout.addWidget(self.help_pane, stretch=1)
        layout.addWidget(self.input)
        layout.addWidget(self.preview)
        layout.addWidget(self.intview)
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
                self.model.append(HistoryEntry(old.expression, old.result, old.note))
            self.history_view.scrollToBottom()
            s = app_settings()
            geometry = s.value("geometry")
            if geometry is not None:
                self.restoreGeometry(geometry)
            if s.value("always_on_top", False, type=bool):
                self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

        self.intview.show_value(None, session.word_size, session.signed)
        self.input.setFocus()

    # -- construction helpers ---------------------------------------------------

    def _build_status_bar(self) -> None:
        bar = self.statusBar()
        self.toast_label = QLabel("")
        self.toast_label.setProperty("class", "statusItem")
        bar.addWidget(self.toast_label, 1)

        self.status_items: dict[str, QLabel] = {}
        for key, handler in (
            ("angle", self._toggle_angle),
            ("word", self._cycle_word_size),
            ("sign", self._toggle_signed),
            ("base", self._cycle_int_base),
            ("notation", self._cycle_notation),
        ):
            label = _ClickableLabel(handler)
            label.setProperty("class", "statusItem")
            label.setCursor(Qt.CursorShape.PointingHandCursor)
            bar.addPermanentWidget(label)
            self.status_items[key] = label
        help_hint = _ClickableLabel(self._show_help)
        help_hint.setText("?")
        help_hint.setProperty("class", "statusItem")
        help_hint.setCursor(Qt.CursorShape.PointingHandCursor)
        help_hint.setToolTip("help  (F1)")
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
        ):
            action = QAction(self)
            action.setShortcut(QKeySequence(keys))
            action.triggered.connect(handler)
            self.addAction(action)

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
        if outcome.kind == "clear":
            self.model.clear()
            if self.store is not None:
                self.store.clear()
            self.input.clear()
            self._toast("cleared")
            self.intview.show_value(None, self.session.word_size, self.session.signed)
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
            )
        )
        if self.store is not None:
            self.store.append(text.strip(), display, outcome.value.note or "")
        self.history_view.scrollToBottom()
        self.recall_index = None
        self.input.clear()
        self.preview.setText(" ")
        number = outcome.value.number
        self.intview.show_value(
            number if isinstance(number, int) else None,
            self.session.word_size,
            self.session.signed,
        )

    def _schedule_preview(self) -> None:
        self.preview_timer.start()

    def _update_preview(self) -> None:
        text = self.input.text()
        if not text.strip():
            self._set_preview(" ", error=False)
            self._panel_follow(self.session.ans)  # back to the last result
            return
        try:
            outcome = self.session.preview(text)
        except IncompleteError:
            self._set_preview("…", error=False)
            return  # keep the panel steady while typing continues
        except CalcError as exc:
            marker = "·" * exc.span.start + "^"
            self._set_preview(f"{marker}  {exc.message}", error=True)
            return
        if outcome.kind == "help":
            self._set_preview("press Enter for help", error=False)
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

    def _panel_follow(self, value: object) -> None:
        """Point the integer panel at a previewed/committed value (or grey it)."""
        number = getattr(value, "number", None)
        self.intview.show_value(
            number if isinstance(number, int) else None,
            self.session.word_size,
            self.session.signed,
        )

    def _set_preview(self, text: str, error: bool) -> None:
        self.preview.setText(text)
        self.preview.setProperty("state", "error" if error else "ok")
        style = self.preview.style()
        style.unpolish(self.preview)
        style.polish(self.preview)

    def _show_error(self, exc: CalcError) -> None:
        marker = "·" * exc.span.start + "^" * max(1, exc.span.end - exc.span.start)
        self._set_preview(f"{marker}  {exc.message}", error=True)

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

    def _show_help(self, text: str | None = None) -> None:
        if text is None:
            self.help_pane.setHtml(general_help_html(SHORTCUT_HELP))
        else:
            self.help_pane.setPlainText(text)
        self.history_view.hide()
        self.help_pane.show()

    def _hide_help(self) -> None:
        self.help_pane.hide()
        self.history_view.show()

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
        super().closeEvent(event)  # type: ignore[arg-type]

    def _toast(self, message: str) -> None:
        self.toast_label.setText(message)
        self.toast_timer.start()

    def apply_palette(self, palette: Palette) -> None:
        self.palette_tokens = palette
        self.delegate.set_palette(palette)
        self.intview.set_palette(palette)
        self.highlighter.set_palette(palette)
        self.completer.set_palette(palette)
        self.history_view.viewport().update()

    def resizeEvent(self, event: object) -> None:  # popup geometry would go stale
        if hasattr(self, "completer"):
            self.completer.hide()
        super().resizeEvent(event)  # type: ignore[arg-type]


class _ClickableLabel(QLabel):
    def __init__(self, handler: object) -> None:
        super().__init__()
        self._handler = handler

    def mousePressEvent(self, event: object) -> None:
        self._handler()  # type: ignore[operator]
