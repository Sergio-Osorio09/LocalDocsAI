from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


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


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="localdocsai",
        description="LocalDocsAI — offline RAG for normative documents",
    )
    subparsers = parser.add_subparsers(dest="command")

    parse_cmd = subparsers.add_parser(
        "parse",
        help="Parse a document (PDF, DOCX, XLSX) and print JSON",
    )
    parse_cmd.add_argument("file", help="Path to the document")

    chunk_cmd = subparsers.add_parser(
        "chunk",
        help="Parse and chunk a document, print JSON with chunk list",
    )
    chunk_cmd.add_argument("file", help="Path to the document")
    chunk_cmd.add_argument(
        "--max-tokens",
        type=int,
        default=800,
        metavar="N",
        help="Maximum tokens per chunk (default: 800)",
    )
    chunk_cmd.add_argument(
        "--overlap",
        type=int,
        default=100,
        metavar="N",
        help="Overlap tokens between consecutive chunks (default: 100)",
    )

    args = parser.parse_args()

    if args.command == "parse":
        cmd_parse(args)
    elif args.command == "chunk":
        cmd_chunk(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
