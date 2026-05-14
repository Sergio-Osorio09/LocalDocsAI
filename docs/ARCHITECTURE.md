# LocalDocsAI — Documento de Arquitectura

> Sistema RAG offline para consulta inteligente de documentos normativos y técnicos, distribuible como aplicación portable multiplataforma y publicable como proyecto open source.

**Versión del documento:** 0.1 (inicial)
**Estado del proyecto:** Pre-desarrollo
**Cliente piloto:** Osinergmin (consulta normativa sobre distribución de gas natural)
**Plataforma de desarrollo:** Debian 13 + Claude Code
**Plataforma objetivo de despliegue:** Windows 10/11 (portable) y Linux

---

## 1. Visión y objetivos

### 1.1 Qué es LocalDocsAI

Una aplicación de escritorio que permite a un usuario cargar un conjunto de documentos (PDF, Word, Excel) y realizar consultas en lenguaje natural sobre su contenido. Las respuestas se generan localmente mediante un modelo de lenguaje (LLM) que se ejecuta en la propia máquina del usuario, y **cada respuesta incluye obligatoriamente las citas a los documentos y páginas de origen**.

### 1.2 Principios de diseño

| Principio | Implicancia |
|-----------|-------------|
| **100% offline** | Sin conexión a internet en runtime. Toda la inferencia ocurre localmente. |
| **Trazabilidad obligatoria** | Cada afirmación de la IA va vinculada a su fuente (documento + página + sección). |
| **Sin instalación pesada** | Distribución portable: descomprimir y ejecutar. Sin admin, sin Python en la máquina destino. |
| **Multiplataforma** | Desarrollo en Linux, distribución para Linux y Windows. |
| **Open source** | Genérico y configurable. Cualquier organización debe poder usarlo con sus propios documentos. |
| **Privacy-first** | Los documentos del usuario nunca salen de su máquina. |
| **Configuración sobre código** | Branding, colores, plantillas, modelos: todo en archivos de configuración. |

### 1.3 Casos de uso objetivo

- Consulta de normativa regulatoria (caso Osinergmin: DS, RCDs, manuales NFPA).
- Consulta de manuales técnicos internos de una organización.
- Apoyo a estudios jurídicos para búsqueda en jurisprudencia local.
- Documentación académica e investigación bibliográfica.
- Bases de conocimiento corporativas privadas.

---

## 2. Arquitectura de alto nivel

### 2.1 Visión por capas

```
┌─────────────────────────────────────────────────────────┐
│                     UI Layer (PySide6)                  │
│   Chat | Folder Manager | Settings | Report Export      │
└───────────────────────┬─────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────┐
│                  Application Core                       │
│        Pipeline · Citation · Session · Config           │
└──┬─────────────────────────────────────────────────┬────┘
   │                                                 │
┌──▼────────────────┐                  ┌─────────────▼──┐
│   Ingestion       │                  │   Inference    │
│  ─────────────    │                  │  ────────────  │
│  Parsers          │                  │   Retriever    │
│  Chunker          │                  │   Reranker     │
│  Embedder         │                  │   LLM Client   │
│  Indexer          │                  │   Prompter     │
└──┬────────────────┘                  └────────┬───────┘
   │                                            │
┌──▼──────────────────────────────────────────  ▼───────┐
│                   Storage Layer                       │
│   FAISS index  ·  SQLite metadata  ·  Model files     │
└───────────────────────────────────────────────────────┘
```

### 2.2 Flujo de datos: indexación

```
Carpeta del usuario
       │
       ▼
[ Parser PDF/DOCX/XLSX ] ──► texto plano + metadata cruda
       │
       ▼
[ Chunker normativo ] ──► chunks con estructura preservada
       │                  (artículo, página, archivo, código de norma)
       ▼
[ Embedder BGE-M3 ] ──► vector de 1024 dim por chunk
       │
       ▼
[ Persistencia ] ──► FAISS (vectores) + SQLite (metadata)
```

### 2.3 Flujo de datos: consulta

