"""Main application window — wires together all UI panels and the RAG pipeline."""

from __future__ import annotations

import logging
import traceback
import uuid
from dataclasses import asdict
from pathlib import Path

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import QApplication, QHBoxLayout, QMainWindow, QVBoxLayout, QWidget

from localdocsai.ui.chat_area import ChatAreaWidget, ChatMessage, SourceRef, TraceInfo
from localdocsai.ui.sidebar import ChatEntry, SidebarWidget
from localdocsai.ui.sources_panel import SourcesPanelWidget
from localdocsai.ui.topbar import TopbarWidget
from localdocsai.utils.paths import get_app_data_dir

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pipeline worker
# ---------------------------------------------------------------------------


class _CancelledByUser(Exception):
    """Raised inside the streaming callback when the user cancels generation."""


class _PipelineWorker(QObject):
    """Runs RAGPipeline steps in a background thread, emits phase signals."""

    phase_update = Signal(str)
    token_received = Signal(str)  # accumulated text so far (streaming)
    finished = Signal(object)  # RAGResponse
    cancelled = Signal()  # user-requested cancellation
    error = Signal(str)

    def __init__(self, pipeline: object, question: str) -> None:
        super().__init__()
        self._pipeline = pipeline
        self._question = question
        self._cancel_requested = False

    @Slot()
    def cancel(self) -> None:
        """Request cancellation. The streaming callback checks this flag and
        raises _CancelledByUser to break out of the llama-cpp generator loop."""
        self._cancel_requested = True

    def _on_token(self, text: str) -> None:
        if self._cancel_requested:
            raise _CancelledByUser()
        self.token_received.emit(text)

    @Slot()
    def run(self) -> None:
        try:
            from localdocsai.core.citation import format_response, validate_citations
            from localdocsai.core.pipeline import RAGResponse
            from localdocsai.llm.prompts import build_prompt

            _log.info("Worker started — question: %r", self._question[:80])

            self.phase_update.emit("Buscando en documentos…")
            chunks = self._pipeline._retriever.retrieve(  # type: ignore[union-attr]
                self._question,
                top_k=self._pipeline._top_k,  # type: ignore[union-attr]
            )
            _log.info("Retrieve done — %d chunks returned", len(chunks))

            if self._cancel_requested:
                self.cancelled.emit()
                return

            if not chunks:
                from localdocsai.core.citation import ValidationResult

                no_ctx = "No se encontraron documentos relevantes para esta consulta."
                self.finished.emit(
                    RAGResponse(
                        answer=no_ctx,
                        raw_answer=no_ctx,
                        retrieved_chunks=[],
                        validation=ValidationResult(is_valid=True),
                    )
                )
                return

            self.phase_update.emit("Generando respuesta con IA…")
            system_prompt, user_message = build_prompt(self._question, chunks)
            try:
                raw = self._pipeline._llm.generate_stream(  # type: ignore[union-attr]
                    system_prompt,
                    user_message,
                    max_tokens=self._pipeline._max_tokens,  # type: ignore[union-attr]
                    on_token=self._on_token,
                )
            except _CancelledByUser:
                _log.info("LLM generation cancelled by user")
                self.cancelled.emit()
                return
            _log.info("LLM done — %d chars generated", len(raw))

            validation = validate_citations(raw, len(chunks))
            answer = format_response(raw, chunks)

            self.finished.emit(
                RAGResponse(
                    answer=answer,
                    raw_answer=raw,
                    retrieved_chunks=chunks,
                    validation=validation,
                )
            )
        except _CancelledByUser:
            _log.info("Worker cancelled before LLM stage")
            self.cancelled.emit()
        except Exception as exc:
            tb = traceback.format_exc()
            _log.error("Worker exception:\n%s", tb)
            self.error.emit(f"{exc}\n\nTraceback:\n{tb}")


# ---------------------------------------------------------------------------
# Indexing worker
# ---------------------------------------------------------------------------


