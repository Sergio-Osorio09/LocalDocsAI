"""Main application window — wires together all UI panels and the RAG pipeline."""

from __future__ import annotations

import logging
import traceback
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import QApplication, QHBoxLayout, QMainWindow, QVBoxLayout, QWidget

from localdocsai.ui.chat_area import ChatAreaWidget, ChatMessage, SourceRef, TraceInfo
from localdocsai.ui.sidebar import SidebarWidget
from localdocsai.ui.sources_panel import SourcesPanelWidget
from localdocsai.ui.topbar import TopbarWidget

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pipeline worker
# ---------------------------------------------------------------------------


class _PipelineWorker(QObject):
    """Runs RAGPipeline steps in a background thread, emits phase signals."""

    phase_update = Signal(str)
    finished = Signal(object)  # RAGResponse
    error = Signal(str)

    def __init__(self, pipeline: object, question: str) -> None:
        super().__init__()
        self._pipeline = pipeline
        self._question = question

    @Slot()
    def run(self) -> None:
        try:
            from localdocsai.core.citation import format_response, validate_citations
            from localdocsai.core.pipeline import RAGResponse
            from localdocsai.llm.prompts import build_prompt

            _log.info("Worker started — question: %r", self._question[:80])

            self.phase_update.emit("Buscando en documentos…")
            _log.debug("Calling retriever.retrieve()")
            chunks = self._pipeline._retriever.retrieve(  # type: ignore[union-attr]
                self._question,
                top_k=self._pipeline._top_k,  # type: ignore[union-attr]
            )
            _log.info("Retrieve done — %d chunks returned", len(chunks))

            if not chunks:
                from localdocsai.core.citation import ValidationResult

                _log.warning("No chunks found — returning empty-context response")
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
            _log.debug("Building prompt")
            system_prompt, user_message = build_prompt(self._question, chunks)
            _log.debug("Calling LLM.generate()")
            raw = self._pipeline._llm.generate(  # type: ignore[union-attr]
                system_prompt,
                user_message,
                max_tokens=self._pipeline._max_tokens,  # type: ignore[union-attr]
            )
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
        except Exception as exc:
            tb = traceback.format_exc()
            _log.error("Worker exception:\n%s", tb)
            self.error.emit(f"{exc}\n\nTraceback:\n{tb}")


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------