```
Pregunta del usuario
       │
       ▼
[ Embedder ] ──► vector de la pregunta
       │
       ▼
[ Retriever FAISS ] ──► top-K chunks similares
       │
       ▼
[ Reranker (opcional) ] ──► top-N chunks reordenados
       │
       ▼
[ Prompt builder ] ──► prompt con chunks + instrucciones de citación
       │
       ▼
[ LLM local (llama.cpp) ] ──► respuesta con citas marcadas
       │
       ▼
[ Citation validator ] ──► verifica que las citas existan realmente
       │
       ▼
Respuesta al usuario + fuentes verificables
```

---

## 3. Stack tecnológico

### 3.1 Lenguaje y entorno

- **Python 3.11+** como lenguaje principal.
- **uv** como gestor de dependencias (rápido, moderno, reemplaza pip + venv).
- **ruff** y **black** para linting y formateo.
- **mypy** para tipado estricto.
- **pytest** para tests.

### 3.2 Componentes funcionales

| Función | Librería | Razón |
|---------|----------|-------|
| Parseo PDF | **PyMuPDF** (`pymupdf`) | Mejor extracción de texto y manejo de layout que pypdf. |
| Parseo Word | **python-docx** | Estándar de facto. |
| Parseo Excel | **openpyxl** | Soporta `.xlsx` y `.xlsm`. |
| Embeddings | **sentence-transformers** + **BGE-M3** | Multilingüe robusto para español técnico. |
| Vector store | **FAISS** (`faiss-cpu`) | Local, rápido, sin servidor. |
| Metadata DB | **SQLite** (stdlib) | Cero configuración, archivo único. |
| LLM runtime | **llama-cpp-python** | Modelos GGUF cuantizados, eficiente en CPU y GPU. |
| Modelo LLM | **Qwen 2.5 14B Instruct Q4_K_M** | Mejor opción para español dentro del presupuesto de 16 GB RAM. |
| UI | **PySide6** | Multiplataforma, look nativo, soporte LTS de Qt. |
| Generación Word | **python-docx** + skill `docx` | Plantillas, estilos, citas embebidas. |
| Generación PDF | **reportlab** o **WeasyPrint** | A decidir en fase 7. |

### 3.3 Empaquetado y CI/CD

- **PyInstaller** (modo `--onedir`) para empaquetado.
- **GitHub Actions** para builds automáticos en Linux y Windows.
- **Inno Setup** (opcional, fase posterior) para instalador Windows firmado.

---

## 4. Estructura del repositorio

```
LocalDocsAI/
├── .claude/
│   ├── skills/                       # Skills personalizadas del proyecto
│   │   ├── rag-architecture/SKILL.md
│   │   ├── citation-format/SKILL.md
│   │   ├── chunking-strategy/SKILL.md
│   │   ├── cross-platform-paths/SKILL.md
│   │   └── windows-packaging/SKILL.md
│   └── settings.json
├── .github/
│   └── workflows/
│       ├── tests.yml
│       ├── build-linux.yml
│       └── build-windows.yml
├── docs/
│   ├── ARCHITECTURE.md               # Este documento
│   ├── ROADMAP.md
│   ├── DEVELOPMENT.md                # Guía para contribuidores
│   ├── USER_GUIDE.md                 # Manual de usuario (inglés)
│   └── USER_GUIDE.es.md              # Manual de usuario (español)
├── src/
│   └── localdocsai/
│       ├── __init__.py
│       ├── __main__.py               # Entry point: python -m localdocsai
│       ├── config/
│       │   ├── settings.py
│       │   └── default_config.yaml
│       ├── parsers/
│       │   ├── base.py
│       │   ├── pdf_parser.py
│       │   ├── docx_parser.py
│       │   └── xlsx_parser.py
│       ├── indexing/
│       │   ├── chunker.py
│       │   ├── embeddings.py
│       │   ├── vector_store.py
│       │   └── metadata_store.py
│       ├── retrieval/
│       │   ├── retriever.py
│       │   └── reranker.py
│       ├── llm/
│       │   ├── client.py
│       │   └── prompts.py
│       ├── reports/
│       │   ├── word_report.py
│       │   └── pdf_report.py
│       ├── ui/
│       │   ├── main_window.py
│       │   ├── chat_widget.py
│       │   ├── folder_manager.py
│       │   ├── settings_dialog.py
│       │   └── themes/
│       ├── core/
│       │   ├── pipeline.py
│       │   ├── citation.py
│       │   └── session.py
│       └── utils/
│           ├── paths.py              # Helpers cross-platform
│           └── logging.py
├── tests/
│   ├── fixtures/                     # Documentos pequeños de prueba (no reales del cliente)
│   ├── test_parsers/
│   ├── test_indexing/
│   ├── test_retrieval/
│   └── test_llm/
├── scripts/
│   ├── download_models.py            # Descarga el LLM y embeddings al primer uso
│   ├── build_release.sh
│   └── dev_setup.sh
├── resources/
│   ├── icons/
│   ├── themes/
│   └── report_templates/
├── samples/                          # gitignored - documentos del usuario para pruebas locales
├── .gitignore
├── .gitattributes                    # eol=lf para evitar problemas Linux/Windows
├── pyproject.toml
├── uv.lock
├── README.md                         # Inglés
├── README.es.md                      # Español
├── LICENSE                           # MIT
├── CHANGELOG.md
└── CLAUDE.md                         # Contexto del proyecto para Claude Code
```

