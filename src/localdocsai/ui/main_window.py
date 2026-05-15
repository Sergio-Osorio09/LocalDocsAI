"""Main application window — wires together all UI panels and the RAG pipeline."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import QApplication, QHBoxLayout, QMainWindow, QVBoxLayout, QWidget

from localdocsai.ui.chat_area import ChatAreaWidget, ChatMessage, SourceRef, TraceInfo
from localdocsai.ui.sidebar import SidebarWidget
from localdocsai.ui.sources_panel import SourcesPanelWidget
from localdocsai.ui.topbar import TopbarWidget

# ---------------------------------------------------------------------------
# Pipeline worker
# ---------------------------------------------------------------------------


class _PipelineWorker(QObject):
    """Runs RAGPipeline.ask in a background thread, emits streaming tokens."""

    token_ready = Signal(str)
    finished = Signal(object)  # RAGResponse
    error = Signal(str)

    def __init__(self, pipeline: object, question: str) -> None:
        super().__init__()
        self._pipeline = pipeline
        self._question = question

    @Slot()
    def run(self) -> None:
        try:
            response = self._pipeline.ask(self._question)  # type: ignore[union-attr]
            self.finished.emit(response)
        except Exception as exc:
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------


class MainWindow(QMainWindow):
    """3-column layout: sidebar | chat | sources panel."""

    def __init__(self, settings: object | None = None) -> None:
        super().__init__()
        self._settings = settings
        self._pipeline: object | None = None
        self._worker_thread: QThread | None = None
        self._chat_counter = 0
        self._active_sources: list[SourceRef] = []

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

    def _load_theme(self) -> None:
        qss_path = Path(__file__).parent / "themes" / "dark.qss"
        if qss_path.exists():
            app = QApplication.instance()
            if app:
                app.setStyleSheet(qss_path.read_text(encoding="utf-8"))

    def init_pipeline(self) -> None:
        """Lazily initialize the RAG pipeline (heavy — call after window shown)."""
        try:
            from localdocsai.core.pipeline import RAGPipeline

            self._pipeline = RAGPipeline(settings=self._settings)
            self._sidebar.set_model_status("Modelo: listo")
        except ImportError:
            self._sidebar.set_model_status("Modelo: llama-cpp no instalado")
        except Exception as exc:
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
        self._chat_area.append_user_message(text)
        self._chat_area.start_streaming()

        if self._pipeline is None:
            self._finish_with_error(
                "El pipeline no está inicializado. Ejecuta 'localdocsai index'."
            )
            return

        # Run pipeline in background thread
        self._worker_thread = QThread(self)
        worker = _PipelineWorker(self._pipeline, text)
        worker.moveToThread(self._worker_thread)
        self._worker_thread.started.connect(worker.run)
        worker.finished.connect(self._on_pipeline_finished)
        worker.error.connect(self._on_pipeline_error)
        worker.finished.connect(self._worker_thread.quit)
        worker.error.connect(self._worker_thread.quit)
        self._worker_thread.start()

    @Slot(object)
    def _on_pipeline_finished(self, response: object) -> None:
        from localdocsai.core.pipeline import RAGResponse

        if not isinstance(response, RAGResponse):
            return

        sources = [
            SourceRef(
                id=f"s{i+1}",
                n=i + 1,
                title=chunk.doc_id,
                doc=chunk.doc_id,
                page=chunk.page,
                section=chunk.section_path,
                group_id="",
                chunk_id=str(chunk.chunk_id),
                score=chunk.score,
                snippet=chunk.text[:200],
            )
            for i, chunk in enumerate(response.retrieved_chunks)
        ]

        trace = TraceInfo(
            retrieved=response.validation.cited_indices.__len__()
            + len(response.validation.invalid_indices),
            reranked=len(response.retrieved_chunks),
            tokens=0,
            time="–",
            model=self._settings.model.llm if self._settings else "LLM",
            scope="Todas las fuentes",
        )

        msg = ChatMessage(
            role="assistant",
            text=response.answer,
            sources=sources,
            trace=trace,
        )
        self._chat_area.finish_streaming(msg)
        self._active_sources.extend(sources)
        self._sources_panel.load_sources(self._chat_area.get_all_sources())

    @Slot(str)
    def _on_pipeline_error(self, error: str) -> None:
        self._finish_with_error(f"Error en el pipeline: {error}")

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
        dlg = ExportDialog(chat_title=title, parent=self)
        dlg.export_requested.connect(self._on_export_requested)
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
        pass  # Report generation (Phase 7)
