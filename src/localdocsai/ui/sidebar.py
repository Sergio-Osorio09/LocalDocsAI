"""Sidebar widget — collapsible navigation panel."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import QPropertyAnimation, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from localdocsai.ui import icons as ic

SIDEBAR_EXPANDED = 280
SIDEBAR_COLLAPSED = 56


@dataclass
class ChatEntry:
    id: str
    title: str
    date: str
    pinned: bool = False
    message_count: int = 0


class SidebarWidget(QWidget):
    """Left sidebar: logo, new-chat button, chat list, footer actions."""

    chat_selected = Signal(str)
    new_chat_requested = Signal()
    folders_requested = Signal()
    settings_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self._collapsed = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_header())
        layout.addWidget(self._build_chat_list(), 1)
        layout.addWidget(self._build_footer())

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("sidebarHeader")
        h = QHBoxLayout(header)
        h.setContentsMargins(12, 10, 12, 10)
        h.setSpacing(8)

        self._logo = QLabel("LocalDocsAI")
        self._logo.setObjectName("logoLabel")
        h.addWidget(self._logo, 1)

        self._new_chat_btn = QPushButton("Nueva")
        self._new_chat_btn.setObjectName("newChatBtn")
        self._new_chat_btn.setIcon(ic.icon("plus", 14, "#2cc8e4"))
        self._new_chat_btn.setIconSize(QSize(14, 14))
        self._new_chat_btn.clicked.connect(self.new_chat_requested)
        h.addWidget(self._new_chat_btn)

        self._collapse_btn = QPushButton()
        self._collapse_btn.setObjectName("collapseBtn")
        self._collapse_btn.setFixedSize(28, 28)
        self._collapse_btn.setIcon(ic.icon("sidebar-collapse", 16, "#555e78"))
        self._collapse_btn.setIconSize(QSize(16, 16))
        self._collapse_btn.setToolTip("Colapsar barra lateral")
        self._collapse_btn.clicked.connect(self.toggle_collapse)
        h.addWidget(self._collapse_btn)

        return header

    def _build_chat_list(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(0)

        self._section_label = QLabel("CONVERSACIONES")
        self._section_label.setObjectName("sectionLabel")
        layout.addWidget(self._section_label)

        self._chat_list = QListWidget()
        self._chat_list.setObjectName("chatListWidget")
        self._chat_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._chat_list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._chat_list)

        return container

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        footer.setObjectName("sidebarFooter")
        layout = QVBoxLayout(footer)
        layout.setContentsMargins(6, 6, 6, 8)
        layout.setSpacing(1)

        self._folders_btn = self._make_footer_btn("Carpetas", "folders", self.folders_requested)
        layout.addWidget(self._folders_btn)

        self._settings_btn = self._make_footer_btn(
            "Configuración", "settings", self.settings_requested
        )
        layout.addWidget(self._settings_btn)

        self._model_status = QLabel("Modelo: sin cargar")
        self._model_status.setObjectName("modelStatusLabel")
        layout.addWidget(self._model_status)

        return footer

    def _make_footer_btn(self, label: str, icon_name: str, slot: object) -> QPushButton:
        """Build a footer button with icon on the left and text."""
        btn = QPushButton()
        btn.setObjectName("footerBtn")
        btn.setIcon(ic.icon(icon_name, 15, "#8892a8"))
        btn.setIconSize(QSize(15, 15))
        btn.setText(label)
        btn.setStyleSheet("text-align: left; padding-left: 10px;")
        btn.clicked.connect(slot)  # type: ignore[arg-type]
        return btn

    def load_chats(self, chats: Sequence[ChatEntry]) -> None:
        self._chat_list.clear()
        for chat in chats:
            item = QListWidgetItem(chat.title)
            item.setData(Qt.ItemDataRole.UserRole, chat.id)
            item.setToolTip(chat.title)
            self._chat_list.addItem(item)

    def set_active_chat(self, chat_id: str) -> None:
        for i in range(self._chat_list.count()):
            item = self._chat_list.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == chat_id:
                self._chat_list.setCurrentItem(item)
                break

    def set_model_status(self, status: str) -> None:
        self._model_status.setText(status)

    def toggle_collapse(self) -> None:
        self._collapsed = not self._collapsed
        target_w = SIDEBAR_COLLAPSED if self._collapsed else SIDEBAR_EXPANDED

        anim = QPropertyAnimation(self, b"minimumWidth", self)
        anim.setDuration(180)
        anim.setStartValue(self.width())
        anim.setEndValue(target_w)
        anim.start()

        anim2 = QPropertyAnimation(self, b"maximumWidth", self)
        anim2.setDuration(180)
        anim2.setStartValue(self.width())
        anim2.setEndValue(target_w)
        anim2.start()

        self._logo.setVisible(not self._collapsed)
        self._new_chat_btn.setVisible(not self._collapsed)
        self._section_label.setVisible(not self._collapsed)
        self._folders_btn.setVisible(not self._collapsed)
        self._settings_btn.setVisible(not self._collapsed)
        self._model_status.setVisible(not self._collapsed)
        self._collapse_btn.setIcon(
            ic.icon("sidebar", 16, "#555e78")
            if self._collapsed
            else ic.icon("sidebar-collapse", 16, "#555e78")
        )

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        chat_id = item.data(Qt.ItemDataRole.UserRole)
        if chat_id:
            self.chat_selected.emit(str(chat_id))

    @property
    def is_collapsed(self) -> bool:
        return self._collapsed
