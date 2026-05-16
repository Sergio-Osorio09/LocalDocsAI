"""Sources panel widget — citation cards for retrieved chunks."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from localdocsai.ui import icons as ic
from localdocsai.ui.chat_area import SourceRef


class SourceCardWidget(QWidget):
    """Single citation card in the sources panel."""

    activated = Signal(str)   # source id
    open_pdf_requested = Signal(str)  # source id
    hovered = Signal(int)     # citation number (on mouse enter)
    unhovered = Signal()      # (on mouse leave)

    def __init__(self, source: SourceRef, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._source = source
        self._active = False
        self.setObjectName("sourceCard")
        self.setProperty("active", "false")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # Header row: N chip + title
        header = QHBoxLayout()
        header.setSpacing(8)

        n_label = QLabel(f"[{self._source.n}]")
        n_label.setObjectName("sourceCardN")
        header.addWidget(n_label)

        title = QLabel(self._source.title)
        title.setObjectName("sourceCardTitle")
        title.setWordWrap(True)
        title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        header.addWidget(title, 1)

        layout.addLayout(header)

        # Metadata row
        meta_parts = [self._source.doc]
        if self._source.section:
            meta_parts.append(self._source.section)
        if self._source.page:
            meta_parts.append(f"p. {self._source.page}")
        meta = QLabel("  ·  ".join(meta_parts))
        meta.setObjectName("sourceCardMeta")
        meta.setWordWrap(True)
        layout.addWidget(meta)

        # Relevance score bar
        score_container = QWidget()
        score_layout = QHBoxLayout(score_container)
        score_layout.setContentsMargins(0, 0, 0, 0)
        score_layout.setSpacing(6)

        score_bg = QWidget()
        score_bg.setObjectName("scoreBar")
        score_bg.setFixedHeight(3)
        score_bg.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        fill_pct = int(self._source.score * 100)
        score_fill = QWidget(score_bg)
        score_fill.setObjectName("scoreBarFill")
        score_fill.setFixedHeight(3)
        score_fill.resize(int(score_bg.width() * self._source.score), 3)

        score_layout.addWidget(score_bg, 1)

        score_label = QLabel(f"{fill_pct}%")
        score_label.setObjectName("sourceCardMeta")
        score_label.setFixedWidth(30)
        score_layout.addWidget(score_label)
        layout.addWidget(score_container)

        # Snippet
        if self._source.snippet:
            snippet = QLabel(f'"{self._source.snippet[:160]}…"')
            snippet.setObjectName("sourceCardSnippet")
            snippet.setWordWrap(True)
            layout.addWidget(snippet)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        btn_row.addStretch(1)

        if self._source.doc.lower().endswith(".pdf") or "pdf" in self._source.doc.lower():
            pdf_btn = QPushButton("Abrir PDF")
            pdf_btn.setObjectName("topbarActionBtn")
            pdf_btn.setFixedHeight(26)
            pdf_btn.clicked.connect(lambda: self.open_pdf_requested.emit(self._source.id))
            btn_row.addWidget(pdf_btn)

        layout.addLayout(btn_row)

    def set_active(self, active: bool) -> None:
        self._active = active
        self.setProperty("active", "true" if active else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def enterEvent(self, event: object) -> None:
        self.hovered.emit(self._source.n)

    def leaveEvent(self, event: object) -> None:
        self.unhovered.emit()

    def mousePressEvent(self, event: object) -> None:
        self.activated.emit(self._source.id)


class SourcesPanelWidget(QWidget):
    """Right panel showing citation cards for the current conversation."""

    source_activated = Signal(str)  # source id
    open_pdf_requested = Signal(str)  # source id
    closed = Signal()
    citation_hovered = Signal(int)   # citation number
    citation_unhovered = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sourcesPanel")
        self._cards: dict[str, SourceCardWidget] = {}
        self._active_id: str | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setObjectName("sourcesPanelHeader")
        h = QHBoxLayout(header)
        h.setContentsMargins(16, 0, 12, 0)
        h.setSpacing(8)

        icon_label = QLabel()
        icon_label.setPixmap(ic.pixmap("sources", 15, "#8892a8"))
        h.addWidget(icon_label)

        title = QLabel("Fuentes")
        title.setObjectName("sourcesPanelTitle")
        h.addWidget(title, 1)

        close_btn = QPushButton()
        close_btn.setObjectName("closePanelBtn")
        close_btn.setFixedSize(28, 28)
        close_btn.setIcon(ic.icon("close", 14, "#555e78"))
        close_btn.setIconSize(QSize(14, 14))
        close_btn.clicked.connect(self.closed)
        h.addWidget(close_btn)

        layout.addWidget(header)

        # Scroll area for cards
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setObjectName("chatScrollArea")

        self._cards_widget = QWidget()
        self._cards_widget.setObjectName("chatContent")
        self._cards_layout = QVBoxLayout(self._cards_widget)
        self._cards_layout.setContentsMargins(0, 8, 0, 8)
        self._cards_layout.setSpacing(0)
        self._cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._empty_label = QLabel("Sin fuentes en esta conversación")
        self._empty_label.setObjectName("sourceCardMeta")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cards_layout.addWidget(self._empty_label)

        self._scroll.setWidget(self._cards_widget)
        layout.addWidget(self._scroll, 1)

    def load_sources(self, sources: list[SourceRef]) -> None:
        while self._cards_layout.count() > 0:
            item = self._cards_layout.takeAt(0)
            if item and item.widget():
                item.widget().setParent(None)

        self._cards = {}

        if not sources:
            self._cards_layout.addWidget(self._empty_label)
            self._empty_label.show()
            return

        self._empty_label.hide()
        for src in sources:
            card = SourceCardWidget(src)
            card.activated.connect(self._on_activated)
            card.open_pdf_requested.connect(self.open_pdf_requested)
            card.hovered.connect(self.citation_hovered)
            card.unhovered.connect(self.citation_unhovered)
            self._cards[src.id] = card
            self._cards_layout.addWidget(card)

        # Restore active
        if self._active_id and self._active_id in self._cards:
            self._cards[self._active_id].set_active(True)

    def set_active_source(self, source_id: str | None) -> None:
        for sid, card in self._cards.items():
            card.set_active(sid == source_id)
        self._active_id = source_id

        # Scroll to active card
        if source_id and source_id in self._cards:
            self._scroll.ensureWidgetVisible(self._cards[source_id])

    def _on_activated(self, source_id: str) -> None:
        self.set_active_source(source_id)
        self.source_activated.emit(source_id)