---

## 5. Decisiones de diseño clave

### 5.1 Chunking respetando estructura jurídica

Los documentos normativos tienen estructura jerárquica (artículos, numerales, anexos). Un chunker genérico por tokens pierde precisión. El chunker propio detecta patrones como:

- `Artículo N°` / `Artículo N` (con o sin tilde)
- `RCD N° XXX-AAAA-OS/CD`
- `D.S. N° XXX-AAAA-EM`
- Secciones numeradas (`1.`, `1.1`, `1.1.1`)
- Anexos (`ANEXO N°`)

Cada chunk lleva en su metadata el contexto jerárquico completo (norma → capítulo → artículo) para que las citas sean precisas.

### 5.2 Citas verificables, no inventadas

El prompt al LLM obliga a citar **exclusivamente** los IDs de chunk que se le proveyeron. Un validador post-respuesta verifica que cada cita exista realmente en los chunks del retrieval; si el modelo inventa una cita (alucina), se marca o se reintenta.

Formato interno de cita: `[doc_id:chunk_id]` que la UI traduce a `(RCD N° 029-2016-OS/CD, Art. 5, p. 12)`.

### 5.3 Minigrupos de carpetas

Concepto del usuario: agrupar carpetas indexadas bajo un nombre lógico para filtrar búsquedas. Implementación: cada chunk en SQLite lleva una columna `groups` (tags). Al consultar, se filtra el retrieval por los grupos seleccionados antes de pasar al LLM.

Tres modos de consulta:
1. **Todas las fuentes** indexadas.
2. **Selección de minigrupos** (uno o varios).
3. **Carpeta específica ad-hoc** indicada en el momento.

### 5.4 Configuración por archivo, no por código

Un `config.yaml` que el usuario puede editar sin tocar código:

```yaml
app:
  name: "LocalDocsAI"
  language: "es"           # i18n: es, en
  theme: "dark"            # dark, light, custom

model:
  llm: "qwen2.5-14b-instruct-q4_k_m"
  embeddings: "BAAI/bge-m3"
  context_window: 8192
  max_tokens: 1024

retrieval:
  top_k: 10
  rerank: true
  min_similarity: 0.5

ui:
  primary_color: "#1a73e8"
  accent_color: "#fbbc04"
  logo_path: "resources/logo.png"

reports:
  default_format: "docx"
  template: "resources/report_templates/default.docx"
  font: "Arial"
```

Esto es lo que permite que Osinergmin tenga su `config.yaml` específico (con sus colores y su plantilla) sin que el código del repo lo sepa.

### 5.5 Paths multiplataforma desde el día 1

Regla estricta: **todo path en código va por `pathlib.Path`**, nunca por strings concatenados. Nombres de archivo normalizados a minúsculas internamente para evitar problemas de case-sensitivity entre Linux y Windows.

---

## 6. Plan de desarrollo por fases

> Las fases están diseñadas para que cada una termine en algo **probable y demostrable**. Al final de cada fase tienes un avance funcional, no solo código a medio hacer.

### Resumen de fases

