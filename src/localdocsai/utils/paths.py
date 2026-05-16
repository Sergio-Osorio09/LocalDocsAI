from __future__ import annotations

import re
import sys
from pathlib import Path


def get_app_data_dir() -> Path:
    """Return the platform-appropriate user data directory for LocalDocsAI.

    Windows : %APPDATA%/localdocsai  (C:/Users/<user>/AppData/Roaming/localdocsai)
    Linux/macOS: ~/.local/share/localdocsai
    """
    if sys.platform == "win32":
        return Path.home() / "AppData" / "Roaming" / "localdocsai"
    return Path.home() / ".local" / "share" / "localdocsai"


def get_app_root() -> Path:
    """Return the project root directory.

    Works both from the source tree and from a PyInstaller bundle:
      source: src/localdocsai/utils/paths.py → parents[3] = project root
      frozen: sys.executable is inside the bundle dir
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parents[3]


def get_models_dir() -> Path:
    """Directory where LLM and embedding model files are stored."""
    return get_app_root() / "models"


def get_indexes_dir() -> Path:
    """Directory where FAISS index and SQLite DB are stored."""
    return get_app_root() / "indexes"


def ensure_dir(path: Path) -> Path:
    """Create *path* (and parents) if it does not exist; return *path*."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def derive_doc_id(path: Path) -> str:
    """Convert a file path to a short, safe, lowercase document identifier.

    Strips all extensions (handles double extensions like .pdf.pdf),
    lowercases, and replaces unsafe characters with hyphens.

    Examples:
        Osinergmin-029-2016-OS-CD.pdf  → osinergmin-029-2016-os-cd
        DS N° 001-2022-MINEM-EM.pdf.pdf → ds-n-001-2022-minem-em
    """
    name = path.name
    while Path(name).suffix:
        name = Path(name).stem
    name = name.lower()
    name = re.sub(r"[°º]+", "", name)
    name = re.sub(r"[\s/\\]+", "-", name)
    name = re.sub(r"[^a-z0-9\-]", "", name)
    name = re.sub(r"-{2,}", "-", name).strip("-")
    return name[:64]
