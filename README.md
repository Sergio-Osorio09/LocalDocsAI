# LocalDocsAI

> Offline RAG desktop app for intelligent querying of normative and technical documents.

[![Tests](https://github.com/Sergio-Osorio09/LocalDocsAI/actions/workflows/tests.yml/badge.svg)](https://github.com/Sergio-Osorio09/LocalDocsAI/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

**[Versión en español](README.es.md)**

---

## What is LocalDocsAI?

LocalDocsAI is a cross-platform desktop application (PySide6) that lets you load
a folder of documents (PDF, Word, Excel) and ask questions about them in natural
language. Responses are generated **entirely on your machine** — no internet
connection required at runtime, and your documents never leave your laptop.

Every response includes **verifiable citations** to the source documents:
file name, page number, article or section, plus a clickable bidirectional
link between each `[N]` marker in the answer and the corresponding source card
in the right-side panel.

### Highlights

- **100% offline** — embedding and LLM inference both run locally
- **Per-sentence citations** — every claim is attached to the chunk that best
  supports it, using a length-normalized recall/precision score
- **Streaming responses** with a real "stop" button to cancel mid-generation
- **Sidebar with live indicator** — a chat created right now appears in
  RECIENTES immediately and shows an animated cyan dot while it is still
  generating, even if you switch to another chat
- **Rich Word and PDF export** — title, metadata table, numbered Q/A sections,
  amber citation chips, full source list with snippet + chunk_id, paginated
  footer
- **Optimized for Spanish** technical and normative documents
- **Configurable** — model, context window, retrieval k, theme — everything
  via a YAML file in `%APPDATA%/localdocsai/config.yaml` (Windows) or
  `~/.local/share/localdocsai/config.yaml` (Linux/macOS)

---

## Supported document types

| Format | Extension | Parser |
|--------|-----------|--------|
| PDF    | `.pdf`    | PyMupdf |
| Word   | `.docx`   | python-docx |
| Excel  | `.xlsx`, `.xlsm` | openpyxl |

---

## Requirements

- Windows 10/11 (x64) — primary target. Linux is supported via the same source
  install but has not been packaged yet.
- 8 GB RAM minimum for the 3B model, 16 GB recommended for the 14B model
- ~3 GB free disk space for the bundled Qwen 2.5 3B Q4_K_M model, ~9 GB if you
  switch to the 14B variant
- NVIDIA GPU with CUDA optional but recommended — inference on CPU works but
  is 3-5× slower

---

## Quick start

### From source (current path)

```powershell
# 1. Clone the repository
git clone https://github.com/Sergio-Osorio09/LocalDocsAI.git
cd LocalDocsAI

# 2. Create a virtual environment and install
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[all]"

# 3. Install llama-cpp-python from the prebuilt CPU wheel index
#    (the source build fails on Windows due to the 260-char MAX_PATH limit)
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu

# 4. Download the default LLM (Qwen 2.5 3B Instruct, ~2 GB)
python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='Qwen/Qwen2.5-3B-Instruct-GGUF', filename='qwen2.5-3b-instruct-q4_k_m.gguf', local_dir='models')"

# 5. Launch the desktop UI
python -m localdocsai ui
```

The first time you ask a question the BGE-M3 embedding model (~2.3 GB) is
downloaded to the HuggingFace cache. Subsequent launches are fully offline.

### Optional: GPU build for NVIDIA cards

If you have a recent NVIDIA GPU and the CUDA runtime installed, replace step 3
with the CUDA wheel index so generation is 3-5× faster:

```powershell
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu122 --force-reinstall --no-cache-dir
```

Then raise `model.n_gpu_layers` in `config.yaml` to load layers onto the GPU.

---

## Using the desktop app

1. **Add a folder** — open *Carpetas* (bottom-left), pick the folder containing
   your PDFs / Word / Excel files. The app indexes everything (parse → chunk
   → embed → FAISS) with a live progress bar and per-file status.
2. **Ask a question** in the composer at the bottom. The streaming response
   appears in the chat area with citation chips `[1]`, `[2]`, … next to each
   claim.
3. **Click any `[N]`** to highlight the matching source card on the right and
   vice versa. Clicking again on the source pulls up the snippet excerpt.
4. **Cancel** mid-generation by clicking the red ✕ button in the composer — the
   original question is restored to the input so you can edit and resend.
5. **Export** the conversation via the *Exportar* button. Word (`.docx`) gives
   you a fully styled report with metadata, citation chips and per-source
   snippets; PDF (`.pdf`) is laid out the same way using reportlab so no
   external converter is needed.

### CLI

The same pipeline is also exposed as CLI commands for batch use:

```powershell
python -m localdocsai parse path\to\document.pdf
python -m localdocsai index path\to\documents\
python -m localdocsai ask  "¿Qué norma regula la odorización del gas natural?"
```

---

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full system design.

```
Documents → Parsers → Normative chunker → BGE-M3 embeddings → FAISS + SQLite
                                                                     ↓
Query → BGE-M3 → FAISS top-k → (optional reranker) → Qwen 2.5 ─→ Validated answer
                                                                  with [N] citations
```

---

## Development

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for the contributor guide.

```powershell
# Linting
ruff check src/ tests/
black --check src/ tests/

# Type checking
mypy src/localdocsai

# Tests
pytest
```

216 tests currently pass; CI runs them on every push.

---

## Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| 0 — Foundation | ✅ | Repo, tooling, CI |
| 1 — Parsers | ✅ | PDF, DOCX, XLSX |
| 2 — Chunking | ✅ | Normative-aware chunker |
| 3 — Indexing | ✅ | FAISS + SQLite |
| 4 — LLM + Citations | ✅ | Local inference + per-sentence citation enrichment |
| 5 — Configuration | ✅ | YAML profiles, settings dialog |
| 6 — UI | ✅ | PySide6 desktop app with the LocalDocsAI Prototype theme |
| 7 — Reports | ✅ | Rich Word + PDF export |
| 8 — Windows validation | ✅ | Cross-platform path / GPU / SQL LIKE fixes |
| 9 — Packaging | 🔄 | PyInstaller portable bundle |
| 10 — v1.0 | Pending | Documentation + public release |

---

## License

MIT — see [LICENSE](LICENSE).

---

## Acknowledgements

Built with [llama-cpp-python](https://github.com/abetlen/llama-cpp-python),
[sentence-transformers](https://www.sbert.net/), [FAISS](https://faiss.ai/),
[PySide6](https://doc.qt.io/qtforpython/), [PyMuPDF](https://pymupdf.readthedocs.io/),
[python-docx](https://python-docx.readthedocs.io/) and
[reportlab](https://www.reportlab.com/).
