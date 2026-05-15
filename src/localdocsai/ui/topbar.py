"""Topbar widget — chat title, scope selector, action buttons."""

from __future__ import annotations

from PySide6.QtCore import QSize, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from localdocsai.ui import icons as ic


class TopbarWidget(QWidget):
    """Top bar with chat title, scope selector, and panel toggles."""

    sources_toggled = Signal(bool)
    export_requested = Signal()
    scope_change_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("topbar")
        self._sources_open = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        h = QHBoxLayout(self)
        h.setContentsMargins(16, 0, 16, 0)
        h.setSpacing(8)

        self._title = QLabel("Nueva consulta")
        self._title.setObjectName("chatTitleLabel")
        h.addWidget(self._title, 1)

        self._scope_btn = QPushButton("Todas las fuentes")
        self._scope_btn.setObjectName("scopeBtn")
        self._scope_btn.setIcon(ic.icon("globe", 14, "#8892a8"))
        self._scope_btn.setIconSize(QSize(14, 14))
        self._scope_btn.clicked.connect(self.scope_change_requested)
        h.addWidget(self._scope_btn)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("background-color: #222840; max-width: 1px; margin: 12px 4px;")
        h.addWidget(sep)

        self._sources_btn = QPushButton("Fuentes")
        self._sources_btn.setObjectName("topbarActionBtn")
        self._sources_btn.setIcon(ic.icon("sources", 14, "#8892a8"))
        self._sources_btn.setIconSize(QSize(14, 14))
        self._sources_btn.clicked.connect(self._toggle_sources)
        h.addWidget(self._sources_btn)

        self._export_btn = QPushButton("Exportar")
        self._export_btn.setObjectName("topbarActionBtn")
        self._export_btn.setIcon(ic.icon("export", 14, "#8892a8"))
        self._export_btn.setIconSize(QSize(14, 14))
        self._export_btn.clicked.connect(self.export_requested)
        h.addWidget(self._export_btn)

    def set_title(self, title: str) -> None:
        self._title.setText(title)

    def set_scope_label(self, label: str) -> None:
        self._scope_btn.setText(label)

    def set_sources_open(self, open_: bool) -> None:
        self._sources_open = open_
        self._sources_btn.setProperty("active", "true" if open_ else "false")
        # force style refresh
        self._sources_btn.style().unpolish(self._sources_btn)
        self._sources_btn.style().polish(self._sources_btn)

    def _toggle_sources(self) -> None:
        self._sources_open = not self._sources_open
        self.set_sources_open(self._sources_open)
        self.sources_toggled.emit(self._sources_open)
