"""Markdown adapter.

Code fences and inline code are masked with spaces rather than removed, so the
offsets in the resulting text still line up with the original markdown. That
matters when you want to point a human at the exact source line.
"""

from __future__ import annotations

import re2

from .base import Document
from .text import normalize, paragraphs

_FENCE = re2.compile(
    r"(?ms)^[ \t]*(?:`{3,}|~{3,})[^\n]*\n.*?^[ \t]*(?:`{3,}|~{3,})[ \t]*$"
)
_COMMENT = re2.compile(r"(?s)<!--.*?-->")
_INLINE_CODE = re2.compile(r"`[^`\n]+`")
_LINK = re2.compile(r"!?\[([^\]\n]*)\]\([^)\n]*\)")
_HEADING = re2.compile(r"(?m)^[ \t]*#{1,6}[ \t]+")
_QUOTE = re2.compile(r"(?m)^[ \t]*(?:>[ \t]?)+")
_LIST = re2.compile(r"(?m)^[ \t]*(?:[-*+]|\d{1,3}[.)])[ \t]+")
_RULE = re2.compile(r"(?m)^[ \t]*(?:\*[ \t]*){3,}$|^[ \t]*(?:-[ \t]*){3,}$|^[ \t]*(?:_[ \t]*){3,}$")
_FRONT_MATTER = re2.compile(r"(?s)\A---\n.*?\n---[ \t]*(?:\n|$)")


def _blank(value: str) -> str:
    return "".join(ch if ch == "\n" else " " for ch in value)


def _mask(text: str, pattern: re2.Pattern) -> str:
    parts: list[str] = []
    last = 0
    for match in pattern.finditer(text):
        parts.append(text[last : match.start()])
        parts.append(_blank(match.group(0)))
        last = match.end()
    parts.append(text[last:])
    return "".join(parts)


def _links(text: str) -> str:
    """Keep the visible label, pad the rest so offsets do not move."""
    parts: list[str] = []
    last = 0
    for match in _LINK.finditer(text):
        label = match.group(1) or ""
        whole = match.group(0)
        parts.append(text[last : match.start()])
        parts.append(label + " " * max(0, len(whole) - len(label)))
        last = match.end()
    parts.append(text[last:])
    return "".join(parts)


def markdown_to_text(source: str) -> str:
    text = normalize(source)
    text = _mask(text, _FRONT_MATTER)
    text = _mask(text, _FENCE)
    text = _mask(text, _COMMENT)
    text = _mask(text, _INLINE_CODE)
    text = _links(text)
    text = _mask(text, _RULE)
    text = _mask(text, _HEADING)
    text = _mask(text, _QUOTE)
    text = _mask(text, _LIST)
    # Emphasis markers are noise. Asterisks are safe to mask wholesale;
    # double underscores cover the common bold form without touching snake_case.
    text = text.replace("*", " ").replace("__", "  ")
    # Masking leaves "1223 ." behind; swap the pair instead of shrinking text.
    text = text.replace(" .", ". ").replace(" ,", ", ")
    return text.replace("|", " ")


def parse_markdown(
    source: str,
    *,
    url: str | None = None,
    language: str | None = None,
) -> Document:
    text = markdown_to_text(source)
    meta = {"language": language} if language else {}
    if url:
        meta["url"] = url
    return Document(
        text=text,
        blocks=paragraphs(text, tag="md"),
        meta=meta,
        content_type="text/markdown",
    )
