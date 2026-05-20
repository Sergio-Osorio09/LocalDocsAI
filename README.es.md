# LocalDocsAI

> App de escritorio RAG offline para consulta inteligente de documentos normativos y técnicos.

[![Tests](https://github.com/Sergio-Osorio09/LocalDocsAI/actions/workflows/tests.yml/badge.svg)](https://github.com/Sergio-Osorio09/LocalDocsAI/actions/workflows/tests.yml)
[![Licencia: MIT](https://img.shields.io/badge/Licencia-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

**[English version](README.md)**

---

## ¿Qué es LocalDocsAI?

LocalDocsAI es una aplicación de escritorio multiplataforma (PySide6) que
permite cargar una carpeta de documentos (PDF, Word, Excel) y hacer preguntas
sobre su contenido en lenguaje natural. Las respuestas se generan
**completamente en tu máquina** — no requiere conexión a internet en tiempo
de ejecución, y los documentos nunca salen de tu equipo.

Cada respuesta incluye **citas verificables** a los documentos fuente: nombre
del archivo, número de página, artículo o sección, además de un vínculo
bidireccional clickable entre cada marcador `[N]` en la respuesta y la tarjeta
de fuente correspondiente en el panel derecho.

### Características principales

- **100% offline** — embeddings e inferencia del LLM corren localmente
- **Citas por oración** — cada afirmación se vincula al chunk que mejor la
  respalda usando un score recall/precision normalizado por longitud
- **Respuestas en streaming** con botón "stop" para cancelar a mitad de la
  generación
- **Sidebar reactivo** — un chat recién creado aparece en RECIENTES al instante
  y muestra un punto cian animado mientras sigue generando, aunque cambies a
  otro chat
- **Exportación Word y PDF rica** — título, tabla de metadata, secciones Q/A
  numeradas, chips ámbar de cita, lista de fuentes con snippet + chunk_id,
  pie con paginación
- **Optimizado para español** técnico y documentos normativos
- **Configurable** — modelo, ventana de contexto, top_k de recuperación, tema —
  todo vía un archivo YAML en `%APPDATA%/localdocsai/config.yaml` (Windows) o
  `~/.local/share/localdocsai/config.yaml` (Linux/macOS)

---

## Formatos de documento soportados

| Formato | Extensión | Parser |
|---------|-----------|--------|
| PDF     | `.pdf`    | PyMuPDF |
| Word    | `.docx`   | python-docx |
| Excel   | `.xlsx`, `.xlsm` | openpyxl |

---

## Requisitos

- Windows 10/11 (x64) — objetivo principal. Linux funciona con el mismo
  install desde fuente pero todavía no se empaqueta.
- 8 GB de RAM mínimo para el modelo 3B, 16 GB recomendado para el 14B
- ~3 GB de espacio libre para el modelo Qwen 2.5 3B Q4_K_M, ~9 GB si usas
  la variante 14B
- GPU NVIDIA con CUDA opcional pero recomendada — la inferencia en CPU
  funciona pero es 3-5× más lenta

---

## Inicio rápido

### Desde el código fuente (camino actual)

```powershell
# 1. Clonar el repositorio
git clone https://github.com/Sergio-Osorio09/LocalDocsAI.git
cd LocalDocsAI

# 2. Crear el entorno virtual e instalar
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[all]"

# 3. Instalar llama-cpp-python desde el índice de wheels precompilados
#    (la build desde fuente falla en Windows por el límite MAX_PATH de 260)
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu

# 4. Descargar el LLM por defecto (Qwen 2.5 3B Instruct, ~2 GB)
python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='Qwen/Qwen2.5-3B-Instruct-GGUF', filename='qwen2.5-3b-instruct-q4_k_m.gguf', local_dir='models')"

# 5. Lanzar la UI de escritorio
python -m localdocsai ui
```

La primera vez que hagas una pregunta, el modelo de embeddings BGE-M3 (~2.3 GB)
se descarga al caché de HuggingFace. Los siguientes arranques son completamente
offline.

### Opcional: build GPU para NVIDIA

Si tienes una GPU NVIDIA reciente y CUDA instalado, reemplaza el paso 3 con el
índice de wheels CUDA para que la generación sea 3-5× más rápida:

```powershell
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu122 --force-reinstall --no-cache-dir
```

Luego sube `model.n_gpu_layers` en `config.yaml` para cargar capas a la GPU.

---

## Uso de la app

1. **Agregar una carpeta** — abre *Carpetas* (esquina inferior izquierda),
   selecciona la carpeta con los PDFs / Word / Excel. La app indexa todo
   (parse → chunk → embed → FAISS) con barra de progreso en vivo y estado
   por archivo.
2. **Haz una pregunta** en el composer abajo. La respuesta streamea con chips
   de cita `[1]`, `[2]`, … junto a cada afirmación.
3. **Click en cualquier `[N]`** para resaltar la tarjeta de fuente del panel
   derecho y viceversa. Otro click sobre la tarjeta abre el snippet del chunk.
4. **Cancela** la generación con el botón rojo ✕ del composer — la pregunta
   original vuelve al input para que la edites y reenvíes.
5. **Exportar** la conversación con el botón *Exportar*. Word (`.docx`) genera
   un informe con metadata, chips de cita y snippets por fuente; PDF (`.pdf`)
   tiene el mismo layout usando reportlab, sin necesidad de un convertidor
   externo.

### CLI

El mismo pipeline está expuesto también como CLI para uso batch:

```powershell
python -m localdocsai parse ruta\al\documento.pdf
python -m localdocsai index ruta\a\documentos\
python -m localdocsai ask  "¿Qué norma regula la odorización del gas natural?"
```

---

## Arquitectura

Ver [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) para el diseño completo.

```
Documentos → Parsers → Chunker normativo → BGE-M3 embeddings → FAISS + SQLite
                                                                       ↓
Consulta → BGE-M3 → FAISS top-k → (reranker opcional) → Qwen 2.5 ──→ Respuesta
                                                                     con citas [N]
```

---

## Desarrollo

Ver [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) para la guía de contribuidores.

```powershell
# Linting
ruff check src/ tests/
black --check src/ tests/

# Tipado
mypy src/localdocsai

# Tests
pytest
```

Actualmente pasan 216 tests; CI los corre en cada push.

---

## Hoja de ruta

| Fase | Estado | Descripción |
|------|--------|-------------|
| 0 — Fundación | ✅ | Repo, herramientas, CI |
| 1 — Parsers | ✅ | PDF, DOCX, XLSX |
| 2 — Chunking | ✅ | Chunker con conciencia normativa |
| 3 — Indexación | ✅ | FAISS + SQLite |
| 4 — LLM + Citas | ✅ | Inferencia local + enriquecimiento por oración |
| 5 — Configuración | ✅ | Perfiles YAML, diálogo de Configuración |
| 6 — UI | ✅ | App de escritorio PySide6 con el tema LocalDocsAI Prototype |
| 7 — Informes | ✅ | Exportación rica a Word + PDF |
| 8 — Validación Windows | ✅ | Fixes de paths, GPU y SQL LIKE multiplataforma |
| 9 — Empaquetado | 🔄 | Bundle portable con PyInstaller |
| 10 — v1.0 | Pendiente | Documentación + release pública |

---

## Licencia

MIT — ver [LICENSE](LICENSE).

---

## Créditos

Construido con [llama-cpp-python](https://github.com/abetlen/llama-cpp-python),
[sentence-transformers](https://www.sbert.net/), [FAISS](https://faiss.ai/),
[PySide6](https://doc.qt.io/qtforpython/), [PyMuPDF](https://pymupdf.readthedocs.io/),
[python-docx](https://python-docx.readthedocs.io/) y
[reportlab](https://www.reportlab.com/).
