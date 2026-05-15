"""Report editor dialog — review and edit auto-filled template fields before generating."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from localdocsai.reports.template import TemplateField
from localdocsai.ui import icons as ic


class ReportEditorDialog(QDialog):
    """Shows template fields pre-filled by the generator for user review/editing.

    On confirm emits ``generation_confirmed(output_path, fields)`` where *fields*
    contains the user-edited values.
    """

    generation_confirmed: Signal = Signal(str, list)  # (output_path, fields)

    def __init__(
        self,
        fields: list[TemplateField],
        template_path: Path,
        chat_title: str = "Conversación",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._fields = fields
        self._template_path = template_path
        self._output_path: str = ""
        self._editors: list[QTextEdit] = []

        self.setWindowTitle("Revisar y editar informe")
        self.setMinimumSize(580, 520)
        self.resize(640, 600)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._setup_ui(chat_title)

    def _setup_ui(self, chat_title: str) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())
        root.addWidget(self._build_body(), 1)
        root.addWidget(self._build_footer())

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("dialogHeader")
        h = QHBoxLayout(header)
        h.setContentsMargins(20, 0, 12, 0)
        h.setSpacing(8)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(ic.pixmap("export", 18, "#2cc8e4"))
        h.addWidget(icon_lbl)

        title = QLabel("Revisar campos del informe")
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
        outer = QWidget()
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        hint = QLabel(
            "Revisa los campos generados automáticamente. Edita cualquier campo antes de generar."
        )
        hint.setObjectName("sourceCardMeta")
        hint.setWordWrap(True)
        hint.setContentsMargins(20, 12, 20, 8)
        outer_layout.addWidget(hint)

        scroll = QScrollArea()
        scroll.setObjectName("chatScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        form_w = QWidget()
        form = QFormLayout(form_w)
        form.setContentsMargins(20, 12, 20, 12)
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self._editors = []
        for field in self._fields:
            editor = QTextEdit()
            editor.setObjectName("composerInput")
            editor.setAcceptRichText(False)
            editor.setPlainText(field.value)
            editor.setMinimumHeight(60)
            editor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            editor.document().contentsChanged.connect(lambda ed=editor: self._adjust_editor(ed))
            self._editors.append(editor)

            label_w = QLabel(field.label)
            label_w.setObjectName("sourceCardTitle")
            label_w.setFixedWidth(150)
            label_w.setWordWrap(True)
            form.addRow(label_w, editor)

        scroll.setWidget(form_w)
        outer_layout.addWidget(scroll, 1)

        return outer

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        h = QHBoxLayout(footer)
        h.setContentsMargins(16, 10, 16, 16)
        h.setSpacing(8)

        self._path_label = QLabel("Sin ruta de guardado")
        self._path_label.setObjectName("traceLabel")
        self._path_label.setWordWrap(True)
        h.addWidget(self._path_label, 1)

        browse_btn = QPushButton("Guardar como…")
        browse_btn.setObjectName("footerBtn")
        browse_btn.clicked.connect(self._choose_path)
        h.addWidget(browse_btn)

        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)
        h.addWidget(cancel_btn)

        self._generate_btn = QPushButton("Generar informe")
        self._generate_btn.setObjectName("primaryBtn")
        self._generate_btn.setEnabled(False)
        self._generate_btn.clicked.connect(self._on_generate)
        h.addWidget(self._generate_btn)

        return footer

    def _adjust_editor(self, editor: QTextEdit) -> None:
        doc_h = int(editor.document().size().height()) + 12
        editor.setFixedHeight(max(60, min(200, doc_h)))

    def _choose_path(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar informe",
            "informe.docx",
            "Word (*.docx)",
        )
        if path:
            self._output_path = path
            self._path_label.setText(path)
            self._generate_btn.setEnabled(True)

    def _on_generate(self) -> None:
        if not self._output_path:
            return
        filled_fields = []
        for field, editor in zip(self._fields, self._editors, strict=True):
            filled_fields.append(
                field.__class__(
                    paragraph_idx=field.paragraph_idx,
                    pattern=field.pattern,
                    context=field.context,
                    label=field.label,
                    semantic_type=field.semantic_type,
                    value=editor.toPlainText(),
                )
            )
        self.generation_confirmed.emit(self._output_path, filled_fields)
        self.accept()
