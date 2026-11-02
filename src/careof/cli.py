"""Command line entry point: ``careof page.html``."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from ._version import __version__
from .pipeline import extract, extract_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="careof",
        description="Find and parse postal addresses in HTML, Markdown, or text.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument("path", nargs="?", help="input file, or - to read stdin")
    parser.add_argument("--content-type", help="override content-type detection")
    parser.add_argument("--url", help="base URL, used for content-type hints and metadata")
    parser.add_argument("--country", help="country hint for libpostal, e.g. ph or us")
    parser.add_argument("--language", help="language hint for libpostal, e.g. en")
    parser.add_argument(
        "--libpostal-url",
        default=os.environ.get("CAREOF_LIBPOSTAL_URL"),
        help="libpostal REST base URL (or set CAREOF_LIBPOSTAL_URL)",
    )
    parser.add_argument("--threshold", type=float, default=0.4)
    parser.add_argument(
        "--extractor",
        choices=("auto", "gliner", "heuristic", "none"),
        default="auto",
        help="'none' returns only structured matches (JSON-LD, <address>, ...)",
    )
    parser.add_argument("--max-candidates", type=int, default=40)
    parser.add_argument("--no-structured", action="store_true")
    parser.add_argument("--ndjson", action="store_true", help="one JSON object per line")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    extractor: str | None = args.extractor
    if extractor == "none":
        extractor = None

    kwargs = {
        "language": args.language,
        "country": args.country,
        "libpostal_url": args.libpostal_url,
        "threshold": args.threshold,
        "extractor": extractor,
        "max_candidates": args.max_candidates,
        "structured": not args.no_structured,
    }

    if args.path in (None, "-"):
        data = sys.stdin.buffer.read()
        if not data:
            print("careof: no input", file=sys.stderr)
            return 2
        addresses = extract(
            data, args.content_type, url=args.url, **kwargs
        )
    else:
        path = Path(args.path)
        if not path.exists():
            print(f"careof: no such file: {path}", file=sys.stderr)
            return 2
        addresses = extract_file(
            path, content_type=args.content_type, url=args.url, **kwargs
        )

    rows = [address.to_dict() for address in addresses]
    if args.ndjson:
        for row in rows:
            print(json.dumps(row, ensure_ascii=False))
    else:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
