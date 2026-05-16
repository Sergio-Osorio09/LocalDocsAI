"""Chat area widget — message list with streaming support and empty state."""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QMouseEvent, QTextCursor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
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
    doc: str
    page: int
    section: str
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


# ---------------------------------------------------------------------------
# Message widgets
# ---------------------------------------------------------------------------


class UserMessageWidget(QWidget):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("userMessageWidget")
        h = QHBoxLayout(self)
        h.setContentsMargins(60, 4, 16, 4)
        h.setSpacing(0)
        h.addStretch(1)

        bubble = QLabel(text)
        bubble.setObjectName("userBubble")
        bubble.setWordWrap(True)
        bubble.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        bubble.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        bubble.setMaximumWidth(560)
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
        layout.setContentsMargins(16, 4, 60, 4)
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
        self._browser.document().documentLayout().documentSizeChanged.connect(
            self._resize_browser
        )
        self._set_text(text)
        layout.addWidget(self._browser)

        # Trace badge
        if trace:
            layout.addWidget(self._build_trace(trace))

    def _resize_browser(self) -> None:
        doc_height = int(self._browser.document().size().height()) + 8
        self._browser.setFixedHeight(max(60, doc_height))

    def update_text(self, text: str) -> None:
        self._set_text(text)

    def _set_text(self, text: str) -> None:
        html = _markdown_to_html(text)
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
        layout.setContentsMargins(16, 8, 60, 8)
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
    cite_clicked = Signal(int, list)  # (citation_n, sources_list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._messages: list[ChatMessage] = []
        self._current_sources: list[SourceRef] = []
        self._streaming_widget: StreamingWidget | None = None
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

        self._content = QWidget()
        self._content.setObjectName("chatContent")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(0)
        self._content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._empty_state = EmptyStateWidget()
        self._empty_state.suggestion_clicked.connect(self._on_suggestion)
        self._content_layout.addWidget(self._empty_state)

        self._scroll.setWidget(self._content)
        layout.addWidget(self._scroll, 1)

        # Composer
        self._composer = ComposerWidget()
        self._composer.message_submitted.connect(self.message_submitted)
        layout.addWidget(self._composer)

    def load_messages(self, messages: list[ChatMessage]) -> None:
        self._messages = messages
        self._current_sources = []
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


# ---------------------------------------------------------------------------
# QTextBrowser stylesheet
# ---------------------------------------------------------------------------

_MESSAGE_CSS = """
body { color: #e0e4f0; font-size: 14px; line-height: 1.75; margin: 0; padding: 0; }
strong, b { color: #f0f4ff; font-weight: 600; }
em, i { color: #c8ccda; }
code { font-family: "Consolas", "Fira Code", monospace; font-size: 12px;
       background: rgba(255,255,255,0.07); padding: 1px 5px; border-radius: 4px;
       color: #a8d8e8; }
pre { background: rgba(255,255,255,0.05); border-radius: 6px; padding: 10px 14px;
      margin: 8px 0; overflow-x: auto; }
pre code { background: none; padding: 0; }
blockquote { border-left: 3px solid #d2af23; margin: 10px 0; padding: 8px 14px;
             color: #e0e4f0; background: rgba(210,175,35,0.08);
             border-radius: 0 8px 8px 0; }
a.cite { color: #d2af23; text-decoration: none; background: rgba(210,175,35,0.15);
         border: 1px solid rgba(210,175,35,0.45); border-radius: 4px;
         padding: 1px 5px; font-size: 11px; font-weight: 700; font-family: monospace; }
a.cite:hover { background: rgba(210,175,35,0.30); }
h1,h2 { color: #e0e4f0; font-size: 15px; font-weight: 600; margin: 12px 0 6px; }
h3 { color: #e0e4f0; font-size: 14px; font-weight: 600; margin: 10px 0 4px; }
ul, ol { margin: 6px 0; padding-left: 22px; }
li { margin: 4px 0; line-height: 1.65; }
p { margin: 4px 0; }
"""
