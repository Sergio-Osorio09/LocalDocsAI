"""Composer widget — message input with send button and scope chip."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from localdocsai.ui import icons as ic


class _ComposerInput(QTextEdit):
    """Multi-line text input that submits on Enter (Shift+Enter for newline)."""

    submit_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("composerInput")
        self.setPlaceholderText("Haz una pregunta sobre tus documentos…")
        self.setAcceptRichText(False)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFixedHeight(40)
        self.document().contentsChanged.connect(self._adjust_height)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # type: ignore[override]
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (
            event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            self.submit_requested.emit()
        else:
            super().keyPressEvent(event)

    def _adjust_height(self) -> None:
        doc_height = int(self.document().size().height()) + 12
        clamped = max(40, min(140, doc_height))
        self.setFixedHeight(clamped)


class ComposerWidget(QWidget):
    """Bottom input bar with scope chip, text input, and send button."""

    message_submitted = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("composerWidget")
        self._setup_ui()

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 8, 16, 12)
        outer.setSpacing(4)

        # Scope chip row (compact)
        chip_row = QWidget()
        chip_layout = QHBoxLayout(chip_row)
        chip_layout.setContentsMargins(2, 0, 2, 0)
        chip_layout.setSpacing(6)

        self._scope_chip = QLabel("Todas las fuentes")
        self._scope_chip.setObjectName("scopeChip")
        chip_layout.addWidget(self._scope_chip)
        chip_layout.addStretch(1)
        outer.addWidget(chip_row)

        # Inner bordered box — fixed to content height
        inner = QWidget()
        inner.setObjectName("composerInner")
        inner_layout = QHBoxLayout(inner)
        inner_layout.setContentsMargins(6, 4, 6, 4)
        inner_layout.setSpacing(4)

        # Action buttons (left)
        attach_btn = QPushButton()
        attach_btn.setObjectName("composerActionBtn")
        attach_btn.setFixedSize(30, 30)
        attach_btn.setIcon(ic.icon("attach", 15, "#555e78"))
        attach_btn.setIconSize(QSize(15, 15))
        attach_btn.setToolTip("Adjuntar archivo")
        inner_layout.addWidget(attach_btn)

        # Text input
        self._input = _ComposerInput()
        self._input.submit_requested.connect(self._on_submit)
        inner_layout.addWidget(self._input, 1)

        # Mic button
        mic_btn = QPushButton()
        mic_btn.setObjectName("composerActionBtn")
        mic_btn.setFixedSize(30, 30)
        mic_btn.setIcon(ic.icon("mic", 15, "#555e78"))
        mic_btn.setIconSize(QSize(15, 15))
        mic_btn.setToolTip("Entrada de voz (próximamente)")
        inner_layout.addWidget(mic_btn)

        # Send button
        self._send_btn = QPushButton()
        self._send_btn.setObjectName("sendBtn")
        self._send_btn.setFixedSize(34, 34)
        self._send_btn.setIcon(ic.icon("send", 15, "#0f1118"))
        self._send_btn.setIconSize(QSize(15, 15))
        self._send_btn.setToolTip("Enviar (Enter)")
        self._send_btn.clicked.connect(self._on_submit)
        inner_layout.addWidget(self._send_btn)

        outer.addWidget(inner)

    def _on_submit(self) -> None:
        text = self._input.toPlainText().strip()
        if text:
            self._input.clear()
            self.message_submitted.emit(text)

    def set_enabled(self, enabled: bool) -> None:
        self._input.setEnabled(enabled)
        self._send_btn.setEnabled(enabled)
        self._input.setPlaceholderText(
            "Generando respuesta…" if not enabled else "Haz una pregunta sobre tus documentos…"
        )

    def set_scope_label(self, label: str) -> None:
        self._scope_chip.setText(label)

    def set_text(self, text: str) -> None:
        self._input.setPlainText(text)
        from PySide6.QtGui import QTextCursor

        self._input.moveCursor(QTextCursor.MoveOperation.End)
