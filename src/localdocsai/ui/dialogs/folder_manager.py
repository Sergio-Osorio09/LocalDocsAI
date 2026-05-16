"""Folder manager dialog — add/remove indexed folders and document groups."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from localdocsai.ui import icons as ic

if TYPE_CHECKING:
    from localdocsai.indexing.metadata_store import MetadataStore

_SUPPORTED = {".pdf", ".docx", ".xlsx"}

_EXT_LABEL = {".pdf": "PDF", ".docx": "Word", ".xlsx": "Excel"}


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


def _count_files(folder: Path) -> int:
    return sum(1 for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in _SUPPORTED)


def _list_supported(folder: Path) -> list[Path]:
    return sorted(
        (p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in _SUPPORTED),
        key=lambda p: p.name.lower(),
    )


def _list_unsupported(folder: Path) -> list[Path]:
    return sorted(
        (p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() not in _SUPPORTED),
        key=lambda p: p.name.lower(),
    )


def _fmt_size(n_bytes: int) -> str:
    if n_bytes >= 1_048_576:
        return f"{n_bytes / 1_048_576:.1f} MB"
    return f"{n_bytes // 1024} KB"


class FolderManagerDialog(QDialog):
    """Folder manager dialog — lists monitored folders and their file contents."""

    indexing_requested = Signal(list)  # list[Path]

    def __init__(
        self,
        folders: list[FolderEntry] | None = None,
        groups: list[GroupEntry] | None = None,
        metadata_store: MetadataStore | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._folders = folders or []
        self._groups = groups or []
        self._ms = metadata_store
        self.setWindowTitle("Gestor de carpetas")
        self.setMinimumSize(920, 580)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._setup_ui()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

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
        outer = QVBoxLayout(w)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(10)

        # Toolbar
        toolbar = QHBoxLayout()
        add_btn = QPushButton("  Añadir carpeta")
        add_btn.setIcon(ic.icon("plus", 14, "#0f1118"))
        add_btn.setIconSize(QSize(14, 14))
        add_btn.setObjectName("primaryBtn")
        add_btn.clicked.connect(self._add_folder)
        toolbar.addWidget(add_btn)
        toolbar.addStretch(1)
        outer.addLayout(toolbar)

        # Splitter: left = folder list | right = file tree
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("QSplitter::handle { background: #2a2f3d; }")

        # ── Left pane: folder list ──────────────────────────────────────
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 6, 0)
        ll.setSpacing(6)

        lbl_folders = QLabel("Carpetas")
        lbl_folders.setObjectName("sourceCardMeta")
        ll.addWidget(lbl_folders)

        self._folder_list = QListWidget()
        self._folder_list.setObjectName("folderListWidget")
        self._folder_list.setSpacing(2)
        self._folder_list.setMinimumWidth(220)
        self._folder_list.currentRowChanged.connect(self._on_folder_selected)
        ll.addWidget(self._folder_list, 1)

        for entry in self._folders:
            self._add_folder_item(entry)

        splitter.addWidget(left)

        # ── Right pane: file tree ───────────────────────────────────────
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(6, 0, 0, 0)
        rl.setSpacing(6)

        self._preview_label = QLabel("Selecciona una carpeta")
        self._preview_label.setObjectName("sourceCardMeta")
        rl.addWidget(self._preview_label)

        self._file_tree = QTreeWidget()
        self._file_tree.setObjectName("fileTreeWidget")
        self._file_tree.setColumnCount(4)
        self._file_tree.setHeaderLabels(["Nombre", "Tipo", "Tamaño", "Estado"])
        self._file_tree.setRootIsDecorated(False)
        self._file_tree.setSortingEnabled(True)
        self._file_tree.setAlternatingRowColors(True)
        self._file_tree.header().setStretchLastSection(False)
        self._file_tree.setColumnWidth(0, 340)
        self._file_tree.setColumnWidth(1, 60)
        self._file_tree.setColumnWidth(2, 75)
        self._file_tree.setColumnWidth(3, 110)
        rl.addWidget(self._file_tree, 1)

        splitter.addWidget(right)
        splitter.setSizes([260, 620])
        outer.addWidget(splitter, 1)

        # Status / progress label
        self._status_label = QLabel("")
        self._status_label.setObjectName("indexingStatusLabel")
        self._status_label.hide()
        outer.addWidget(self._status_label)

        # Action bar
        actions = QHBoxLayout()
        actions.addStretch(1)
        remove_btn = QPushButton("Eliminar")
        remove_btn.setObjectName("dangerBtn")
        remove_btn.clicked.connect(self._remove_folder)
        actions.addWidget(remove_btn)
        reindex_btn = QPushButton("Re-indexar")
        reindex_btn.clicked.connect(self._reindex_selected)
        actions.addWidget(reindex_btn)
        outer.addLayout(actions)

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
        h.setContentsMargins(16, 10, 16, 14)
        h.addStretch(1)
        close_btn = QPushButton("Cerrar")
        close_btn.clicked.connect(self.accept)
        h.addWidget(close_btn)
        return footer

    # ------------------------------------------------------------------
    # Folder list helpers
    # ------------------------------------------------------------------

    def _add_folder_item(self, entry: FolderEntry) -> None:
        if entry.indexing:
            status = "Indexando…"
        else:
            status = f"{entry.indexed_count}/{entry.file_count} indexados"
        item = QListWidgetItem()
        item.setText(f"{entry.path.name}\n{status}")
        item.setData(Qt.ItemDataRole.UserRole, str(entry.path))
        item.setToolTip(str(entry.path))
        self._folder_list.addItem(item)

    def _on_folder_selected(self, row: int) -> None:
        self._file_tree.clear()
        if row < 0 or row >= len(self._folders):
            self._preview_label.setText("Selecciona una carpeta")
            return

        entry = self._folders[row]
        supported = _list_supported(entry.path)
        unsupported = _list_unsupported(entry.path)

        indexed_paths: set[str] = set()
        if self._ms:
            indexed_paths = self._ms.get_indexed_paths_in_folder(entry.path)

        total = len(supported)
        indexed_n = sum(
            1 for f in supported if str(f.resolve()) in indexed_paths or str(f) in indexed_paths
        )
        self._preview_label.setText(
            f"{entry.path.name}  ·  {indexed_n}/{total} indexados"
            + (f"  ·  {len(unsupported)} archivos no soportados" if unsupported else "")
        )

        # Supported files
        for f in supported:
            is_indexed = str(f.resolve()) in indexed_paths or str(f) in indexed_paths
            ext = f.suffix.lower()
            status_text = "✓  Indexado" if is_indexed else "○  Pendiente"
            size_text = _fmt_size(f.stat().st_size)
            type_text = _EXT_LABEL.get(ext, ext.upper())

            item = QTreeWidgetItem([f.name, type_text, size_text, status_text])
            item.setToolTip(0, str(f))
            item.setTextAlignment(1, Qt.AlignmentFlag.AlignCenter)
            item.setTextAlignment(2, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            if is_indexed:
                item.setForeground(3, _color("#4ecb71"))
            else:
                item.setForeground(0, _color("#c8c8d0"))
                item.setForeground(3, _color("#d2af23"))

            self._file_tree.addTopLevelItem(item)

        # Unsupported files (grayed, at the bottom)
        for f in unsupported:
            size_text = _fmt_size(f.stat().st_size)
            ext = f.suffix.lstrip(".").upper() or "—"
            item = QTreeWidgetItem([f.name, ext, size_text, "—"])
            item.setToolTip(0, str(f))
            item.setTextAlignment(1, Qt.AlignmentFlag.AlignCenter)
            item.setTextAlignment(2, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            for col in range(4):
                item.setForeground(col, _color("#555e78"))
            self._file_tree.addTopLevelItem(item)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _add_folder(self) -> None:
        path_str = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de documentos")
        if not path_str:
            return
        folder = Path(path_str)
        file_count = _count_files(folder)
        indexed_count = self._ms.count_docs_in_folder(folder) if self._ms else 0
        entry = FolderEntry(path=folder, file_count=file_count, indexed_count=indexed_count)
        self._folders.append(entry)
        self._add_folder_item(entry)
        self._folder_list.setCurrentRow(len(self._folders) - 1)
        if indexed_count < file_count:
            self.indexing_requested.emit([entry.path])

    def _remove_folder(self) -> None:
        row = self._folder_list.currentRow()
        if row >= 0:
            self._folder_list.takeItem(row)
            if row < len(self._folders):
                self._folders.pop(row)
            self._file_tree.clear()
            self._preview_label.setText("Selecciona una carpeta")

    def _reindex_selected(self) -> None:
        row = self._folder_list.currentRow()
        if row < 0 or row >= len(self._folders):
            return
        entry = self._folders[row]
        item = self._folder_list.item(row)
        if item:
            item.setText(f"{entry.path.name}\nIndexando…")
        self._status_label.setText("Indexando documentos, por favor espera…")
        self._status_label.show()
        self.indexing_requested.emit([entry.path])

    # ------------------------------------------------------------------
    # Called from MainWindow to update progress
    # ------------------------------------------------------------------

    def set_indexing_progress(self, filename: str, current: int, total: int) -> None:
        if total > 0 and filename:
            self._status_label.setText(f"Indexando  {current + 1}/{total}:  {filename[:50]}")
            self._status_label.show()

    def set_indexing_done(self, folder: Path, indexed: int, skipped: int) -> None:
        self._status_label.hide()
        self._status_label.setText("")
        for i, entry in enumerate(self._folders):
            if entry.path == folder:
                entry.file_count = _count_files(folder)
                entry.indexed_count = self._ms.count_docs_in_folder(folder) if self._ms else skipped
                item = self._folder_list.item(i)
                if item:
                    item.setText(
                        f"{entry.path.name}\n{entry.indexed_count}/{entry.file_count} indexados"
                    )
                if self._folder_list.currentRow() == i:
                    self._on_folder_selected(i)
                break


# ------------------------------------------------------------------
# Utility
# ------------------------------------------------------------------


def _color(hex_str: str) -> object:
    from PySide6.QtGui import QColor

    return QColor(hex_str)
