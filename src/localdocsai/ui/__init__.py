"""LocalDocsAI PySide6 desktop UI.

Public API:
    run_app(settings) — start the Qt event loop
"""

from __future__ import annotations


def run_app(settings: object | None = None) -> int:
    """Launch the LocalDocsAI desktop UI. Returns the process exit code."""
    import logging
    import os
    import sys
    from pathlib import Path

    # Force offline mode — models are always pre-downloaded; avoid HF network hangs
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    # Prevent OpenMP/PyTorch thread pool from deadlocking inside Qt's thread environment
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

    # File + stderr logging so crashes are always captured
    log_dir = Path.home() / ".local" / "share" / "localdocsai"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "localdocsai.log"

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8", mode="a"),
            logging.StreamHandler(sys.stderr),
        ],
        force=True,
    )
    log = logging.getLogger(__name__)
    log.info("=== LocalDocsAI starting — log: %s ===", log_file)

    from PySide6.QtWidgets import QApplication

    from localdocsai.config.settings import Settings
    from localdocsai.ui.main_window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("LocalDocsAI")
    app.setApplicationDisplayName("LocalDocsAI")

    # Load user config if saved, otherwise use defaults
    user_config = log_dir / "config.yaml"
    settings_obj: Settings
    if isinstance(settings, Settings):
        settings_obj = settings
    elif user_config.exists():
        try:
            settings_obj = Settings.load(user_config)
            log.info("Loaded user config from %s", user_config)
        except Exception:
            log.warning("Failed to load user config, using defaults", exc_info=True)
            settings_obj = Settings.defaults()
    else:
        settings_obj = Settings.defaults()

    window = MainWindow(settings=settings_obj)
    window.show()

    # Initialize pipeline after window is visible (heavy operation)
    from PySide6.QtCore import QTimer

    QTimer.singleShot(200, window.init_pipeline)

    return app.exec()
