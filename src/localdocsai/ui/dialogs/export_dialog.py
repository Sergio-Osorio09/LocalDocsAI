"""Export dialog — format selection and template-based report generation."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from localdocsai.ui import icons as ic

_DEFAULT_TEMPLATE = (
    Path(__file__).parent.parent.parent.parent.parent
    / "resources"
    / "report_templates"
    / "nota_tecnica.docx"
)


class ExportDialog(QDialog):
    """Format selector + template picker for conversation export.

    For .docx exports, emits ``template_export_requested`` so the caller can
    open the ReportEditorDialog with auto-filled fields.
    For .pdf exports, emits ``export_requested`` with format and output path directly.
    """

    export_requested: Signal = Signal(str, str)  # (format, output_path) — pdf only
    template_export_requested: Signal = Signal(str, str)  # (template_path, scope)

    def __init__(
        self,
        chat_title: str = "Conversación",
        custom_template: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._chat_title = chat_title
        self._custom_template_path = custom_template
        self.setWindowTitle("Exportar informe")
        self.setMinimumSize(460, 400)
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
        h.setSpacing(8)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(ic.pixmap("export", 18, "#2cc8e4"))
        h.addWidget(icon_lbl)

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

        # Conversation title
        conv_lbl = QLabel(f"Conversación: {self._chat_title}")
        conv_lbl.setObjectName("sourceCardTitle")
        layout.addWidget(conv_lbl)

        # Format
        fmt_lbl = QLabel("Formato:")
        fmt_lbl.setObjectName("sourceCardMeta")
        layout.addWidget(fmt_lbl)

        btn_group = QButtonGroup(self)
        self._fmt_docx = QRadioButton("Word (.docx)  — con plantilla editable")
        self._fmt_pdf = QRadioButton("PDF (.pdf)  — solo lectura")
        self._fmt_docx.setChecked(True)
        btn_group.addButton(self._fmt_docx)
        btn_group.addButton(self._fmt_pdf)
        layout.addWidget(self._fmt_docx)
        layout.addWidget(self._fmt_pdf)
        self._fmt_docx.toggled.connect(self._on_format_toggled)

        # Template section (only for docx)
        self._template_section = QWidget()
        t_layout = QVBoxLayout(self._template_section)
        t_layout.setContentsMargins(0, 0, 0, 0)
        t_layout.setSpacing(6)

        tpl_lbl = QLabel("Plantilla:")
        tpl_lbl.setObjectName("sourceCardMeta")
        t_layout.addWidget(tpl_lbl)

        self._tpl_combo = QComboBox()
        self._tpl_combo.addItem("Nota Técnica (predeterminada)", str(_DEFAULT_TEMPLATE))
        if self._custom_template_path:
            self._tpl_combo.addItem(
                f"Personalizada: {Path(self._custom_template_path).name}",
                self._custom_template_path,
            )
        self._tpl_combo.addItem("Otra plantilla…", "__browse__")
        self._tpl_combo.currentIndexChanged.connect(self._on_template_combo_changed)
        t_layout.addWidget(self._tpl_combo)

        # Path display for custom templates
        self._tpl_path_edit = QLineEdit()
        self._tpl_path_edit.setObjectName("composerInput")
        self._tpl_path_edit.setReadOnly(True)
        self._tpl_path_edit.setPlaceholderText("Seleccionar archivo .docx…")
        self._tpl_path_edit.setVisible(False)
        t_layout.addWidget(self._tpl_path_edit)

        layout.addWidget(self._template_section)

        # Scope
        scope_lbl = QLabel("Incluir mensajes:")
        scope_lbl.setObjectName("sourceCardMeta")
        layout.addWidget(scope_lbl)

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
        h.setSpacing(8)
        h.addStretch(1)

        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)
        h.addWidget(cancel_btn)

        self._action_btn = QPushButton("Continuar")
        self._action_btn.setObjectName("primaryBtn")
        self._action_btn.clicked.connect(self._on_action)
        h.addWidget(self._action_btn)

        return footer

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_format_toggled(self, docx_checked: bool) -> None:
        self._template_section.setVisible(docx_checked)
        self._action_btn.setText("Continuar" if docx_checked else "Exportar")

    def _on_template_combo_changed(self, index: int) -> None:
        data = self._tpl_combo.itemData(index)
        if data == "__browse__":
            path, _ = QFileDialog.getOpenFileName(
                self, "Seleccionar plantilla", "", "Word (*.docx)"
            )
            if path:
                self._tpl_path_edit.setText(path)
                self._tpl_path_edit.setVisible(True)
                # Replace the browse entry with the selected path
                self._tpl_combo.setItemText(index, f"Otra: {Path(path).name}")
                self._tpl_combo.setItemData(index, path)
            else:
                self._tpl_combo.setCurrentIndex(0)
        else:
            self._tpl_path_edit.setVisible(False)

    def _on_action(self) -> None:
        if self._fmt_docx.isChecked():
            template_path = self._tpl_combo.currentData() or str(_DEFAULT_TEMPLATE)
            scope = self._scope_combo.currentText()
            self.template_export_requested.emit(template_path, scope)
            self.accept()
        else:
            # PDF: direct save dialog
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Guardar informe PDF",
                f"{self._chat_title}.pdf",
                "PDF (*.pdf)",
            )
            if path:
                self.export_requested.emit("pdf", path)
                self.accept()
