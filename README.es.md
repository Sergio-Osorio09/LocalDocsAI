# LocalDocsAI

> Sistema RAG offline para consulta inteligente de documentos normativos y técnicos.

[![Tests](https://github.com/Sergio-Osorio09/LocalDocsAI/actions/workflows/tests.yml/badge.svg)](https://github.com/Sergio-Osorio09/LocalDocsAI/actions/workflows/tests.yml)
[![Licencia: MIT](https://img.shields.io/badge/Licencia-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

**[English version](README.md)**

---

## ¿Qué es LocalDocsAI?

LocalDocsAI es una aplicación de escritorio multiplataforma que permite cargar un
conjunto de documentos (PDF, Word, Excel) y hacer preguntas sobre su contenido en
lenguaje natural. Las respuestas se generan **completamente de forma local** — no
requiere conexión a internet en tiempo de ejecución, y tus documentos nunca salen
de tu máquina.

Cada respuesta incluye **citas verificables** a los documentos fuente: nombre del
archivo, número de página, artículo o sección. Sin referencias inventadas.

### Características principales

- **100% offline** — toda la inferencia ocurre en tu máquina
- **Citas verificables** — cada afirmación está vinculada a su fuente
- **Portable** — descomprimís y ejecutás, sin instalación, sin permisos de admin
- **Multilingüe** — optimizado para español técnico y documentos normativos
- **Configurable** — branding, modelo, colores: todo mediante un archivo YAML

---

## Formatos de documento soportados

| Formato | Extensión | Parser |
|---------|-----------|--------|
| PDF | `.pdf` | PyMuPDF |
| Word | `.docx` | python-docx |
| Excel | `.xlsx`, `.xlsm` | openpyxl |

---

## Requisitos

- Windows 10/11 (x64) o Linux (x64)
- 16 GB de RAM recomendado (mínimo 8 GB con modelo más pequeño)
- ~12 GB de espacio en disco (para los modelos)
- No requiere Python instalado en la máquina destino (versión portable)

---

## Inicio rápido

### Versión portable (recomendada)

1. Descargá la última versión desde [GitHub Releases](https://github.com/Sergio-Osorio09/LocalDocsAI/releases)
2. Descomprimí el ZIP en cualquier carpeta
3. Ejecutá `LocalDocsAI.exe` (Windows) o `./LocalDocsAI` (Linux)
4. En el primer arranque, la app descarga los modelos de lenguaje (~10 GB) — requiere internet solo esa vez

### Desde el código fuente

```bash
# Clonar el repositorio
git clone https://github.com/Sergio-Osorio09/LocalDocsAI.git
cd LocalDocsAI

# Instalar uv (si no está instalado)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Instalar dependencias
uv sync --extra dev

# Ejecutar
uv run localdocsai
```

---

## Uso

_Guía completa disponible en la Fase 6 (UI). Por ahora, uso por CLI:_

```bash
# Parsear un documento
uv run localdocsai parse ruta/al/documento.pdf

# Indexar una carpeta
uv run localdocsai index ruta/a/documentos/

# Hacer una pregunta
uv run localdocsai ask "¿Qué norma regula la odorización del gas natural?"
```

---

## Arquitectura

Ver [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) para el diseño completo del sistema.

```
Documentos → Parsers → Chunker → Embedder (BGE-M3) → FAISS + SQLite
Consulta → Embedder → Retrieval → Reranker → LLM (Qwen 2.5 14B) → Respuesta con citas
```

---

## Desarrollo

Ver [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) para la guía de contribuidores.

```bash
# Linting
uv run ruff check src/ tests/
uv run black --check src/ tests/

# Tipado
uv run mypy src/localdocsai

# Tests
uv run pytest
```

---

## Hoja de ruta

| Fase | Estado | Descripción |
|------|--------|-------------|
| 0 — Fundación | ✅ | Repo, herramientas, CI |
| 1 — Parsers | Pendiente | PDF, DOCX, XLSX |
| 2 — Chunking | Pendiente | Chunker con conciencia normativa |
| 3 — Indexación | Pendiente | FAISS + SQLite |
| 4 — LLM + Citas | Pendiente | Inferencia local + validación de citas |
| 5 — Configuración | Pendiente | Perfiles YAML |
| 6 — UI | Pendiente | App de escritorio PySide6 |
| 7 — Informes | Pendiente | Exportación Word/PDF |
| 8 — Validación Windows | Pendiente | Tests multiplataforma |
| 9 — Empaquetado | Pendiente | PyInstaller + releases automáticas |
| 10 — v1.0 | Pendiente | Documentación + release pública |

---

## Licencia

MIT — ver [LICENSE](LICENSE).

---

## Créditos

Construido con [llama-cpp-python](https://github.com/abetlen/llama-cpp-python),
[sentence-transformers](https://www.sbert.net/), [FAISS](https://faiss.ai/),
[PySide6](https://doc.qt.io/qtforpython/) y [PyMuPDF](https://pymupdf.readthedocs.io/).
