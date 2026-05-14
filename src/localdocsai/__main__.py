from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# parse
# ---------------------------------------------------------------------------


def cmd_parse(args: argparse.Namespace) -> None:
    from localdocsai.parsers import get_parser

    path = Path(args.file)
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    try:
        parser = get_parser(path)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    result = parser.parse(path)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# chunk
# ---------------------------------------------------------------------------


def cmd_chunk(args: argparse.Namespace) -> None:
    from localdocsai.indexing import NormativeChunker
    from localdocsai.parsers import get_parser

    path = Path(args.file)
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    try:
        parser = get_parser(path)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    doc = parser.parse(path)
    chunker = NormativeChunker(
        max_tokens=args.max_tokens,
        overlap_tokens=args.overlap,
    )
    chunks = chunker.chunk(doc)

    output = {
        "source": str(path),
        "doc_id": chunks[0].doc_id if chunks else "",
        "total_chunks": len(chunks),
        "norm_codes": doc.norm_codes,
        "chunks": [c.to_dict() for c in chunks],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# index
# ---------------------------------------------------------------------------


def cmd_index(args: argparse.Namespace) -> None:
    import numpy as np

    from localdocsai.indexing import (
        EmbeddingModel,
        MetadataStore,
        NormativeChunker,
        VectorStore,
        file_sha256,
    )
    from localdocsai.parsers import get_parser
    from localdocsai.utils.paths import ensure_dir, get_indexes_dir, get_models_dir

    folder = Path(args.folder)
    if not folder.is_dir():
        print(f"Error: not a directory: {folder}", file=sys.stderr)
        sys.exit(1)

    indexes_dir = ensure_dir(get_indexes_dir())
    db_path = indexes_dir / "localdocsai.db"
    faiss_path = indexes_dir / "localdocsai.faiss"

    metadata_store = MetadataStore(db_path)
    vector_store = VectorStore(faiss_path)
    embedding_model = EmbeddingModel(get_models_dir())
    chunker = NormativeChunker(max_tokens=args.max_tokens, overlap_tokens=args.overlap)

    supported = {".pdf", ".docx", ".xlsx", ".xlsm"}
    files = sorted(f for f in folder.rglob("*") if f.suffix.lower() in supported)

    if not files:
        print(f"No supported documents found in {folder}")
        return

    print(f"Found {len(files)} document(s). Starting indexing...\n")

    indexed = skipped = errors = 0

    for i, file_path in enumerate(files, 1):
        prefix = f"[{i:2d}/{len(files)}]"
        file_hash = file_sha256(file_path)

        if metadata_store.is_indexed(file_hash):
            print(f"{prefix} SKIP  {file_path.name}")
            skipped += 1
            continue

        print(f"{prefix} INDEX {file_path.name} ...", end="", flush=True)

        try:
            parser = get_parser(file_path)
            doc = parser.parse(file_path)
            chunks = chunker.chunk(doc)

            if not chunks:
                print(" (no chunks produced)")
                continue

            texts = [c.text for c in chunks]
            embeddings = embedding_model.embed(texts)

            doc_db_id = metadata_store.add_document(doc, file_hash)
            chunk_ids = metadata_store.add_chunks(doc_db_id, chunks)
            vector_store.add(embeddings, np.array(chunk_ids, dtype=np.int64))

            print(f" {len(chunks)} chunks")
            indexed += 1

        except Exception as exc:
            print(f" ERROR: {exc}")
            errors += 1

    vector_store.save()

    print(
        f"\nDone. Indexed: {indexed} | Skipped: {skipped} | Errors: {errors}"
        f" | Total vectors: {vector_store.total_vectors}"
    )


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


def cmd_search(args: argparse.Namespace) -> None:
    from localdocsai.indexing import EmbeddingModel, MetadataStore, VectorStore
    from localdocsai.utils.paths import get_indexes_dir, get_models_dir

    indexes_dir = get_indexes_dir()
    db_path = indexes_dir / "localdocsai.db"
    faiss_path = indexes_dir / "localdocsai.faiss"

    if not db_path.exists() or not faiss_path.exists():
        print(
            "No index found. Run 'localdocsai index <folder>' first.",
            file=sys.stderr,
        )
        sys.exit(1)

    metadata_store = MetadataStore(db_path)
    vector_store = VectorStore(faiss_path)
    embedding_model = EmbeddingModel(get_models_dir())

    print(f"Searching for: {args.query!r}\n")
    query_embedding = embedding_model.embed([args.query])[0]
    results = vector_store.search(query_embedding, top_k=args.top_k)

    if not results:
        print("No results found.")
        return

    for rank, (chunk_id, score) in enumerate(results, 1):
        chunk = metadata_store.get_chunk(chunk_id)
        if not chunk:
            continue
        print(f"[{rank}] score={score:.4f}  doc={chunk['doc_id']}  p.{chunk['page']}")
        if chunk["section_path"]:
            print(f"    section: {chunk['section_path']}")
        if chunk["norm_code"]:
            print(f"    norm:    {chunk['norm_code']}")
        print(f"    {chunk['text'][:200]!r}")
        print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="localdocsai",
        description="LocalDocsAI — offline RAG for normative documents",
    )
    sub = parser.add_subparsers(dest="command")

    # parse
    p = sub.add_parser("parse", help="Parse a document and print JSON")
    p.add_argument("file", help="Path to PDF, DOCX, or XLSX")

    # chunk
    c = sub.add_parser("chunk", help="Parse and chunk a document, print JSON")
    c.add_argument("file", help="Path to document")
    c.add_argument("--max-tokens", type=int, default=800, metavar="N")
    c.add_argument("--overlap", type=int, default=100, metavar="N")

    # index
    ix = sub.add_parser("index", help="Index a folder of documents")
    ix.add_argument("folder", help="Folder containing documents to index")
    ix.add_argument("--max-tokens", type=int, default=800, metavar="N")
    ix.add_argument("--overlap", type=int, default=100, metavar="N")

    # search
    s = sub.add_parser("search", help="Semantic search over the indexed documents")
    s.add_argument("query", help="Natural language query")
    s.add_argument("--top-k", type=int, default=5, metavar="K")

    args = parser.parse_args()

    if args.command == "parse":
        cmd_parse(args)
    elif args.command == "chunk":
        cmd_chunk(args)
    elif args.command == "index":
        cmd_index(args)
    elif args.command == "search":
        cmd_search(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
