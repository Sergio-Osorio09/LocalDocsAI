#!/usr/bin/env python3
"""Download the BGE-M3 embedding model and the Qwen 2.5 14B LLM to the local models directory.

Run once before using the app for the first time:
    python scripts/download_models.py              # both models
    python scripts/download_models.py --embeddings # embeddings only (~1.5 GB)
    python scripts/download_models.py --llm        # LLM only (~8 GB)

This requires an internet connection.
Subsequent runs of 'localdocsai index/ask' are fully offline.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running directly from the scripts/ directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

_LLM_REPO = "Qwen/Qwen2.5-14B-Instruct-GGUF"
_LLM_FILENAME = "qwen2.5-14b-instruct-q4_k_m.gguf"


def download_embeddings(models_dir: Path) -> None:
    from localdocsai.indexing.embeddings import DIMENSION, MODEL_NAME

    print(f"Downloading {MODEL_NAME} (~1.5 GB) to {models_dir} ...")
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(MODEL_NAME, cache_folder=str(models_dir))
    test_vec = model.encode(["prueba"], normalize_embeddings=True)
    assert test_vec.shape == (1, DIMENSION), f"Unexpected embedding shape: {test_vec.shape}"
    print(f"  Embeddings OK — dimension: {DIMENSION}")


def download_llm(models_dir: Path) -> None:
    dest = models_dir / _LLM_FILENAME
    if dest.exists():
        print(f"  LLM already present: {dest}")
        return

    print(f"Downloading {_LLM_FILENAME} (~8 GB) to {models_dir} ...")
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        print(
            "  ERROR: huggingface_hub is not installed.\n"
            "  Install it with: uv pip install huggingface-hub\n"
            "  Or download manually from:\n"
            f"  https://huggingface.co/{_LLM_REPO}/resolve/main/{_LLM_FILENAME}\n"
            f"  and place it at: {dest}"
        )
        return

    hf_hub_download(
        repo_id=_LLM_REPO,
        filename=_LLM_FILENAME,
        local_dir=str(models_dir),
    )
    print(f"  LLM OK: {dest}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download LocalDocsAI models")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--embeddings", action="store_true", help="Download only the embedding model"
    )
    group.add_argument("--llm", action="store_true", help="Download only the LLM")
    args = parser.parse_args()

    from localdocsai.utils.paths import ensure_dir, get_models_dir

    models_dir = ensure_dir(get_models_dir())

    if args.embeddings:
        download_embeddings(models_dir)
    elif args.llm:
        download_llm(models_dir)
    else:
        download_embeddings(models_dir)
        download_llm(models_dir)

    print('\nAll done. You can now run: localdocsai ask "tu pregunta"')


if __name__ == "__main__":
    main()
