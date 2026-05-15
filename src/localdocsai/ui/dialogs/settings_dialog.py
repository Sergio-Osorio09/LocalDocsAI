"""Settings dialog — 4-tab configuration UI backed by Settings pydantic model."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from localdocsai.ui import icons as ic


class SettingsDialog(QDialog):
    """4-tab settings dialog: Model | Retrieval | Interface | Advanced."""

    settings_saved = Signal(dict)

    def __init__(self, settings: object | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self.setWindowTitle("Configuración")
        self.setMinimumSize(560, 480)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._setup_ui()
        if settings:
            self._load_settings(settings)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_header())

        tabs = QTabWidget()
        tabs.addTab(self._build_model_tab(), "Modelo")
        tabs.addTab(self._build_retrieval_tab(), "Recuperación")
        tabs.addTab(self._build_ui_tab(), "Interfaz")
        tabs.addTab(self._build_advanced_tab(), "Avanzado")
        layout.addWidget(tabs, 1)

        layout.addWidget(self._build_footer())

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("dialogHeader")
        h = QHBoxLayout(header)
        h.setContentsMargins(20, 0, 12, 0)

        icon_label = QLabel()
        icon_label.setPixmap(ic.pixmap("settings", 18, "#2cc8e4"))
        h.addWidget(icon_label)

        title = QLabel("Configuración")
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

    def _build_model_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(20, 16, 20, 16)
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._llm_combo = QComboBox()
        self._llm_combo.addItems(
            [
                "qwen2.5-14b-instruct-q4_k_m",
                "qwen2.5-7b-instruct-q4_k_m",
                "llama-3.1-8b-instruct-q4_k_m",
            ]
        )
        form.addRow("Modelo LLM:", self._llm_combo)

        self._context_spin = QSpinBox()
        self._context_spin.setRange(1024, 131072)
        self._context_spin.setSingleStep(1024)
        self._context_spin.setValue(8192)
        self._context_spin.setSuffix(" tokens")
        form.addRow("Ventana de contexto:", self._context_spin)

        self._max_tokens_spin = QSpinBox()
        self._max_tokens_spin.setRange(128, 8192)
        self._max_tokens_spin.setSingleStep(128)
        self._max_tokens_spin.setValue(1024)
        self._max_tokens_spin.setSuffix(" tokens")
        form.addRow("Tokens máximos:", self._max_tokens_spin)

        self._gpu_layers_spin = QSpinBox()
        self._gpu_layers_spin.setRange(0, 100)
        self._gpu_layers_spin.setValue(0)
        self._gpu_layers_spin.setSpecialValueText("0 (solo CPU)")
        form.addRow("Capas GPU:", self._gpu_layers_spin)

        return w

    def _build_retrieval_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(20, 16, 20, 16)
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._top_k_spin = QSpinBox()
        self._top_k_spin.setRange(1, 50)
        self._top_k_spin.setValue(10)
        form.addRow("Chunks recuperados (top-k):", self._top_k_spin)

        self._rerank_check = QCheckBox("Activar re-ranking")
        form.addRow("Re-ranking:", self._rerank_check)

        self._min_sim_spin = QDoubleSpinBox()
        self._min_sim_spin.setRange(0.0, 1.0)
        self._min_sim_spin.setSingleStep(0.05)
        self._min_sim_spin.setDecimals(2)
        self._min_sim_spin.setValue(0.5)
        form.addRow("Similitud mínima:", self._min_sim_spin)

        return w

    def _build_ui_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(20, 16, 20, 16)
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._lang_combo = QComboBox()
        self._lang_combo.addItems(["Español (es)", "English (en)"])
        form.addRow("Idioma de la interfaz:", self._lang_combo)

        self._theme_combo = QComboBox()
        self._theme_combo.addItems(["Oscuro", "Claro", "Personalizado"])
        form.addRow("Tema:", self._theme_combo)

        self._primary_color = QLineEdit("#2cc8e4")
        form.addRow("Color primario:", self._primary_color)

        self._accent_color = QLineEdit("#d2af23")
        form.addRow("Color de citas:", self._accent_color)

        return w

    def _build_advanced_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(20, 16, 20, 16)
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._show_trace_check = QCheckBox("Mostrar trazabilidad del pipeline")
        self._show_trace_check.setChecked(True)
        form.addRow("Pipeline trace:", self._show_trace_check)

        self._chunk_size_spin = QSpinBox()
        self._chunk_size_spin.setRange(200, 4000)
        self._chunk_size_spin.setSingleStep(100)
        self._chunk_size_spin.setValue(800)
        self._chunk_size_spin.setSuffix(" tokens")
        form.addRow("Tamaño de chunk:", self._chunk_size_spin)

        self._chunk_overlap_spin = QSpinBox()
        self._chunk_overlap_spin.setRange(0, 500)
        self._chunk_overlap_spin.setSingleStep(25)
        self._chunk_overlap_spin.setValue(100)
        self._chunk_overlap_spin.setSuffix(" tokens")
        form.addRow("Solapamiento:", self._chunk_overlap_spin)

        return w

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        h = QHBoxLayout(footer)
        h.setContentsMargins(16, 10, 16, 16)
        h.addStretch(1)
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)
        h.addWidget(cancel_btn)
        save_btn = QPushButton("Guardar")
        save_btn.setObjectName("primaryBtn")
        save_btn.clicked.connect(self._save)
        h.addWidget(save_btn)
        return footer

    def _load_settings(self, settings: object) -> None:
        if hasattr(settings, "model"):
            m = settings.model  # type: ignore[union-attr]
            idx = self._llm_combo.findText(m.llm, Qt.MatchFlag.MatchContains)
            if idx >= 0:
                self._llm_combo.setCurrentIndex(idx)
            self._context_spin.setValue(m.context_window)
            self._max_tokens_spin.setValue(m.max_tokens)
            self._gpu_layers_spin.setValue(m.n_gpu_layers)
        if hasattr(settings, "retrieval"):
            r = settings.retrieval  # type: ignore[union-attr]
            self._top_k_spin.setValue(r.top_k)
            self._rerank_check.setChecked(r.rerank)
            self._min_sim_spin.setValue(r.min_similarity)

    def _save(self) -> None:
        data = {
            "model": {
                "llm": self._llm_combo.currentText(),
                "context_window": self._context_spin.value(),
                "max_tokens": self._max_tokens_spin.value(),
                "n_gpu_layers": self._gpu_layers_spin.value(),
            },
            "retrieval": {
                "top_k": self._top_k_spin.value(),
                "rerank": self._rerank_check.isChecked(),
                "min_similarity": self._min_sim_spin.value(),
            },
        }
        self.settings_saved.emit(data)
        self.accept()
