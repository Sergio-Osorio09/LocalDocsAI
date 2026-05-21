"""Chat area widget — message list with streaming support and empty state."""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QMouseEvent, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from localdocsai.ui import icons as ic
from localdocsai.ui._markdown import markdown_to_html as _markdown_to_html


def _make_separator() -> QFrame:
    sep = QFrame()
    sep.setObjectName("messageSeparator")
    sep.setFrameShape(QFrame.Shape.HLine)
    sep.setFixedHeight(1)
    return sep


@dataclass
class SourceRef:
    id: str
    n: int
    title: str
    doc: str  # full file path (for PDF opening)
    doc_code: str  # short readable code, e.g. "RCD N° 029-2016-OS/CD"
    page: int
    section: str  # full section_path
    section_short: str  # last segment of section_path for display
    group_id: str
    chunk_id: str
    score: float
    snippet: str


@dataclass
class TraceInfo:
    retrieved: int
    reranked: int
    tokens: int
    time: str
    model: str
    scope: str


@dataclass
class ChatMessage:
    role: str  # "user" | "assistant"
    text: str
    sources: list[SourceRef] = field(default_factory=list)
    trace: TraceInfo | None = None
    citations_valid: bool = True


# ---------------------------------------------------------------------------
# Message widgets
# ---------------------------------------------------------------------------


class UserMessageWidget(QWidget):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("userMessageWidget")
        h = QHBoxLayout(self)
        h.setContentsMargins(80, 6, 20, 6)
        h.setSpacing(0)
        h.addStretch(1)

        bubble = QLabel(text)
        bubble.setObjectName("userBubble")
        bubble.setWordWrap(True)
        bubble.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        bubble.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        bubble.setMaximumWidth(600)
        h.addWidget(bubble, 0)