class MainWindow(QMainWindow):
    """3-column layout: sidebar | chat | sources panel."""

    def __init__(self, settings: object | None = None) -> None:
        super().__init__()
        self._settings = settings
        self._pipeline: object | None = None
        self._worker: _PipelineWorker | None = None  # kept alive for thread duration
        self._worker_thread: QThread | None = None
        self._chat_counter = 0
        self._active_sources: list[SourceRef] = []
        self._active_template_path: Path | None = None

        self.setWindowTitle("LocalDocsAI")
        self.setMinimumSize(1024, 680)

        self._setup_ui()
        self._connect_signals()
        self._load_theme()

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        self._root_layout = QHBoxLayout(central)
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)

        # Sidebar
        self._sidebar = SidebarWidget()
        self._root_layout.addWidget(self._sidebar)

        # Main column (topbar + chat)
        self._main_col = QWidget()
        main_v = QVBoxLayout(self._main_col)
        main_v.setContentsMargins(0, 0, 0, 0)
        main_v.setSpacing(0)

        self._topbar = TopbarWidget()
        main_v.addWidget(self._topbar)

        self._chat_area = ChatAreaWidget()
        main_v.addWidget(self._chat_area, 1)

        self._root_layout.addWidget(self._main_col, 1)

        # Sources panel (hidden by default)
        self._sources_panel = SourcesPanelWidget()
        self._root_layout.addWidget(self._sources_panel)
        self._sources_panel.hide()

    def _connect_signals(self) -> None:
        # Sidebar
        self._sidebar.chat_selected.connect(self._on_chat_selected)
        self._sidebar.new_chat_requested.connect(self._on_new_chat)
        self._sidebar.folders_requested.connect(self._open_folder_manager)
        self._sidebar.settings_requested.connect(self._open_settings)

        # Topbar
        self._topbar.sources_toggled.connect(self._on_sources_toggled)
        self._topbar.export_requested.connect(self._open_export)
        self._topbar.scope_change_requested.connect(self._open_scope_selector)

        # Chat area
        self._chat_area.message_submitted.connect(self._on_message_submitted)
        self._chat_area.cite_clicked.connect(self._on_cite_clicked)

        # Sources panel
        self._sources_panel.closed.connect(lambda: self._on_sources_toggled(False))
        self._sources_panel.open_pdf_requested.connect(self._open_pdf)
        self._sources_panel.citation_hovered.connect(self._chat_area.highlight_citation)
        self._sources_panel.citation_unhovered.connect(self._chat_area.clear_citation_highlight)

    def _load_theme(self) -> None:
        qss_path = Path(__file__).parent / "themes" / "dark.qss"
        if qss_path.exists():
            app = QApplication.instance()
            if app:
                app.setStyleSheet(qss_path.read_text(encoding="utf-8"))

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
    # Handlers
    # ------------------------------------------------------------------

    @Slot(str)
    def _on_chat_selected(self, chat_id: str) -> None:
        self._topbar.set_title(f"Chat {chat_id}")
        self._chat_area.load_messages([])

    @Slot()
    def _on_new_chat(self) -> None:
        self._chat_counter += 1
        self._topbar.set_title("Nueva consulta")
        self._chat_area.load_messages([])
        self._active_sources = []
        self._sources_panel.load_sources([])
        self._sidebar.set_active_chat("")

    @Slot(str)
    def _on_message_submitted(self, text: str) -> None:
        _log.info("Message submitted: %r", text[:80])
        self._chat_area.append_user_message(text)
        self._chat_area.start_streaming()

        if self._pipeline is None:
            _log.error("_pipeline is None — init_pipeline may have failed silently")
            self._finish_with_error(
                "El pipeline no está inicializado. Revisa el log en "
                "~/.local/share/localdocsai/localdocsai.log"
            )
            return

        # Guard against double-submission while a query is running
        if self._worker_thread is not None and self._worker_thread.isRunning():
            _log.warning("Worker thread still running — rejecting new query")
            self._finish_with_error("Una consulta anterior sigue en curso. Espera a que termine.")
            return

        # Keep a strong reference to the worker so Python GC doesn't destroy it
        # before the thread picks it up (PySide6 uses weak refs for signal slots).
        self._worker = _PipelineWorker(self._pipeline, text)
        self._worker_thread = QThread(self)

        self._worker.moveToThread(self._worker_thread)
        self._worker_thread.started.connect(self._worker.run)
        self._worker.phase_update.connect(self._chat_area.update_streaming_phase)
        self._worker.finished.connect(self._on_pipeline_finished)
        self._worker.error.connect(self._on_pipeline_error)
        self._worker.finished.connect(self._worker_thread.quit)
        self._worker.error.connect(self._worker_thread.quit)
        self._worker_thread.finished.connect(self._worker.deleteLater)
        self._worker_thread.finished.connect(self._worker_thread.deleteLater)
        self._worker_thread.finished.connect(self._on_worker_thread_done)

        _log.info("Starting pipeline worker thread")
        self._worker_thread.start()

    @Slot(object)
    def _on_pipeline_finished(self, response: object) -> None:
        try:
            from localdocsai.core.pipeline import RAGResponse

            _log.info("Pipeline finished signal received")

            if not isinstance(response, RAGResponse):
                _log.error("Unexpected response type: %s", type(response))
                self._finish_with_error("Error interno: tipo de respuesta inesperado.")
                return

            def _section_short(section_path: str) -> str:
                if not section_path:
                    return ""
                if "›" in section_path:
                    return section_path.rsplit("›", 1)[-1].strip()
                return section_path.split("/")[-1].strip()

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
                settings = self._settings
                if settings is not None:
                    model_name = getattr(getattr(settings, "model", None), "llm", "LLM")
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
            _log.info("Response displayed successfully")

        except Exception as exc:
            _log.error("Error in _on_pipeline_finished:\n%s", traceback.format_exc())
            self._finish_with_error(f"Error al mostrar la respuesta: {exc}")

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

    # ------------------------------------------------------------------
    # Open dialogs
    # ------------------------------------------------------------------

    def _open_folder_manager(self) -> None:
        from localdocsai.ui.dialogs.folder_manager import FolderManagerDialog

        dlg = FolderManagerDialog(parent=self)
        dlg.indexing_requested.connect(self._on_indexing_requested)
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
        pass  # Scope selector is a future feature (dropdown menu)

    @Slot(list)
    def _on_indexing_requested(self, paths: list[Path]) -> None:
        pass  # Indexing progress will be handled in a future toast/progress widget

    @Slot(dict)
    def _on_settings_saved(self, data: dict) -> None:
        pass  # Apply settings changes at runtime (future)

    @Slot(str, str)
    def _on_export_requested(self, fmt: str, output_path: str) -> None:
        pass  # PDF export (future)

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
        """Convert ChatMessage list to plain dicts for the generator."""
        all_msgs = [{"role": m.role, "text": m.text} for m in self._chat_area._messages]
        if scope == "Últimos 5 mensajes":
            return all_msgs[-5:]
        if scope == "Últimos 10 mensajes":
            return all_msgs[-10:]
        if scope == "Solo respuestas del asistente":
            return [m for m in all_msgs if m["role"] == "assistant"]
        return all_msgs
