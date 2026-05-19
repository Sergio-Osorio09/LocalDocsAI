"""Topbar widget — chat title, scope selector, action buttons."""

from __future__ import annotations

from PySide6.QtCore import QSize, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
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
        h.setContentsMargins(20, 8, 20, 8)
        h.setSpacing(10)

        # Title + meta column (left side)
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title_col.setContentsMargins(0, 0, 0, 0)

        self._title = QLabel("Nueva consulta")
        self._title.setObjectName("chatTitleLabel")
        title_col.addWidget(self._title)

        self._meta = QLabel("")
        self._meta.setObjectName("topbarMeta")
        title_col.addWidget(self._meta)

        title_widget = QWidget()
        title_widget.setLayout(title_col)
        title_widget.setObjectName("topbarTitleWrap")
        h.addWidget(title_widget, 1)

        # Scope selector pill ("alcance: Todas las fuentes")
        self._scope_btn = QPushButton("alcance:  Todas las fuentes")
        self._scope_btn.setObjectName("scopeBtn")
        self._scope_btn.setIcon(ic.icon("globe", 14, "#828690"))
        self._scope_btn.setIconSize(QSize(14, 14))
        self._scope_btn.clicked.connect(self.scope_change_requested)
        h.addWidget(self._scope_btn)

        sep = QFrame()
        sep.setObjectName("topbarSep")
        sep.setFrameShape(QFrame.Shape.VLine)
        h.addWidget(sep)

        self._export_btn = QPushButton("Exportar")
        self._export_btn.setObjectName("topbarActionBtn")
        self._export_btn.setIcon(ic.icon("export", 14, "#b8bbc1"))
        self._export_btn.setIconSize(QSize(14, 14))
        self._export_btn.clicked.connect(self.export_requested)
        h.addWidget(self._export_btn)

        self._sources_btn = QPushButton("Fuentes")
        self._sources_btn.setObjectName("topbarActionBtn")
        self._sources_btn.setCheckable(True)
        self._sources_btn.setIcon(ic.icon("sources", 14, "#b8bbc1"))
        self._sources_btn.setIconSize(QSize(14, 14))
        self._sources_btn.clicked.connect(self._toggle_sources)
        h.addWidget(self._sources_btn)

    def set_title(self, title: str) -> None:
        self._title.setText(title)

    def set_meta(self, text: str) -> None:
        """Set the subtitle meta line under the title (e.g. '3 mensajes')."""
        self._meta.setText(text)

    def set_scope_label(self, label: str) -> None:
        self._scope_btn.setText(f"alcance:  {label}")

    def set_sources_open(self, open_: bool) -> None:
        self._sources_open = open_
        self._sources_btn.setChecked(open_)

    def _toggle_sources(self) -> None:
        self._sources_open = self._sources_btn.isChecked()
        self.sources_toggled.emit(self._sources_open)