class AssistantMessageWidget(QWidget):
    cite_clicked = Signal(int)  # citation number

    def __init__(
        self,
        text: str,
        sources: list[SourceRef],
        trace: TraceInfo | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("assistantMessageWidget")
        self._sources = {s.n: s for s in sources}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 6, 20, 6)
        layout.setSpacing(6)

        # Message body
        self._browser = QTextBrowser()
        self._browser.setObjectName("messageText")
        self._browser.setOpenLinks(False)
        self._browser.anchorClicked.connect(self._on_anchor)
        self._browser.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._browser.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self._browser.document().setDefaultStyleSheet(_MESSAGE_CSS)
        # Resize browser whenever Qt finishes laying out the document (including
        # after the widget is first shown and gets a real width from the layout).
        self._browser.document().documentLayout().documentSizeChanged.connect(self._resize_browser)
        self._raw_text = text
        self._active_n: int | None = None
        self._set_text(text)
        layout.addWidget(self._browser)

        # Pills row (source quick-access chips)
        if sources:
            layout.addWidget(self._build_pills(sources))

        # Trace badge
        if trace:
            layout.addWidget(self._build_trace(trace))

    def _resize_browser(self) -> None:
        doc_height = int(self._browser.document().size().height()) + 8
        self._browser.setFixedHeight(max(60, doc_height))

    def highlight_citation(self, n: int) -> None:
        """Temporary preview highlight (used on hover from sources panel)."""
        fmt = QTextCharFormat()
        fmt.setBackground(QColor(220, 174, 74, 100))
        doc = self._browser.document()
        selections = []
        cursor = QTextCursor(doc)
        while True:
            cursor = doc.find(f"[{n}]", cursor)
            if cursor.isNull():
                break
            from PySide6.QtWidgets import QTextEdit

            sel = QTextEdit.ExtraSelection()
            sel.format = fmt
            sel.cursor = cursor
            selections.append(sel)
        self._browser.setExtraSelections(selections)

    def clear_citation_highlight(self) -> None:
        self._browser.setExtraSelections([])

    def set_active_citation(self, n: int | None) -> None:
        """Persistent 'active' state for citation [n] — solid amber fill.

        Re-renders the HTML so that the matching anchor uses class="cite active"
        instead of just class="cite". Pass None to clear.
        """
        if self._active_n == n:
            return
        self._active_n = n
        self._set_text(self._raw_text)

    def update_text(self, text: str) -> None:
        self._raw_text = text
        self._set_text(text)

    def _set_text(self, text: str) -> None:
        html = _markdown_to_html(text)
        if self._active_n is not None:
            # Promote the chosen citation anchor to the active class.
            old = f'<a href="cite:{self._active_n}" class="cite">[{self._active_n}]</a>'
            new = f'<a href="cite:{self._active_n}" class="cite active">[{self._active_n}]</a>'
            html = html.replace(old, new)
        self._browser.setHtml(f"<body>{html}</body>")

    def _build_trace(self, trace: TraceInfo) -> QWidget:
        w = QWidget()
        w.setObjectName("traceWidget")
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(12)

        parts = [
            f"recuperados: {trace.retrieved}",
            f"reranked: {trace.reranked}",
            f"tokens: {trace.tokens}",
            f"{trace.time}",
            f"{trace.model}",
            f"scope: {trace.scope}",
        ]
        label = QLabel("  ·  ".join(parts))
        label.setObjectName("traceLabel")
        h.addWidget(label)
        h.addStretch(1)
        return w

    def _build_pills(self, sources: list[SourceRef]) -> QWidget:
        w = QWidget()
        w.setObjectName("pillsRow")
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 2, 0, 2)
        row.setSpacing(6)

        _MAX_PILLS = 4
        shown = sources[:_MAX_PILLS]
        remaining = len(sources) - _MAX_PILLS

        for src in shown:
            code = src.doc_code or src.title[:24]
            label = f"[{src.n}]  {code} · p.{src.page}" if src.page else f"[{src.n}]  {code}"
            btn = QPushButton(label)
            btn.setObjectName("sourcePill")
            btn.setFixedHeight(22)
            if src.snippet:
                btn.setToolTip(src.snippet[:80])
            _n = src.n
            btn.clicked.connect(lambda checked=False, n=_n: self.cite_clicked.emit(n))
            row.addWidget(btn)

        if remaining > 0:
            more_btn = QPushButton(f"+{remaining} más")
            more_btn.setObjectName("sourcePill")
            more_btn.setFixedHeight(22)
            more_btn.clicked.connect(lambda: self.cite_clicked.emit(0))
            row.addWidget(more_btn)

        row.addStretch(1)
        return w

    def _on_anchor(self, url: object) -> None:
        href = str(url.toString() if hasattr(url, "toString") else url)
        if href.startswith("cite:"):
            try:
                n = int(href.split("cite:")[1])
                self.cite_clicked.emit(n)
            except ValueError:
                pass


# ---------------------------------------------------------------------------
# Empty state with suggestions
# ---------------------------------------------------------------------------

_SUGGESTIONS = [
    ("Resumen de normativa vigente", "/normas activas en distribución"),
    ("Comparar dos resoluciones", "/comparar RCD-029-2016 y RCD-191-2011"),
    ("Extraer requisitos técnicos", "/listar requisitos para tubería PE-80"),
    ("Generar informe en Word", "/exportar últimas 5 respuestas en docx"),
]


