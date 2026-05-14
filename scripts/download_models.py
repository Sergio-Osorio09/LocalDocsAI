#!/usr/bin/env python3
"""Download the BGE-M3 embedding model to the local models directory.

Run once before indexing documents for the first time:
    python scripts/download_models.py

This requires an internet connection (~1.5 GB download).
Subsequent runs of 'localdocsai index' are fully offline.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running directly from the scripts/ directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def main() -> None:
    from localdocsai.indexing.embeddings import DIMENSION, MODEL_NAME
    from localdocsai.utils.paths import ensure_dir, get_models_dir

    models_dir = ensure_dir(get_models_dir())
    print(f"Downloading {MODEL_NAME} to {models_dir} ...")
    print("Expected download size: ~1.5 GB. This may take several minutes.\n")

    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(MODEL_NAME, cache_folder=str(models_dir))

    # Smoke test
    test_vec = model.encode(["prueba"], normalize_embeddings=True)
    assert test_vec.shape == (1, DIMENSION), (
        f"Unexpected embedding shape: {test_vec.shape}, expected (1, {DIMENSION})"
    )

    print(f"\nModel ready. Embedding dimension: {DIMENSION}")
    print("You can now run: localdocsai index <folder>")


if __name__ == "__main__":
    main()
