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
    cancel_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("composerWidget")
        self._streaming = False
        self._last_question = ""
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
        attach_btn.setIcon(ic.icon("attach", 15, "#828690"))
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
        mic_btn.setIcon(ic.icon("mic", 15, "#828690"))
        mic_btn.setIconSize(QSize(15, 15))
        mic_btn.setToolTip("Entrada de voz (próximamente)")
        inner_layout.addWidget(mic_btn)

        # Send / cancel button (toggles depending on streaming state)
        self._send_btn = QPushButton()
        self._send_btn.setObjectName("sendBtn")
        self._send_btn.setFixedSize(34, 34)
        self._send_btn.setIcon(ic.icon("send", 15, "#4ec2e8"))
        self._send_btn.setIconSize(QSize(15, 15))
        self._send_btn.setToolTip("Enviar (Enter)")
        self._send_btn.clicked.connect(self._on_button_clicked)
        inner_layout.addWidget(self._send_btn)

        outer.addWidget(inner)

    def _on_button_clicked(self) -> None:
        if self._streaming:
            self.cancel_requested.emit()
        else:
            self._on_submit()

    def _on_submit(self) -> None:
        text = self._input.toPlainText().strip()
        if text:
            self._last_question = text
            self._input.clear()
            self.message_submitted.emit(text)

    def set_enabled(self, enabled: bool) -> None:
        """Toggle input/send state. When disabled the send button becomes a
        cancel (stop) button so the user can interrupt generation."""
        self._streaming = not enabled
        self._input.setEnabled(enabled)
        # Send button stays clickable even while streaming so it can cancel.
        self._send_btn.setEnabled(True)
        if self._streaming:
            self._send_btn.setIcon(ic.icon("close", 14, "#e36a52"))
            self._send_btn.setToolTip("Cancelar generación (Esc)")
            self._send_btn.setProperty("cancelling", "true")
            self._input.setPlaceholderText(
                "Generando respuesta…  pulsa el botón rojo para cancelar"
            )
        else:
            self._send_btn.setIcon(ic.icon("send", 15, "#4ec2e8"))
            self._send_btn.setToolTip("Enviar (Enter)")
            self._send_btn.setProperty("cancelling", "false")
            self._input.setPlaceholderText("Haz una pregunta sobre tus documentos…")
        # Force QSS re-evaluation so the cancelling-state styling applies.
        self._send_btn.style().unpolish(self._send_btn)
        self._send_btn.style().polish(self._send_btn)

    def restore_last_question(self) -> None:
        """Put the previous question back in the input so the user can edit it."""
        if self._last_question:
            self._input.setPlainText(self._last_question)
            from PySide6.QtGui import QTextCursor

            self._input.moveCursor(QTextCursor.MoveOperation.End)
            self._input.setFocus()

    def set_scope_label(self, label: str) -> None:
        self._scope_chip.setText(label)

    def set_text(self, text: str) -> None:
        self._input.setPlainText(text)
        from PySide6.QtGui import QTextCursor

        self._input.moveCursor(QTextCursor.MoveOperation.End)
