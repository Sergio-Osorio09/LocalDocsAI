"""PDF viewer dialog — renders pages via PyMuPDF into a scroll area."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from localdocsai.ui import icons as ic


class PdfViewerDialog(QDialog):
    """Minimal PDF viewer: renders one page at a time via PyMuPDF."""

    def __init__(
        self,
        path: Path,
        initial_page: int = 1,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._path = path
        self._doc: object | None = None
        self._total_pages = 1
        self._current_page = max(1, initial_page)
        self.setWindowTitle(f"PDF — {path.name}")
        self.setMinimumSize(700, 860)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._setup_ui()
        self._load_document()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_header())

        # Page display
        scroll = QScrollArea()
        scroll.setObjectName("chatScrollArea")
        scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll.setWidgetResizable(False)

        self._page_label = QLabel()
        self._page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._page_label.setObjectName("chatContent")
        scroll.setWidget(self._page_label)
        layout.addWidget(scroll, 1)

        layout.addWidget(self._build_toolbar())

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("dialogHeader")
        h = QHBoxLayout(header)
        h.setContentsMargins(20, 0, 12, 0)

        icon_label = QLabel()
        icon_label.setPixmap(ic.pixmap("file-doc", 18, "#2cc8e4"))
        h.addWidget(icon_label)

        self._title_label = QLabel(self._path.name)
        self._title_label.setObjectName("dialogTitle")
        h.addWidget(self._title_label, 1)

        close_btn = QPushButton()
        close_btn.setObjectName("closeDialogBtn")
        close_btn.setFixedSize(30, 30)
        close_btn.setIcon(ic.icon("close", 14, "#555e78"))
        close_btn.setIconSize(QSize(14, 14))
        close_btn.clicked.connect(self.reject)
        h.addWidget(close_btn)

        return header

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("sidebarFooter")
        h = QHBoxLayout(bar)
        h.setContentsMargins(12, 8, 12, 8)
        h.setSpacing(8)

        prev_btn = QPushButton()
        prev_btn.setObjectName("topbarActionBtn")
        prev_btn.setIcon(ic.icon("chevron-left", 14, "#8892a8"))
        prev_btn.setIconSize(QSize(14, 14))
        prev_btn.setFixedSize(32, 32)
        prev_btn.setToolTip("Página anterior")
        prev_btn.clicked.connect(self._prev_page)
        h.addWidget(prev_btn)

        self._page_spin = QSpinBox()
        self._page_spin.setRange(1, 9999)
        self._page_spin.setValue(self._current_page)
        self._page_spin.setFixedWidth(64)
        self._page_spin.editingFinished.connect(lambda: self._go_to_page(self._page_spin.value()))
        h.addWidget(self._page_spin)

        self._total_label = QLabel("/ 1")
        self._total_label.setObjectName("sourceCardMeta")
        h.addWidget(self._total_label)

        h.addStretch(1)

        next_btn = QPushButton()
        next_btn.setObjectName("topbarActionBtn")
        next_btn.setIcon(ic.icon("chevron-right", 14, "#8892a8"))
        next_btn.setIconSize(QSize(14, 14))
        next_btn.setFixedSize(32, 32)
        next_btn.setToolTip("Página siguiente")
        next_btn.clicked.connect(self._next_page)
        h.addWidget(next_btn)

        return bar

    def _load_document(self) -> None:
        try:
            import fitz  # PyMuPDF

            self._doc = fitz.open(str(self._path))
            self._total_pages = self._doc.page_count  # type: ignore[union-attr]
            self._total_label.setText(f"/ {self._total_pages}")
            self._page_spin.setMaximum(self._total_pages)
            self._render_page(self._current_page)
        except Exception as exc:
            self._page_label.setText(f"No se pudo abrir el PDF:\n{exc}")

    def _render_page(self, page_num: int) -> None:
        if not self._doc:
            return
        try:
            import fitz

            page = self._doc[page_num - 1]  # type: ignore[index]
            mat = fitz.Matrix(1.5, 1.5)
            clip = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
            img = QImage(
                clip.samples,
                clip.width,
                clip.height,
                clip.stride,
                QImage.Format.Format_RGB888,
            )
            self._page_label.setPixmap(QPixmap.fromImage(img))
            self._page_label.resize(clip.width, clip.height)
        except Exception as exc:
            self._page_label.setText(f"Error al renderizar p.{page_num}:\n{exc}")

    def _go_to_page(self, page: int) -> None:
        self._current_page = max(1, min(page, self._total_pages))
        self._page_spin.setValue(self._current_page)
        self._render_page(self._current_page)

    def _prev_page(self) -> None:
        self._go_to_page(self._current_page - 1)

    def _next_page(self) -> None:
        self._go_to_page(self._current_page + 1)

    def closeEvent(self, event: object) -> None:
        if self._doc:
            self._doc.close()  # type: ignore[union-attr]
        super().closeEvent(event)  # type: ignore[arg-type]