| Fase | Nombre | Duración estimada | Entregable demostrable |
|------|--------|-------------------|------------------------|
| 0 | Fundación del proyecto | 1-2 días | Repo configurado, skills, CI básico. |
| 1 | Parsers de documentos | 3-4 días | CLI que parsea PDF/Word/Excel y muestra texto + metadata. |
| 2 | Chunking inteligente | 2-3 días | CLI que trocea documentos respetando estructura. |
| 3 | Indexación vectorial | 3-4 días | CLI que indexa una carpeta y permite búsqueda semántica básica. |
| 4 | LLM y generación con citas | 4-5 días | CLI que responde preguntas en español con citas verificables. |
| 5 | Sistema de configuración | 1-2 días | `config.yaml` funcional, perfiles, temas. |
| 6 | UI con PySide6 | 6-8 días | Aplicación gráfica completa: chat, minigrupos, drag & drop. |
| 7 | Generación de informes | 2-3 días | Exportación Word y PDF desde el chat. |
| 8 | Validación cross-platform | 2-3 días | App funcionando en Windows VM. |
| 9 | Empaquetado y CI/CD | 2-3 días | Releases automáticas en GitHub para Linux y Windows. |
| 10 | Documentación y v1.0 | 2-3 días | README, manuales, primera release pública. |

**Total estimado:** 28-40 días de trabajo efectivo.

---

### Fase 0 — Fundación del proyecto

**Objetivo:** dejar el terreno listo para que Claude Code y tú tengan máxima eficiencia desde el primer commit.

**Tareas:**
- [ ] `git init` y crear repositorio en GitHub (público o privado al inicio).
- [ ] Crear `pyproject.toml` con dependencias mínimas usando `uv init`.
- [ ] Crear estructura de carpetas vacía según sección 4.
- [ ] Escribir `CLAUDE.md` raíz con convenciones del proyecto.
- [ ] Crear las 5 skills personalizadas en `.claude/skills/` (mínimo el SKILL.md de cada una).
- [ ] Instalar skills de Anthropic: `docx`, `pdf`, `xlsx`, `pdf-reading`.
- [ ] Configurar `.gitignore` (modelos, índices, samples, venv, `__pycache__`, etc.).
- [ ] Configurar `.gitattributes` con `* text=auto eol=lf`.
- [ ] Configurar `ruff`, `black`, `mypy` en `pyproject.toml`.
- [ ] Crear `LICENSE` (MIT recomendado).
- [ ] Esqueleto de `README.md` y `README.es.md`.
- [ ] Primer workflow de GitHub Actions: `tests.yml` que solo corre `ruff` y `pytest` (vacío por ahora).

**Criterio de salida:** un commit inicial al repo con CI verde corriendo.

---

### Fase 1 — Parsers de documentos

**Objetivo:** convertir cualquier documento de entrada en texto plano con metadata estructurada.

**Tareas:**
- [ ] Crear módulo `parsers/base.py` con la interfaz abstracta `BaseParser`.
- [ ] Implementar `pdf_parser.py` con PyMuPDF: extraer texto por página, preservar número de página, detectar headers/footers para limpiarlos.
- [ ] Implementar `docx_parser.py` con python-docx: extraer texto preservando estructura (títulos, párrafos, tablas).
- [ ] Implementar `xlsx_parser.py` con openpyxl: extraer celdas como texto, una hoja por documento lógico.
- [ ] Detectar y limpiar contenido espurio (números de página, marcas de agua repetidas).
- [ ] Detectar códigos de norma en el contenido: `RCD N° XXX-AAAA-OS/CD`, `D.S. N° XXX-AAAA-EM`, etc.
- [ ] CLI `localdocsai parse <archivo>` que vuelca el resultado en JSON para inspección.
- [ ] Tests unitarios con fixtures pequeñas (no usar documentos reales del cliente).

**Criterio de salida:** podés parsear los ~30 documentos de `Moises_Proyecto/` y obtener salida JSON consistente con texto + páginas + códigos de norma detectados.

---

### Fase 2 — Chunking inteligente

**Objetivo:** trocear documentos en chunks que respeten la estructura jurídica.

