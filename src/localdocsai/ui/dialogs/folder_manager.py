"""Folder manager dialog — add/remove indexed folders and document groups."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from localdocsai.ui import icons as ic


@dataclass
class FolderEntry:
    path: Path
    file_count: int
    indexed_count: int
    indexing: bool = False


@dataclass
class GroupEntry:
    id: str
    name: str
    color: str
    doc_count: int


class FolderManagerDialog(QDialog):
    """3-tab dialog: Folders | Groups | Statistics."""

    indexing_requested = Signal(list)  # list[Path]

    def __init__(
        self,
        folders: list[FolderEntry] | None = None,
        groups: list[GroupEntry] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._folders = folders or []
        self._groups = groups or []
        self.setWindowTitle("Gestor de carpetas")
        self.setMinimumSize(640, 480)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_header())

        tabs = QTabWidget()
        tabs.addTab(self._build_folders_tab(), "Carpetas")
        tabs.addTab(self._build_groups_tab(), "Grupos")
        tabs.addTab(self._build_stats_tab(), "Estadísticas")
        layout.addWidget(tabs, 1)

        layout.addWidget(self._build_footer())

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("dialogHeader")
        h = QHBoxLayout(header)
        h.setContentsMargins(20, 0, 12, 0)

        icon_label = QLabel()
        icon_label.setPixmap(ic.pixmap("folders", 18, "#2cc8e4"))
        h.addWidget(icon_label)

        title = QLabel("Gestor de carpetas")
        title.setObjectName("dialogTitle")
        h.addWidget(title, 1)

        close_btn = QPushButton()
        close_btn.setObjectName("closeDialogBtn")
        close_btn.setFixedSize(30, 30)
        close_btn.setIcon(ic.icon("close", 14, "#555e78"))
        close_btn.setIconSize(QSize(14, 14))
        close_btn.clicked.connect(self.reject)
        h.addWidget(close_btn)

        return header

    def _build_folders_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Toolbar
        toolbar = QHBoxLayout()
        add_btn = QPushButton("Añadir carpeta")
        add_btn.setIcon(ic.icon("plus", 14, "#0f1118"))
        add_btn.setIconSize(QSize(14, 14))
        add_btn.setObjectName("primaryBtn")
        add_btn.clicked.connect(self._add_folder)
        toolbar.addWidget(add_btn)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        # Folder list
        self._folder_list = QListWidget()
        self._folder_list.setObjectName("chatListWidget")
        self._folder_list.setSpacing(2)
        layout.addWidget(self._folder_list, 1)

        for entry in self._folders:
            self._add_folder_item(entry)

        # Actions
        actions = QHBoxLayout()
        actions.addStretch(1)
        remove_btn = QPushButton("Eliminar")
        remove_btn.setObjectName("dangerBtn")
        remove_btn.clicked.connect(self._remove_folder)
        actions.addWidget(remove_btn)
        reindex_btn = QPushButton("Re-indexar")
        reindex_btn.clicked.connect(self._reindex_selected)
        actions.addWidget(reindex_btn)
        layout.addLayout(actions)

        return w

    def _build_groups_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QLabel("Grupos de documentos")
        header.setObjectName("sourcesPanelTitle")
        layout.addWidget(header)

        self._group_list = QListWidget()
        self._group_list.setObjectName("chatListWidget")
        layout.addWidget(self._group_list, 1)

        for g in self._groups:
            item = QListWidgetItem(f"{g.name}  ({g.doc_count} docs)")
            self._group_list.addItem(item)

        if not self._groups:
            self._group_list.addItem("Sin grupos definidos")

        return w

    def _build_stats_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        total_files = sum(f.file_count for f in self._folders)
        total_indexed = sum(f.indexed_count for f in self._folders)

        for label, value in [
            ("Carpetas monitoreadas", str(len(self._folders))),
            ("Archivos totales", str(total_files)),
            ("Archivos indexados", str(total_indexed)),
            ("Grupos definidos", str(len(self._groups))),
        ]:
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setObjectName("sourceCardMeta")
            row.addWidget(lbl)
            row.addStretch(1)
            val = QLabel(value)
            val.setObjectName("sourceCardTitle")
            row.addWidget(val)
            layout.addLayout(row)

        layout.addStretch(1)
        return w

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        h = QHBoxLayout(footer)
        h.setContentsMargins(16, 10, 16, 16)
        h.addStretch(1)
        close_btn = QPushButton("Cerrar")
        close_btn.clicked.connect(self.accept)
        h.addWidget(close_btn)
        return footer

    def _add_folder_item(self, entry: FolderEntry) -> None:
        status = (
            "Indexando…"
            if entry.indexing
            else f"{entry.indexed_count}/{entry.file_count} indexados"
        )
        item = QListWidgetItem(f"{entry.path}  —  {status}")
        item.setData(Qt.ItemDataRole.UserRole, str(entry.path))
        self._folder_list.addItem(item)

    def _add_folder(self) -> None:
        path_str = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de documentos")
        if path_str:
            entry = FolderEntry(
                path=Path(path_str),
                file_count=0,
                indexed_count=0,
            )
            self._folders.append(entry)
            self._add_folder_item(entry)
            self.indexing_requested.emit([entry.path])

    def _remove_folder(self) -> None:
        row = self._folder_list.currentRow()
        if row >= 0:
            self._folder_list.takeItem(row)
            if row < len(self._folders):
                self._folders.pop(row)

    def _reindex_selected(self) -> None:
        row = self._folder_list.currentRow()
        if 0 <= row < len(self._folders):
            self.indexing_requested.emit([self._folders[row].path])
