"""LocalDocsAI PySide6 desktop UI.

Public API:
    run_app(settings) — start the Qt event loop
"""

from __future__ import annotations


def run_app(settings: object | None = None) -> int:
    """Launch the LocalDocsAI desktop UI. Returns the process exit code."""
    import sys

    from PySide6.QtWidgets import QApplication

    from localdocsai.ui.main_window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("LocalDocsAI")
    app.setApplicationDisplayName("LocalDocsAI")

    window = MainWindow(settings=settings)
    window.show()

    # Initialize pipeline after window is visible (heavy operation)
    from PySide6.QtCore import QTimer

    QTimer.singleShot(200, window.init_pipeline)

    return app.exec()