**Tareas:**
- [ ] Crear `indexing/chunker.py` con estrategia configurable.
- [ ] Detectar patrones de artículo y numeral para no cortar en medio de uno.
- [ ] Implementar solapamiento (overlap) configurable entre chunks.
- [ ] Cada chunk lleva metadata: `{doc_id, page, section_path, norm_code, chunk_id, text}`.
- [ ] Tamaño objetivo de chunk: ~500-800 tokens, configurable.
- [ ] CLI `localdocsai chunk <archivo>` que muestra los chunks generados.
- [ ] Tests con fixtures de documentos normativos sintéticos.

**Criterio de salida:** los chunks generados sobre los PDFs reales preservan la unidad lógica (no se parte un artículo a la mitad) y la metadata es completa.

---

### Fase 3 — Indexación vectorial

**Objetivo:** convertir chunks en vectores y construir el índice persistente.

**Tareas:**
- [ ] Crear `indexing/embeddings.py` que carga BGE-M3 vía sentence-transformers.
- [ ] Crear `indexing/vector_store.py` con wrapper sobre FAISS (IndexFlatIP para empezar).
- [ ] Crear `indexing/metadata_store.py` con SQLite: tabla `chunks` (id, doc_id, page, text, group_tags, ...) y `documents` (id, path, hash, indexed_at).
- [ ] Implementar deduplicación por hash de archivo (no reindexar lo ya indexado).
- [ ] Script `download_models.py` que baja BGE-M3 a una carpeta local en primera ejecución.
- [ ] CLI `localdocsai index <carpeta>` con barra de progreso.
- [ ] CLI `localdocsai search <consulta>` que muestra los top-K chunks similares (sin LLM aún).
- [ ] Tests de regresión.

**Criterio de salida:** podés indexar la carpeta `Moises_Proyecto/` (puede tardar varios minutos la primera vez) y luego hacer búsquedas semánticas que devuelven resultados coherentes en segundos.

---

### Fase 4 — LLM y generación con citas

**Objetivo:** integrar el modelo de lenguaje local y forzar respuestas con citas verificables. **Esta es la fase más crítica.**

**Tareas:**
- [ ] Crear `llm/client.py` con wrapper sobre llama-cpp-python.
- [ ] Crear `llm/prompts.py` con el sistema de prompts en español.
- [ ] Diseñar prompt que obligue al modelo a citar `[chunk_id]` solo de los chunks provistos.
- [ ] Crear `core/citation.py` con validador post-respuesta: verifica que cada cita exista; si no, reintenta o marca.
- [ ] Implementar la "traducción" de citas internas a citas legibles (`[chunk_id]` → `(RCD N° XXX, Art. Y, p. Z)`).
- [ ] Script `download_models.py` también baja el modelo Qwen 2.5 14B Q4_K_M (~8 GB).
- [ ] CLI `localdocsai ask "pregunta"` que devuelve respuesta + citas verificadas.
- [ ] Pruebas extensivas con preguntas reales del dominio normativo.

**Criterio de salida:** podés hacer preguntas como "¿qué norma regula la odorización del gas natural?" y obtener respuestas correctas con citas precisas a las normas reales.

---

### Fase 5 — Sistema de configuración

**Objetivo:** parametrizar todo lo personalizable para que el proyecto sea verdaderamente reusable.

**Tareas:**
- [ ] Crear `config/settings.py` con clase `Settings` basada en pydantic.
- [ ] Definir `default_config.yaml` con todos los parámetros documentados.
- [ ] Sistema de perfiles: el usuario puede tener varios `config.yaml` y cambiar entre ellos.
- [ ] Validación de configuración al arrancar (errores claros si falta algo).
- [ ] Documentar cada parámetro en `docs/CONFIGURATION.md`.

**Criterio de salida:** podés crear un `osinergmin_profile.yaml` con colores, plantilla y modelo específicos, y la app lo respeta sin tocar código.

---

### Fase 6 — UI con PySide6

**Objetivo:** envolver toda la funcionalidad CLI en una aplicación gráfica usable.

