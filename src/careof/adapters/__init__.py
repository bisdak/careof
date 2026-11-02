"""Content-type detection and adapter dispatch."""

from __future__ import annotations

from pathlib import Path

import re2

from .base import Document
from .html import parse_html
from .markdown import parse_markdown
from .text import parse_text

_HTML_HINT = re2.compile(r"(?is)<!doctype\s+html|<html[\s>]|<body[\s>]|<div[\s>]|<p[\s>]")
_MD_HINT = re2.compile(
    r"(?m)^[ \t]*(?:#{1,6}[ \t]|```|~~~|[-*+][ \t]+\S|\d{1,3}[.)][ \t]+\S)"
    r"|\*\*[^*\n]+\*\*|__[^_\n]+__|\[[^\]\n]+\]\([^)\n]+\)"
)

_SUFFIXES = {
    ".html": "text/html",
    ".htm": "text/html",
    ".xhtml": "application/xhtml+xml",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".mdown": "text/markdown",
    ".txt": "text/plain",
    ".text": "text/plain",
}

_ALIASES = {
    "text/html": "text/html",
    "application/xhtml+xml": "text/html",
    "application/xml": "text/html",
    "text/markdown": "text/markdown",
    "text/x-markdown": "text/markdown",
    "text/plain": "text/plain",
    "text/*": "text/plain",
}


def detect_content_type(
    source: str | bytes,
    content_type: str | None = None,
    url: str | None = None,
) -> str:
    if content_type:
        media = content_type.split(";", 1)[0].strip().lower()
        if media in _ALIASES:
            return _ALIASES[media]
        if media.endswith(("+xml", "+html")):
            return "text/html"
        if media.startswith("text/"):
            return "text/plain"

    if url:
        suffix = Path(url.split("?", 1)[0]).suffix.lower()
        if suffix in _SUFFIXES:
            return _SUFFIXES[suffix]

    sample = source[:4000]
    if isinstance(sample, bytes):
        sample = sample.decode("utf-8", "replace")
    if _HTML_HINT.search(sample):
        return "text/html"
    if _MD_HINT.search(sample):
        return "text/markdown"
    return "text/plain"


def load_document(
    source: str | bytes,
    content_type: str | None = None,
    *,
    url: str | None = None,
    language: str | None = None,
) -> Document:
    kind = detect_content_type(source, content_type, url)
    if kind == "text/html":
        return parse_html(source, url=url, language=language)
    if isinstance(source, bytes):
        source = source.decode("utf-8", "replace")
    if kind == "text/markdown":
        return parse_markdown(source, url=url, language=language)
    return parse_text(source, url=url, language=language)