class _IndexingWorker(QObject):
    """Indexes a folder in a background thread."""

    progress = Signal(str, int, int)  # (filename, current, total)
    finished = Signal(int, int)  # (indexed, skipped)
    error = Signal(str)

    def __init__(self, folder: Path, pipeline: object) -> None:
        super().__init__()
        self._folder = folder
        self._pipeline = pipeline

    @Slot()
    def run(self) -> None:
        try:
            from localdocsai.indexing.indexing_service import IndexingService

            service = IndexingService(
                self._pipeline._retriever._ms,  # type: ignore[union-attr]
                self._pipeline._retriever._vs,  # type: ignore[union-attr]
                self._pipeline._retriever._em,  # type: ignore[union-attr]
            )

            def _progress(filename: str, current: int, total: int) -> None:
                self.progress.emit(filename, current, total)

            indexed, skipped = service.index_folder(self._folder, _progress)
            self.finished.emit(indexed, skipped)
        except Exception as exc:
            tb = traceback.format_exc()
            _log.error("Indexing error:\n%s", tb)
            self.error.emit(f"{exc}\n\n{tb}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _section_short(section_path: str) -> str:
    if not section_path:
        return ""
    if "›" in section_path:
        return section_path.rsplit("›", 1)[-1].strip()
    import re
    return re.split(r"[/\\]", section_path)[-1].strip()


def _parse_source_ref(d: dict) -> SourceRef:  # type: ignore[type-arg]
    return SourceRef(
        id=d["id"],
        n=int(d["n"]),
        title=d.get("title", ""),
        doc=d.get("doc", ""),
        doc_code=d.get("doc_code", ""),
        page=int(d.get("page", 0)),
        section=d.get("section", ""),
        section_short=d.get("section_short", ""),
        group_id=d.get("group_id", ""),
        chunk_id=str(d.get("chunk_id", "")),
        score=float(d.get("score", 0.0)),
        snippet=d.get("snippet", ""),
    )


def _parse_trace_info(d: dict) -> TraceInfo | None:  # type: ignore[type-arg]
    if not d:
        return None
    return TraceInfo(
        retrieved=int(d.get("retrieved", 0)),
        reranked=int(d.get("reranked", 0)),
        tokens=int(d.get("tokens", 0)),
        time=str(d.get("time", "–")),
        model=str(d.get("model", "")),
        scope=str(d.get("scope", "")),
    )


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------


class MainWindow(QMainWindow):
    """3-column layout: sidebar | chat | sources panel."""

    def __init__(self, settings: object | None = None) -> None:
        super().__init__()
        self._settings = settings
        self._pipeline: object | None = None

        # Pipeline worker (strong refs to prevent GC before thread runs)
        self._worker: _PipelineWorker | None = None
        self._worker_thread: QThread | None = None

        # Indexing worker
        self._indexing_worker: _IndexingWorker | None = None
        self._indexing_thread: QThread | None = None
        self._indexing_folder: Path | None = None

        # Active folder manager dialog (None when closed)
        self._folder_manager_dlg: object | None = None

        # Chat state
        self._current_chat_id: str | None = None
        # ID of the chat whose response is currently being streamed (None if
        # no worker is running). Used to drive the sidebar streaming dot.
        self._streaming_chat_id: str | None = None
        self._active_sources: list[SourceRef] = []
        self._active_template_path: Path | None = None

        # Session store (lazy — created after log_dir is known)
        from localdocsai.core.session import SessionStore

        session_db = get_app_data_dir() / "sessions.db"
        self._session_store = SessionStore(session_db)

        self.setWindowTitle("LocalDocsAI")
        self.setMinimumSize(960, 600)
        # Open at a comfortable working size; user can still resize/maximize.
        self.resize(1480, 920)

        self._setup_ui()
        self._connect_signals()
        self._load_theme()
        self._load_sidebar_chats()

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        self._root_layout = QHBoxLayout(central)
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)

        self._sidebar = SidebarWidget()
        self._root_layout.addWidget(self._sidebar)

        self._main_col = QWidget()
        main_v = QVBoxLayout(self._main_col)
        main_v.setContentsMargins(0, 0, 0, 0)
        main_v.setSpacing(0)

        self._topbar = TopbarWidget()
        main_v.addWidget(self._topbar)

        self._chat_area = ChatAreaWidget()
        main_v.addWidget(self._chat_area, 1)

        self._root_layout.addWidget(self._main_col, 1)

        self._sources_panel = SourcesPanelWidget()
        self._root_layout.addWidget(self._sources_panel)
        self._sources_panel.hide()

    def _connect_signals(self) -> None:
        self._sidebar.chat_selected.connect(self._on_chat_selected)
        self._sidebar.chat_delete_requested.connect(self._on_chat_delete)
        self._sidebar.new_chat_requested.connect(self._on_new_chat)
        self._sidebar.folders_requested.connect(self._open_folder_manager)
        self._sidebar.settings_requested.connect(self._open_settings)

        self._topbar.sources_toggled.connect(self._on_sources_toggled)
        self._topbar.export_requested.connect(self._open_export)
        self._topbar.scope_change_requested.connect(self._open_scope_selector)

        self._chat_area.message_submitted.connect(self._on_message_submitted)
        self._chat_area.cancel_requested.connect(self._on_cancel_requested)
        self._chat_area.cite_clicked.connect(self._on_cite_clicked)

        self._sources_panel.closed.connect(lambda: self._on_sources_toggled(False))
        self._sources_panel.open_pdf_requested.connect(self._open_pdf)
        self._sources_panel.citation_hovered.connect(self._chat_area.highlight_citation)
        self._sources_panel.citation_unhovered.connect(self._chat_area.clear_citation_highlight)
        self._sources_panel.source_activated.connect(self._on_source_card_activated)

    def _load_theme(self) -> None:
        qss_path = Path(__file__).parent / "themes" / "dark.qss"
        if qss_path.exists():
            app = QApplication.instance()
            if app:
                app.setStyleSheet(qss_path.read_text(encoding="utf-8"))

    def _load_sidebar_chats(self) -> None:
        stored = self._session_store.list_chats()
        entries = [
            ChatEntry(
                id=c.id,
                title=c.title,
                date=c.updated_at[:10],
                message_count=c.message_count,
            )
            for c in stored
        ]
        self._sidebar.load_chats(entries)

    def init_pipeline(self) -> None:
        """Lazily initialize the RAG pipeline (heavy — call after window shown)."""
        _log.info("init_pipeline() called")
        try:
            from localdocsai.core.pipeline import RAGPipeline

            self._pipeline = RAGPipeline(settings=self._settings)  # type: ignore[arg-type]
            _log.info("Pipeline initialized successfully")
            self._sidebar.set_model_status("Modelo: listo")
        except ImportError as exc:
            _log.error("llama-cpp not installed: %s", exc)
            self._sidebar.set_model_status("Modelo: llama-cpp no instalado")
        except Exception as exc:
            _log.error("Pipeline init error:\n%s", traceback.format_exc())
            self._sidebar.set_model_status(f"Error: {exc}")

    # ------------------------------------------------------------------
    # Chat handlers
    # ------------------------------------------------------------------

    @Slot(str)
    def _on_chat_selected(self, chat_id: str) -> None:
        import json

        self._current_chat_id = chat_id
        rows = self._session_store.load_messages(chat_id)

        messages: list[ChatMessage] = []
        for row in rows:
            sources_raw = json.loads(row["sources"]) if row["sources"] else []
            trace_raw = json.loads(row["trace"]) if row["trace"] else {}
            messages.append(
                ChatMessage(
                    role=row["role"],
                    text=row["text"],
                    sources=[_parse_source_ref(s) for s in sources_raw],
                    trace=_parse_trace_info(trace_raw),
                    citations_valid=bool(row["citations_valid"]),
                )
            )

        # Restore title from first user message
        first_user = next((m.text for m in messages if m.role == "user"), f"Chat {chat_id[:8]}")
        title = first_user[:50]
        self._topbar.set_title(title)

        self._active_sources = []
        self._chat_area.load_messages(messages)
        self._sidebar.set_active_chat(chat_id)

        all_sources = self._chat_area.get_all_sources()
        self._active_sources = list(all_sources)
        if all_sources:
            self._sources_panel.load_sources(all_sources)

    @Slot()
    def _on_new_chat(self) -> None:
        self._current_chat_id = None
        self._topbar.set_title("Nueva consulta")
        self._chat_area.load_messages([])
        self._active_sources = []
        self._sources_panel.load_sources([])
        self._sidebar.set_active_chat("")

    @Slot(str)
    def _on_chat_delete(self, chat_id: str) -> None:
        """Delete a chat from the session store and refresh the sidebar.

        If the deleted chat is the currently active one, reset to a new chat.
        """
        try:
            self._session_store.delete_chat(chat_id)
            _log.info("Chat deleted: %s", chat_id)
        except Exception:
            _log.error("Failed to delete chat %s:\n%s", chat_id, traceback.format_exc())
            return

        if self._current_chat_id == chat_id:
            self._on_new_chat()
        self._load_sidebar_chats()

    def _ensure_chat(self, first_message: str) -> str:
        """Create a session-store chat if one doesn't exist yet; return chat_id.

        When a new chat is created we immediately refresh the sidebar so the
        new entry shows up under RECIENTES — otherwise it stays invisible
        until the response finishes streaming.
        """
        if self._current_chat_id:
            return self._current_chat_id
        chat_id = str(uuid.uuid4())
        title = first_message[:50] or "Sin título"
        self._session_store.create_chat(chat_id, title)
        self._current_chat_id = chat_id
        self._topbar.set_title(title)
        self._load_sidebar_chats()
        self._sidebar.set_active_chat(chat_id)
        return chat_id

    def _save_current_messages(self, chat_id: str) -> None:
        """Overwrite saved messages for *chat_id* with the current conversation."""
        # Delete existing messages for this chat, then re-insert all
        import sqlite3

        session_db = get_app_data_dir() / "sessions.db"
        with sqlite3.connect(str(session_db)) as conn:
            conn.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
            conn.commit()

        for msg in self._chat_area._messages:
            self._session_store.save_message(
                chat_id=chat_id,
                role=msg.role,
                text=msg.text,
                sources=msg.sources,
                trace=msg.trace,
                citations_valid=msg.citations_valid,
            )

        self._load_sidebar_chats()
        self._sidebar.set_active_chat(chat_id)

    # ------------------------------------------------------------------
    # Message / pipeline
    # ------------------------------------------------------------------

    @Slot(str)
    def _on_message_submitted(self, text: str) -> None:
        _log.info("Message submitted: %r", text[:80])

        # Create chat session on first message
        chat_id = self._ensure_chat(text)
        # Mark this chat as the one currently generating so the sidebar row
        # shows the animated indicator until the response is finished.
        self._streaming_chat_id = chat_id
        self._sidebar.set_chat_streaming(chat_id, True)

        self._chat_area.append_user_message(text)
        self._chat_area.start_streaming()

        if self._pipeline is None:
            _log.error("_pipeline is None — init_pipeline may have failed silently")
            self._finish_with_error(
                f"El pipeline no está inicializado. Revisa el log en "
                f"{get_app_data_dir() / 'localdocsai.log'}"
            )
            return

        if self._worker_thread is not None and self._worker_thread.isRunning():
            _log.warning("Worker thread still running — rejecting new query")
            self._finish_with_error("Una consulta anterior sigue en curso. Espera a que termine.")
            return

        self._worker = _PipelineWorker(self._pipeline, text)
        self._worker_thread = QThread(self)

        self._worker.moveToThread(self._worker_thread)
        self._worker_thread.started.connect(self._worker.run)
        self._worker.phase_update.connect(self._chat_area.update_streaming_phase)
        self._worker.token_received.connect(self._chat_area.update_streaming)
        self._worker.finished.connect(self._on_pipeline_finished)
        self._worker.cancelled.connect(self._on_pipeline_cancelled)
        self._worker.error.connect(self._on_pipeline_error)
        self._worker.finished.connect(self._worker_thread.quit)
        self._worker.cancelled.connect(self._worker_thread.quit)
        self._worker.error.connect(self._worker_thread.quit)
        self._worker_thread.finished.connect(self._worker.deleteLater)
        self._worker_thread.finished.connect(self._worker_thread.deleteLater)
        self._worker_thread.finished.connect(self._on_worker_thread_done)

        _log.info("Starting pipeline worker thread")
        self._worker_thread.start()

    def _clear_streaming_indicator(self) -> None:
        """Turn off the sidebar 'generating' dot for the chat that just
        finished, errored, or was cancelled."""
        if self._streaming_chat_id is not None:
            self._sidebar.set_chat_streaming(self._streaming_chat_id, False)
            self._streaming_chat_id = None

    @Slot()
    def _on_cancel_requested(self) -> None:
        """User pressed the cancel button while a response was being generated."""
        if self._worker is None:
            return
        _log.info("Cancel requested by user")
        self._worker.cancel()

    @Slot()
    def _on_pipeline_cancelled(self) -> None:
        """Worker confirmed cancellation. Drop the streaming widget and put the
        question back in the composer so the user can edit it."""
        _log.info("Pipeline cancelled — restoring question to composer")
        self._chat_area.remove_streaming_widget()
        self._chat_area.restore_last_question()
        self._clear_streaming_indicator()

    @Slot(object)
    def _on_pipeline_finished(self, response: object) -> None:
        try:
            from localdocsai.core.pipeline import RAGResponse

            _log.info("Pipeline finished signal received")

            if not isinstance(response, RAGResponse):
                _log.error("Unexpected response type: %s", type(response))
                self._finish_with_error("Error interno: tipo de respuesta inesperado.")
                return

            sources = [
                SourceRef(
                    id=f"s{i+1}",
                    n=i + 1,
                    title=chunk.doc_id,
                    doc=chunk.doc_id,
                    doc_code=chunk.norm_code or Path(chunk.doc_id).name,
                    page=chunk.page,
                    section=chunk.section_path,
                    section_short=_section_short(chunk.section_path),
                    group_id="",
                    chunk_id=str(chunk.chunk_id),
                    score=chunk.score,
                    snippet=chunk.text[:200],
                )
                for i, chunk in enumerate(response.retrieved_chunks)
            ]

            model_name = "LLM"
            try:
                if self._settings is not None:
                    model_name = getattr(getattr(self._settings, "model", None), "llm", "LLM")
            except Exception:
                pass

            trace = TraceInfo(
                retrieved=len(response.validation.cited_indices)
                + len(response.validation.invalid_indices),
                reranked=len(response.retrieved_chunks),
                tokens=0,
                time="–",
                model=model_name,
                scope="Todas las fuentes",
            )

            citations_valid = response.validation.is_valid if response.validation else True
            cited_count = len(response.validation.cited_indices) if response.validation else 0

            msg = ChatMessage(
                role="assistant",
                text=response.answer,
                sources=sources,
                trace=trace,
                citations_valid=citations_valid,
            )
            self._chat_area.finish_streaming(msg)
            self._active_sources.extend(sources)
            self._sources_panel.load_sources(self._chat_area.get_all_sources())
            self._sources_panel.set_validation_status(citations_valid, cited_count)
            if sources:
                self._on_sources_toggled(True)

            # Persist conversation
            if self._current_chat_id:
                self._save_current_messages(self._current_chat_id)

            _log.info("Response displayed and saved")

        except Exception as exc:
            _log.error("Error in _on_pipeline_finished:\n%s", traceback.format_exc())
            self._finish_with_error(f"Error al mostrar la respuesta: {exc}")
        finally:
            self._clear_streaming_indicator()

    @Slot()
    def _on_worker_thread_done(self) -> None:
        self._worker_thread = None
        self._worker = None
        _log.debug("Worker thread cleaned up")

    @Slot(str)
    def _on_pipeline_error(self, error: str) -> None:
        _log.error("Pipeline error signal: %s", error[:200])
        self._finish_with_error(f"Error en el pipeline: {error.split(chr(10))[0]}")

    def _finish_with_error(self, error_text: str) -> None:
        msg = ChatMessage(role="assistant", text=f"*{error_text}*")
        self._chat_area.finish_streaming(msg)
        self._clear_streaming_indicator()

    @Slot(bool)
    def _on_sources_toggled(self, open_: bool) -> None:
        self._sources_panel.setVisible(open_)
        self._topbar.set_sources_open(open_)
        if open_:
            self._sources_panel.load_sources(self._chat_area.get_all_sources())

    @Slot(int, list)
    def _on_cite_clicked(self, n: int, sources: list[SourceRef]) -> None:
        if n == 0:
            self._on_sources_toggled(True)
            return
        source = next((s for s in sources if s.n == n), None)
        if not source:
            return
        if not self._sources_panel.isVisible():
            self._on_sources_toggled(True)
        self._sources_panel.set_active_source(source.id)
        # Persistent active state on the [N] chip itself.
        self._chat_area.set_active_citation(n)

    @Slot(str)
    def _on_source_card_activated(self, source_id: str) -> None:
        """Mirror the active state back to the citation chip when a card
        is clicked in the sources panel."""
        source = next((s for s in self._active_sources if s.id == source_id), None)
        if source is None:
            return
        self._chat_area.set_active_citation(source.n)

    # ------------------------------------------------------------------
    # Open dialogs
    # ------------------------------------------------------------------

    def _open_folder_manager(self) -> None:
        from localdocsai.ui.dialogs.folder_manager import FolderManagerDialog

        ms = None
        if self._pipeline is not None:
            try:
                ms = self._pipeline._retriever._ms  # type: ignore[union-attr]
            except Exception:
                pass

        dlg = FolderManagerDialog(metadata_store=ms, parent=self)
        dlg.indexing_requested.connect(self._on_indexing_requested)
        self._folder_manager_dlg = dlg
        dlg.finished.connect(lambda _: setattr(self, "_folder_manager_dlg", None))
        dlg.exec()

    def _open_settings(self) -> None:
        from localdocsai.ui.dialogs.settings_dialog import SettingsDialog

        dlg = SettingsDialog(settings=self._settings, parent=self)
        dlg.settings_saved.connect(self._on_settings_saved)
        dlg.exec()

    def _open_export(self) -> None:
        from localdocsai.ui.dialogs.export_dialog import ExportDialog

        title = self._topbar._title.text()
        custom_tpl = ""
        if self._settings and hasattr(self._settings, "reports"):
            custom_tpl = getattr(self._settings.reports, "custom_template", "")

        dlg = ExportDialog(chat_title=title, custom_template=custom_tpl, parent=self)
        dlg.export_requested.connect(self._on_export_requested)
        dlg.template_export_requested.connect(self._on_template_export_requested)
        dlg.exec()

    def _open_pdf(self, source_id: str) -> None:
        sources = self._chat_area.get_all_sources()
        src = next((s for s in sources if s.id == source_id), None)
        if not src:
            return
        path = Path(src.doc)
        if not path.exists():
            return
        from localdocsai.ui.dialogs.pdf_viewer import PdfViewerDialog

        dlg = PdfViewerDialog(path=path, initial_page=src.page, parent=self)
        dlg.exec()

    def _open_scope_selector(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    @Slot(list)
    def _on_indexing_requested(self, paths: list[Path]) -> None:
        if self._pipeline is None:
            self._sidebar.set_model_status("Indexado: pipeline no inicializado")
            return
        if self._indexing_thread is not None and self._indexing_thread.isRunning():
            _log.warning("Indexing already in progress")
            return

        for folder in paths:
            _log.info("Indexing requested for: %s", folder)
            self._indexing_folder = folder
            self._indexing_worker = _IndexingWorker(folder, self._pipeline)
            self._indexing_thread = QThread(self)

            self._indexing_worker.moveToThread(self._indexing_thread)
            self._indexing_thread.started.connect(self._indexing_worker.run)
            self._indexing_worker.progress.connect(self._on_indexing_progress)
            self._indexing_worker.finished.connect(self._on_indexing_finished)
            self._indexing_worker.error.connect(self._on_indexing_error)
            self._indexing_worker.finished.connect(self._indexing_thread.quit)
            self._indexing_worker.error.connect(self._indexing_thread.quit)
            self._indexing_thread.finished.connect(self._indexing_worker.deleteLater)
            self._indexing_thread.finished.connect(self._indexing_thread.deleteLater)
            self._indexing_thread.finished.connect(self._on_indexing_thread_done)

            self._indexing_thread.start()
            break  # process one folder at a time

    @Slot(str, int, int)
    def _on_indexing_progress(self, filename: str, current: int, total: int) -> None:
        if total > 0 and filename:
            self._sidebar.set_model_status(f"Indexando {current+1}/{total}: {filename[:30]}")
            if self._folder_manager_dlg is not None:
                try:
                    self._folder_manager_dlg.set_indexing_progress(  # type: ignore[union-attr]
                        filename, current, total
                    )
                except Exception:
                    pass

    @Slot(int, int)
    def _on_indexing_finished(self, indexed: int, skipped: int) -> None:
        msg = f"Indexado: {indexed} nuevos, {skipped} omitidos"
        _log.info(msg)
        self._sidebar.set_model_status(msg)
        QTimer.singleShot(4000, lambda: self._sidebar.set_model_status("Modelo: listo"))
        if self._folder_manager_dlg is not None and self._indexing_folder is not None:
            try:
                self._folder_manager_dlg.set_indexing_done(  # type: ignore[union-attr]
                    self._indexing_folder, indexed, skipped
                )
            except Exception:
                pass

    @Slot(str)
    def _on_indexing_error(self, error: str) -> None:
        _log.error("Indexing error: %s", error[:200])
        self._sidebar.set_model_status("Error al indexar — ver log")
        QTimer.singleShot(5000, lambda: self._sidebar.set_model_status("Modelo: listo"))

    @Slot()
    def _on_indexing_thread_done(self) -> None:
        self._indexing_thread = None
        self._indexing_worker = None
        _log.debug("Indexing thread cleaned up")

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    @Slot(dict)
    def _on_settings_saved(self, data: dict) -> None:
        try:
            from localdocsai.config.settings import Settings

            current: dict = {}
            if self._settings is not None:
                try:
                    current = self._settings.model_dump()  # type: ignore[union-attr]
                except Exception:
                    pass

            for section, values in data.items():
                if isinstance(current.get(section), dict) and isinstance(values, dict):
                    current[section].update(values)
                else:
                    current[section] = values

            new_settings = Settings.model_validate(current)
            self._settings = new_settings

            config_path = get_app_data_dir() / "config.yaml"
            new_settings.save(config_path)
            _log.info("Settings saved to %s", config_path)

            # Apply retrieval/model settings to running pipeline immediately
            if self._pipeline is not None:
                try:
                    self._pipeline._top_k = new_settings.retrieval.top_k  # type: ignore
                    self._pipeline._max_tokens = new_settings.model.max_tokens  # type: ignore
                except Exception:
                    pass

        except Exception:
            _log.error("Failed to save settings:\n%s", traceback.format_exc())

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    @Slot(str, str)
    def _on_export_requested(self, fmt: str, output_path: str) -> None:
        from localdocsai.reports.writer import write_conversation_docx

        messages = [
            {"role": m.role, "text": m.text, "sources": [asdict(s) for s in m.sources]}
            for m in self._chat_area._messages
        ]
        title = self._topbar._title.text() or "Conversación"
        out = Path(output_path).with_suffix(".docx")

        model_name = ""
        try:
            if self._settings is not None:
                model_name = getattr(getattr(self._settings, "model", None), "llm", "") or ""
        except Exception:
            pass

        try:
            write_conversation_docx(messages, out, title, model_name=model_name)
            _log.info("Conversation exported to %s", out)
        except Exception:
            _log.error("Export failed:\n%s", traceback.format_exc())

    @Slot(str, str)
    def _on_template_export_requested(self, template_path: str, scope: str) -> None:
        from localdocsai.reports import autofill, detect_fields
        from localdocsai.ui.dialogs.report_editor import ReportEditorDialog

        tpl = Path(template_path)
        if not tpl.exists():
            return

        self._active_template_path = tpl
        fields = detect_fields(tpl)
        messages = self._build_messages_for_scope(scope)
        chat_title = self._topbar._title.text()
        filled = autofill(fields, messages, chat_title)

        editor = ReportEditorDialog(
            fields=filled,
            template_path=tpl,
            chat_title=chat_title,
            parent=self,
        )
        editor.generation_confirmed.connect(self._on_generation_confirmed)
        editor.exec()

    @Slot(str, list)
    def _on_generation_confirmed(self, output_path: str, fields: list) -> None:
        from localdocsai.reports import write_docx

        tpl = self._active_template_path
        if tpl and tpl.exists():
            write_docx(tpl, fields, Path(output_path))

    def _build_messages_for_scope(self, scope: str) -> list[dict[str, str]]:
        all_msgs = [{"role": m.role, "text": m.text} for m in self._chat_area._messages]
        if scope == "Últimos 5 mensajes":
            return all_msgs[-5:]
        if scope == "Últimos 10 mensajes":
            return all_msgs[-10:]
        if scope == "Solo respuestas del asistente":
            return [m for m in all_msgs if m["role"] == "assistant"]
        return all_msgs