class _SuggestionCard(QFrame):
    """Clickable suggestion card — uses QFrame to avoid QPushButton hover artifacts."""

    clicked = Signal(str)

    def __init__(self, title: str, sub: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._query = title
        self.setObjectName("suggestionCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(72)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(3)

        t = QLabel(title)
        t.setObjectName("suggestionTitle")
        layout.addWidget(t)

        s = QLabel(sub)
        s.setObjectName("suggestionSub")
        layout.addWidget(s)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._query)


class EmptyStateWidget(QWidget):
    suggestion_clicked = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("emptyState")
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(12)

        icon_label = QLabel()
        icon_label.setPixmap(ic.pixmap("sparkle", 32, "#2cc8e4"))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        title = QLabel("¿Qué quieres consultar?")
        title.setObjectName("emptyStateTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        sub = QLabel("Haz una pregunta sobre tus documentos indexados.")
        sub.setObjectName("emptyStateSubtitle")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub)

        layout.addSpacing(16)
        grid_w = QWidget()
        grid = QHBoxLayout(grid_w)
        grid.setSpacing(10)
        for ttl, sub_text in _SUGGESTIONS:
            card = _SuggestionCard(ttl, sub_text)
            card.clicked.connect(self.suggestion_clicked)
            grid.addWidget(card)
        layout.addWidget(grid_w)


# ---------------------------------------------------------------------------
# Streaming indicator
# ---------------------------------------------------------------------------


class StreamingWidget(QWidget):
    """Animated loading indicator shown while the pipeline is running."""

    _SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("assistantMessageWidget")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 8, 20, 8)
        layout.setSpacing(6)

        # Phase row: spinner + label
        phase_row = QHBoxLayout()
        phase_row.setSpacing(8)

        self._spinner_lbl = QLabel(self._SPINNER[0])
        self._spinner_lbl.setObjectName("streamingSpinner")
        self._spinner_lbl.setFixedWidth(20)
        phase_row.addWidget(self._spinner_lbl)

        self._phase_lbl = QLabel("Buscando en documentos…")
        self._phase_lbl.setObjectName("streamingPhase")
        phase_row.addWidget(self._phase_lbl)
        phase_row.addStretch(1)
        layout.addLayout(phase_row)

        # Progress dots row
        self._dots_lbl = QLabel("")
        self._dots_lbl.setObjectName("traceLabel")
        layout.addWidget(self._dots_lbl)

        # Text browser (hidden until text arrives)
        self._browser = QTextBrowser()
        self._browser.setObjectName("messageText")
        self._browser.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._browser.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self._browser.document().setDefaultStyleSheet(_MESSAGE_CSS)
        self._browser.document().documentLayout().documentSizeChanged.connect(
            self._resize_streaming_browser
        )
        self._browser.setFixedHeight(40)
        self._browser.hide()
        layout.addWidget(self._browser)

        self._tick = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(100)

    def _animate(self) -> None:
        self._tick += 1
        self._spinner_lbl.setText(self._SPINNER[self._tick % len(self._SPINNER)])
        dots = "." * ((self._tick // 5) % 4)
        self._dots_lbl.setText(dots)

    def set_phase(self, phase: str) -> None:
        self._phase_lbl.setText(phase)

    def _resize_streaming_browser(self) -> None:
        doc_height = int(self._browser.document().size().height()) + 8
        self._browser.setFixedHeight(max(40, doc_height))

    def update_text(self, text: str) -> None:
        self._browser.show()
        html = _markdown_to_html(text + " ▋")
        self._browser.setHtml(f"<body>{html}</body>")
        cursor = self._browser.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._browser.setTextCursor(cursor)

    def stop(self) -> None:
        self._timer.stop()


# ---------------------------------------------------------------------------
# Main chat area
# ---------------------------------------------------------------------------


class ChatAreaWidget(QWidget):
    """Scrollable message list + composer area."""

    message_submitted = Signal(str)
    cancel_requested = Signal()
    cite_clicked = Signal(int, list)  # (citation_n, sources_list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._messages: list[ChatMessage] = []
        self._current_sources: list[SourceRef] = []
        self._streaming_widget: StreamingWidget | None = None
        self._assistant_widgets: list[AssistantMessageWidget] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        from localdocsai.ui.composer import ComposerWidget

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Scroll area
        self._scroll = QScrollArea()
        self._scroll.setObjectName("chatScrollArea")
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Outer content widget (fills scroll area)
        self._content = QWidget()
        self._content.setObjectName("chatContent")
        outer_v = QVBoxLayout(self._content)
        outer_v.setContentsMargins(0, 12, 0, 24)
        outer_v.setSpacing(0)

        # Centered column — capped at 820 px but with an Expanding horizontal
        # policy and a sensible minimum so the column does NOT shrink down
        # to the width of its smallest child. Without this, the streaming
        # placeholder ("Generando respuesta…") collapses the column to ~200 px
        # and any tokens that arrive get reflowed in a tiny vertical strip
        # (3-5 words per line). When the response widget replaces the
        # placeholder the column re-expands and the reflow becomes normal —
        # but that visual glitch lasts the whole generation.
        self._center_col = QWidget()
        self._center_col.setObjectName("chatCenterCol")
        self._center_col.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self._center_col.setMinimumWidth(620)
        self._center_col.setMaximumWidth(820)
        self._content_layout = QVBoxLayout(self._center_col)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(0)
        self._content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        outer_v.addWidget(self._center_col, 0, Qt.AlignmentFlag.AlignHCenter)
        outer_v.addStretch(1)

        self._empty_state = EmptyStateWidget()
        self._empty_state.suggestion_clicked.connect(self._on_suggestion)
        self._content_layout.addWidget(self._empty_state)

        self._scroll.setWidget(self._content)
        layout.addWidget(self._scroll, 1)

        # Composer
        self._composer = ComposerWidget()
        self._composer.message_submitted.connect(self.message_submitted)
        self._composer.cancel_requested.connect(self.cancel_requested)
        layout.addWidget(self._composer)

    def load_messages(self, messages: list[ChatMessage]) -> None:
        self._messages = messages
        self._current_sources = []
        self._assistant_widgets = []
        self._rebuild_messages()

    def append_user_message(self, text: str) -> None:
        self._hide_empty_state()
        if self._messages:
            self._content_layout.addWidget(_make_separator())
        msg = ChatMessage(role="user", text=text)
        self._messages.append(msg)
        w = UserMessageWidget(text)
        self._content_layout.addWidget(w)
        self._scroll_to_bottom()

    def start_streaming(self) -> None:
        self._streaming_widget = StreamingWidget()
        self._content_layout.addWidget(self._streaming_widget)
        self._scroll_to_bottom()
        self._composer.set_enabled(False)

    def update_streaming(self, text: str) -> None:
        if self._streaming_widget:
            self._streaming_widget.update_text(text)
            self._scroll_to_bottom()

    def highlight_citation(self, n: int) -> None:
        for w in self._assistant_widgets:
            w.highlight_citation(n)

    def clear_citation_highlight(self) -> None:
        for w in self._assistant_widgets:
            w.clear_citation_highlight()

    def set_active_citation(self, n: int | None) -> None:
        """Persistent active citation chip — solid amber. Applies to every
        assistant message that contains the [n] anchor."""
        for w in self._assistant_widgets:
            w.set_active_citation(n)

    def update_streaming_phase(self, phase: str) -> None:
        if self._streaming_widget:
            self._streaming_widget.set_phase(phase)

    def finish_streaming(self, message: ChatMessage) -> None:
        if self._streaming_widget:
            self._streaming_widget.stop()
            self._streaming_widget.setParent(None)
            self._streaming_widget = None

        self._messages.append(message)
        self._current_sources = message.sources

        w = AssistantMessageWidget(message.text, message.sources, message.trace)
        w.cite_clicked.connect(lambda n: self.cite_clicked.emit(n, message.sources))
        self._assistant_widgets.append(w)
        self._content_layout.addWidget(w)
        self._scroll_to_bottom()
        self._composer.set_enabled(True)

    def get_all_sources(self) -> list[SourceRef]:
        sources: list[SourceRef] = []
        for msg in self._messages:
            sources.extend(msg.sources)
        return sources

    def set_scope_label(self, label: str) -> None:
        self._composer.set_scope_label(label)

    def _rebuild_messages(self) -> None:
        # Remove all message widgets (keep empty state)
        while self._content_layout.count() > 0:
            item = self._content_layout.takeAt(0)
            if item and item.widget():
                item.widget().setParent(None)

        if not self._messages:
            self._content_layout.addWidget(self._empty_state)
            self._empty_state.show()
            return

        self._empty_state.hide()
        prev_role = ""
        for msg in self._messages:
            if msg.role == "user" and prev_role == "assistant":
                self._content_layout.addWidget(_make_separator())
            if msg.role == "user":
                self._content_layout.addWidget(UserMessageWidget(msg.text))
            else:
                w = AssistantMessageWidget(msg.text, msg.sources, msg.trace)
                w.cite_clicked.connect(lambda n, s=msg.sources: self.cite_clicked.emit(n, s))
                self._content_layout.addWidget(w)
            prev_role = msg.role

    def _hide_empty_state(self) -> None:
        if self._empty_state.isVisible():
            self._empty_state.hide()
            self._content_layout.removeWidget(self._empty_state)

    def _scroll_to_bottom(self) -> None:
        bar = self._scroll.verticalScrollBar()
        if bar:
            bar.setValue(bar.maximum())

    def _on_suggestion(self, text: str) -> None:
        self._composer.set_text(text)

    def restore_last_question(self) -> None:
        """Put the previous question back into the composer for editing
        (used after a cancellation)."""
        self._composer.restore_last_question()

    def remove_streaming_widget(self) -> None:
        """Tear down the streaming placeholder and remove the last user
        message + separator from the chat. Called when generation is
        cancelled so the user can re-edit and resend the same prompt
        without duplicating it in the history."""
        if self._streaming_widget:
            self._streaming_widget.stop()
            self._streaming_widget.setParent(None)
            self._streaming_widget = None

        # Drop the trailing user message from the model so it doesn't get
        # re-saved on the next submission.
        if self._messages and self._messages[-1].role == "user":
            self._messages.pop()

        # Remove the last 1–2 widgets in the layout (the user bubble and the
        # separator above it, if there was one).
        for _ in range(2):
            if self._content_layout.count() == 0:
                break
            item = self._content_layout.itemAt(self._content_layout.count() - 1)
            w = item.widget() if item else None
            if w is None:
                break
            is_user = w.objectName() == "userMessageWidget"
            is_sep = w.objectName() == "messageSeparator"
            if not (is_user or is_sep):
                break
            self._content_layout.removeWidget(w)
            w.setParent(None)
            if is_user:
                # We removed the user message; the separator above (if any)
                # will be removed on the next iteration.
                continue
            else:
                break

        self._composer.set_enabled(True)


# ---------------------------------------------------------------------------
# QTextBrowser stylesheet
# ---------------------------------------------------------------------------

_MESSAGE_CSS = """
body { color: #ecedf0; font-size: 14.5px; line-height: 1.55; margin: 0; padding: 0; }
strong, b { color: #ffffff; font-weight: 600; }
em, i { color: #b8bbc1; font-style: normal; }
code { font-family: "Geist Mono", "Cascadia Mono", "Consolas", monospace; font-size: 12.5px;
       background: rgba(78,194,232,0.10); padding: 1px 5px; border-radius: 4px;
       color: #4ec2e8; }
pre { background: #1a1d23; border: 1px solid #2b2f37; border-radius: 8px;
      padding: 10px 14px; margin: 8px 0; overflow-x: auto;
      font-family: "Geist Mono", "Cascadia Mono", "Consolas", monospace; font-size: 12.5px; }
pre code { background: none; padding: 0; color: #b8bbc1; }
blockquote { border-left: 2px solid rgba(220,174,74,0.40); margin: 10px 0;
             padding: 8px 12px; color: #b8bbc1;
             background: rgba(220,174,74,0.10);
             border-radius: 0 6px 6px 0;
             font-family: "Geist Mono", "Cascadia Mono", "Consolas", monospace;
             font-size: 13px; }
a.cite { color: #dcae4a; text-decoration: none; background: rgba(220,174,74,0.14);
         border: 1px solid rgba(220,174,74,0.40); border-radius: 5px;
         padding: 1px 5px; font-size: 11px; font-weight: 600;
         font-family: "Geist Mono", "Cascadia Mono", "Consolas", monospace; }
a.cite:hover { background: rgba(220,174,74,0.28); }
a.cite.active { color: #2a1f10; background: #dcae4a;
                border: 1px solid #dcae4a; }
h1,h2 { color: #ecedf0; font-size: 15px; font-weight: 600; margin: 12px 0 6px; }
h3 { color: #ecedf0; font-size: 13.5px; font-weight: 600; margin: 8px 0 4px; }
ul, ol { margin: 6px 0 10px 4px; padding-left: 20px; }
li { margin: 4px 0; line-height: 1.55; }
p { margin: 0 0 10px; }
"""
