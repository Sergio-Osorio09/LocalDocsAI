"""Export dialog — generate conversation reports in docx or pdf."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from localdocsai.ui import icons as ic


class ExportDialog(QDialog):
    """Format selector + output path for conversation export."""

    export_requested = Signal(str, str)  # (format, output_path)

    def __init__(
        self,
        chat_title: str = "Conversación",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._chat_title = chat_title
        self.setWindowTitle("Exportar informe")
        self.setMinimumSize(440, 320)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_header())
        layout.addWidget(self._build_body(), 1)
        layout.addWidget(self._build_footer())

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("dialogHeader")
        h = QHBoxLayout(header)
        h.setContentsMargins(20, 0, 12, 0)

        icon_label = QLabel()
        icon_label.setPixmap(ic.pixmap("export", 18, "#2cc8e4"))
        h.addWidget(icon_label)

        title = QLabel("Exportar informe")
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

    def _build_body(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(16)

        # Chat title
        title_label = QLabel(f"Conversación: {self._chat_title}")
        title_label.setObjectName("sourceCardTitle")
        layout.addWidget(title_label)

        # Format selection
        fmt_label = QLabel("Formato de exportación:")
        fmt_label.setObjectName("sourceCardMeta")
        layout.addWidget(fmt_label)

        btn_group = QButtonGroup(self)
        self._fmt_docx = QRadioButton("Word (.docx)  — con estilos de tabla")
        self._fmt_pdf = QRadioButton("PDF (.pdf)  — solo lectura")
        self._fmt_docx.setChecked(True)
        btn_group.addButton(self._fmt_docx)
        btn_group.addButton(self._fmt_pdf)
        layout.addWidget(self._fmt_docx)
        layout.addWidget(self._fmt_pdf)

        # Scope
        scope_label = QLabel("Incluir mensajes:")
        scope_label.setObjectName("sourceCardMeta")
        layout.addWidget(scope_label)

        self._scope_combo = QComboBox()
        self._scope_combo.addItems(
            [
                "Toda la conversación",
                "Últimos 5 mensajes",
                "Últimos 10 mensajes",
                "Solo respuestas del asistente",
            ]
        )
        layout.addWidget(self._scope_combo)

        layout.addStretch(1)
        return w

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        h = QHBoxLayout(footer)
        h.setContentsMargins(16, 10, 16, 16)
        h.addStretch(1)
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)
        h.addWidget(cancel_btn)
        export_btn = QPushButton("Exportar")
        export_btn.setObjectName("primaryBtn")
        export_btn.clicked.connect(self._on_export)
        h.addWidget(export_btn)
        return footer

    def _on_export(self) -> None:
        fmt = "docx" if self._fmt_docx.isChecked() else "pdf"
        ext = f"*.{fmt}"
        default_name = f"{self._chat_title}.{fmt}"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar informe",
            default_name,
            f"Documentos ({ext})",
        )
        if path:
            self.export_requested.emit(fmt, path)
            self.accept()