**Tareas:**
- [ ] `main_window.py`: ventana principal con sidebar (chats anclados, minigrupos) y área central de chat.
- [ ] `chat_widget.py`: render de mensajes, bubble del usuario y de la IA, indicador de "pensando".
- [ ] `folder_manager.py`: UI para agregar carpetas, crear minigrupos, drag & drop de archivos sueltos.
- [ ] Streaming de respuestas del LLM (tokens apareciendo en vivo).
- [ ] `settings_dialog.py`: editor de configuración con UI.
- [ ] `themes/`: sistema de temas oscuro/claro/personalizado vía QSS.
- [ ] Sidebar de fuentes: clic en una cita abre el PDF original en la página correspondiente.
- [ ] Internacionalización: textos en archivos `.ts` traducibles (mínimo es + en).
- [ ] Indicador de progreso para indexaciones largas (no bloquear UI: usar QThread).

**Criterio de salida:** podés usar la app sin tocar la terminal: agregar carpetas, indexarlas, hacer preguntas, ver citas linkeables.

---

### Fase 7 — Generación de informes

**Objetivo:** permitir al usuario exportar una conversación (o una respuesta) como informe Word o PDF.

**Tareas:**
- [ ] `reports/word_report.py`: genera `.docx` desde una conversación, con plantilla configurable.
- [ ] Solo incluye las respuestas, no las preguntas (según requisito de Osinergmin).
- [ ] Citas en el informe como notas al pie o paréntesis (configurable).
- [ ] Header/footer con logo, fecha, número de página.
- [ ] Soporte de varias plantillas en `resources/report_templates/`.
- [ ] `reports/pdf_report.py`: convierte a PDF (vía LibreOffice headless o reportlab directo).
- [ ] Botón "Exportar informe" en la UI con selección de formato.

**Criterio de salida:** desde un chat podés exportar un `.docx` con formato Arial, con la plantilla del cliente, y verlo en Word.

---

### Fase 8 — Validación cross-platform

**Objetivo:** confirmar que la app funciona idéntica en Windows.

**Tareas:**
- [ ] Configurar VM de Windows 11 (VirtualBox o VMware).
- [ ] Clonar repo en la VM y correr la app desde código fuente.
- [ ] Lista de verificación: parseo, indexación, consulta, exportación, drag & drop, paths, idioma.
- [ ] Corregir todas las incompatibilidades detectadas.
- [ ] Verificar comportamiento del file dialog, el system tray, las notificaciones.

**Criterio de salida:** la app corre en Windows exactamente como en Linux, sin diferencias funcionales.

---

### Fase 9 — Empaquetado y CI/CD

**Objetivo:** convertir el código en ejecutables descargables, generados automáticamente en cada release.

**Tareas:**
- [ ] Crear `localdocsai.spec` para PyInstaller (modo `--onedir`).
- [ ] Workflow `build-linux.yml`: PyInstaller en Ubuntu, genera `.tar.gz`.
- [ ] Workflow `build-windows.yml`: PyInstaller en `windows-latest`, genera `.zip`.
- [ ] Workflow se dispara con tags `v*.*.*` y publica artifacts en GitHub Releases.
- [ ] Decidir si los modelos van empaquetados o se descargan al primer arranque (sugerencia: descarga en primer arranque desde HuggingFace, con fallback a copia manual).
- [ ] Test manual: descargar el ZIP de releases en una máquina Windows limpia, descomprimir, ejecutar.

**Criterio de salida:** un usuario externo puede ir a la página de releases del repo, bajar el ZIP, descomprimirlo y usarlo sin instalar nada.

---

### Fase 10 — Documentación y release v1.0

**Objetivo:** hacer el proyecto presentable, usable por terceros, y publicarlo.

**Tareas:**
- [ ] `README.md` (inglés) y `README.es.md` con: qué es, screenshots, requisitos, instalación, uso básico.
- [ ] `docs/USER_GUIDE.md` con flujos completos.
- [ ] `docs/DEVELOPMENT.md` con guía para contribuidores.
- [ ] `CHANGELOG.md` con entradas para v1.0.
- [ ] Screenshots/GIFs del producto funcionando.
- [ ] Crear tag `v1.0.0` → trigger del workflow de release.
- [ ] Anunciar en redes o foros relevantes (opcional).

**Criterio de salida:** v1.0.0 publicada, página del repo con README atractivo, binarios descargables.

---

## 7. Estrategia de testing

### 7.1 Tests unitarios

