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

    args = parser.parse_args()

    if args.command == "parse":
        cmd_parse(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
