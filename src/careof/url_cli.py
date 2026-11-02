"""Fetch a page URL and pass its response body to the normal extractor."""

from __future__ import annotations

import argparse
import json
import os
import sys
from urllib.parse import urlsplit

from ._version import __version__
from .pipeline import extract

DEFAULT_TIMEOUT = 20.0
DEFAULT_MAX_BYTES = 10 * 1024 * 1024


def fetch_url(
    url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    max_bytes: int = DEFAULT_MAX_BYTES,
    user_agent: str | None = None,
) -> tuple[bytes, str | None, str]:
    """Download an HTTP(S) page with bounded time and response size."""
    parts = urlsplit(url)
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
        raise ValueError("URL must be an absolute http:// or https:// URL")
    if max_bytes <= 0:
        raise ValueError("max_bytes must be greater than zero")

    try:
        import httpx
    except ImportError as exc:  # pragma: no cover - exercised without fetch extra
        raise RuntimeError(
            "URL fetching requires the optional dependency; install with "
            '`pip install "careof[fetch]"`'
        ) from exc

    headers = {"User-Agent": user_agent or f"careof/{__version__}"}
    body = bytearray()
    with httpx.Client(
        follow_redirects=True,
        timeout=timeout,
        headers=headers,
    ) as client, client.stream("GET", url) as response:
        response.raise_for_status()
        content_length = response.headers.get("Content-Length")
        if content_length:
            try:
                declared_length = int(content_length)
            except ValueError:
                declared_length = 0
            if declared_length > max_bytes:
                raise ValueError(
                    f"response exceeds the {max_bytes}-byte size limit"
                )

        for chunk in response.iter_bytes():
            if len(body) + len(chunk) > max_bytes:
                raise ValueError(
                    f"response exceeds the {max_bytes}-byte size limit"
                )
            body.extend(chunk)

        content_type = response.headers.get("Content-Type")
        final_url = str(response.url)

    return bytes(body), content_type, final_url


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="careof-url",
        description="Fetch a web page and extract postal addresses from it.",
    )
    parser.add_argument("url", help="absolute http:// or https:// URL")
    parser.add_argument("--content-type", help="override the response content type")
    parser.add_argument("--country", help="country hint for libpostal, e.g. de or us")
    parser.add_argument("--language", help="language hint for libpostal, e.g. en or de")
    parser.add_argument(
        "--libpostal-url",
        default=os.environ.get("CAREOF_LIBPOSTAL_URL"),
        help="libpostal REST base URL (or set CAREOF_LIBPOSTAL_URL)",
    )
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    parser.add_argument("--threshold", type=float, default=0.4)
    parser.add_argument(
        "--extractor",
        choices=("auto", "gliner", "heuristic", "none"),
        default="auto",
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

    try:
        import httpx
    except ImportError:
        print(
            'careof-url: URL fetching requires the optional dependency; install with '
            '`pip install "careof[fetch]"`',
            file=sys.stderr,
        )
        return 2

    try:
        content, response_type, final_url = fetch_url(
            args.url,
            timeout=args.timeout,
            max_bytes=args.max_bytes,
        )
        addresses = extract(
            content,
            args.content_type or response_type,
            url=final_url,
            language=args.language,
            country=args.country,
            libpostal_url=args.libpostal_url,
            threshold=args.threshold,
            extractor=extractor,
            max_candidates=args.max_candidates,
            structured=not args.no_structured,
        )
    except ValueError as exc:
        print(f"careof-url: {exc}", file=sys.stderr)
        return 2
    except httpx.HTTPError as exc:
        print(f"careof-url: request failed: {exc}", file=sys.stderr)
        return 2

    rows = [address.to_dict() for address in addresses]
    if args.ndjson:
        for row in rows:
            print(json.dumps(row, ensure_ascii=False))
    else:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
