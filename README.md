# LocalDocsAI

> Offline RAG system for intelligent querying of normative and technical documents.

[![Tests](https://github.com/Sergio-Osorio09/LocalDocsAI/actions/workflows/tests.yml/badge.svg)](https://github.com/Sergio-Osorio09/LocalDocsAI/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

**[Versión en español](README.es.md)**

---

## What is LocalDocsAI?

LocalDocsAI is a cross-platform desktop application that lets you load a set of
documents (PDF, Word, Excel) and ask questions about them in natural language.
Responses are generated **entirely locally** — no internet connection required at
runtime, and your documents never leave your machine.

Every response includes **verifiable citations** to the source documents: file name,
page number, article or section. No hallucinated references.

### Key features

- **100% offline** — all inference runs on your machine
- **Verifiable citations** — every answer is linked to its source
- **Portable** — unzip and run, no installation, no admin rights required
- **Multilingual** — optimized for Spanish technical and normative documents
- **Configurable** — branding, model, colors: everything via a YAML file

---

## Supported document types

| Format | Extension | Parser |
|--------|-----------|--------|
| PDF | `.pdf` | PyMuPDF |
| Word | `.docx` | python-docx |
| Excel | `.xlsx`, `.xlsm` | openpyxl |

---

## Requirements

- Windows 10/11 (x64) or Linux (x64)
- 16 GB RAM recommended (8 GB minimum with smaller model)
- ~12 GB free disk space (for models)
- No Python installation required for the portable release

---

## Quick start

### Portable release (recommended)

1. Download the latest release from [GitHub Releases](https://github.com/Sergio-Osorio09/LocalDocsAI/releases)
2. Extract the ZIP to any folder
3. Run `LocalDocsAI.exe` (Windows) or `./LocalDocsAI` (Linux)
4. On first launch, the app downloads the language models (~10 GB) — this requires internet only once

### From source

```bash
# Clone the repository
git clone https://github.com/Sergio-Osorio09/LocalDocsAI.git
cd LocalDocsAI

# Install uv (if not installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync --extra dev

# Run
uv run localdocsai
```

---

## Usage

_Full user guide coming in Phase 6 (UI). For now, CLI usage:_

```bash
# Parse a document
uv run localdocsai parse path/to/document.pdf

# Index a folder
uv run localdocsai index path/to/documents/

# Ask a question
uv run localdocsai ask "What standard regulates gas odorization?"
```

---

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full system design.

```
Documents → Parsers → Chunker → Embedder (BGE-M3) → FAISS + SQLite
Query → Embedder → Retrieval → Reranker → LLM (Qwen 2.5 14B) → Validated response
```

---

## Development

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for the contributor guide.

```bash
# Linting
uv run ruff check src/ tests/
uv run black --check src/ tests/

# Type checking
uv run mypy src/localdocsai

# Tests
uv run pytest
```

---

## Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| 0 — Foundation | ✅ | Repo, tooling, CI |
| 1 — Parsers | Pending | PDF, DOCX, XLSX |
| 2 — Chunking | Pending | Normative-aware chunker |
| 3 — Indexing | Pending | FAISS + SQLite |
| 4 — LLM + Citations | Pending | Local inference + citation validation |
| 5 — Configuration | Pending | YAML profiles |
| 6 — UI | Pending | PySide6 desktop app |
| 7 — Reports | Pending | Word/PDF export |
| 8 — Windows validation | Pending | Cross-platform testing |
| 9 — Packaging | Pending | PyInstaller + GitHub Actions releases |
| 10 — v1.0 | Pending | Documentation + public release |

---

## License

MIT — see [LICENSE](LICENSE).

---

## Acknowledgements

Built with [llama-cpp-python](https://github.com/abetlen/llama-cpp-python),
[sentence-transformers](https://www.sbert.net/), [FAISS](https://faiss.ai/),
[PySide6](https://doc.qt.io/qtforpython/), and [PyMuPDF](https://pymupdf.readthedocs.io/).