- Cada módulo (`parsers`, `chunker`, `embeddings`, etc.) tiene sus tests con fixtures sintéticas pequeñas.
- Coverage objetivo: >70% en módulos core.
- Corren en GitHub Actions en cada PR.

### 7.2 Tests de integración

- Pipeline end-to-end con documentos pequeños (10-20 chunks).
- Validación de citas: el sistema nunca debe devolver una cita que no exista.

### 7.3 Tests manuales

- Lista de preguntas-respuestas conocidas sobre `Moises_Proyecto/` que se ejecutan al final de cada fase relevante para detectar regresiones de calidad.

### 7.4 Test de plataforma

- Linux: corre nativo en Debian de desarrollo.
- Windows: VM con Windows 11, validación manual al cerrar cada fase mayor (5, 6, 8).

---

## 8. Distribución y release

### 8.1 Modelo de distribución

**v1.0 a v1.x:** ZIP portable.
- Usuario descarga `LocalDocsAI-vX.Y.Z-windows-x64.zip` o `-linux-x64.tar.gz` desde GitHub Releases.
- Descomprime en cualquier carpeta de su sistema.
- Doble clic en `LocalDocsAI.exe` (Windows) o `./LocalDocsAI` (Linux).
- En el primer arranque, descarga los modelos (~10 GB) a una carpeta local; los siguientes arranques son instantáneos.

**v2.x (opcional, más adelante):** instalador Inno Setup firmado para Windows. Esto elimina las alertas de SmartScreen y se siente más profesional, pero requiere certificado de firma de código (~USD 300/año).

### 8.2 Versionado

Semantic Versioning (`MAJOR.MINOR.PATCH`):
- `MAJOR`: cambios incompatibles (cambio de formato de índice, breaking changes de API).
- `MINOR`: funcionalidad nueva compatible.
- `PATCH`: correcciones de bugs.

---

## 9. Riesgos identificados y mitigaciones

| Riesgo | Mitigación |
|--------|------------|
| El LLM 14B es lento sin GPU. | Ofrecer también opción 7B para hardware modesto. |
| Antivirus marcan el `.exe` como sospechoso. | Documentar caso. Plan a futuro: certificado de firma. |
| Hugging Face cambia URLs de modelos. | Pinear hashes específicos. Permitir descarga manual. |
| Documentos del cliente filtrados al repo público. | `.gitignore` estricto. Carpeta `samples/` siempre gitignored. |
| Citas alucinadas (LLM inventa fuentes). | Validador post-respuesta obligatorio (Fase 4). |
| Diferencias Linux/Windows descubiertas tarde. | Pruebas en Windows desde Fase 6, no esperar a la 8. |

---

## 10. Glosario

| Término | Significado |
|---------|-------------|
| **RAG** | Retrieval-Augmented Generation. Arquitectura donde el LLM responde basándose en documentos recuperados, no solo en su conocimiento interno. |
| **Chunk** | Fragmento de texto resultante de trocear un documento, unidad básica de indexación y recuperación. |
| **Embedding** | Vector numérico que representa el significado semántico de un texto. |
| **FAISS** | Facebook AI Similarity Search. Librería para búsqueda eficiente en grandes conjuntos de vectores. |
| **GGUF** | Formato de archivo para modelos LLM cuantizados, optimizado para llama.cpp. |
| **Cuantización** | Técnica para reducir el tamaño de un modelo (e.g., Q4 = 4 bits por peso) a costa de algo de precisión. |
| **Minigrupo** | Agrupación lógica de carpetas indexadas, configurada por el usuario para filtrar búsquedas. |
| **Citación verificable** | Cita que el sistema valida que existe realmente en los chunks recuperados, no inventada por el LLM. |

---

## 11. Próximos pasos inmediatos

1. Renombrar la carpeta de trabajo de `LocalDocsIA` a `LocalDocsAI` (o ajustar el nombre del proyecto si prefieres mantener `LocalDocsIA`).
2. Comenzar Fase 0 con Claude Code: crear estructura, escribir `CLAUDE.md`, crear las skills personalizadas.
3. Hacer el primer commit y push al repo de GitHub (privado al inicio si lo prefieres, lo puedes hacer público al llegar a v1.0).

---

*Documento mantenido por: [tu nombre]. Última actualización: fase de planificación.*
