"""Plain-text adapter. Paragraphs are the unit of context."""

from __future__ import annotations

from ..schema import Block
from .base import Document


def normalize(source: str) -> str:
    return (
        source.replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\xa0", " ")
        .replace("\u200b", "")
    )


def paragraphs(text: str, tag: str = "text") -> list[Block]:
    blocks: list[Block] = []
    start: int | None = None
    end = 0
    position = 0

    for line in text.splitlines(keepends=True):
        if line.strip():
            if start is None:
                start = position
            end = position + len(line.rstrip("\n"))
        elif start is not None:
            _append(blocks, text, start, end, tag)
            start = None
        position += len(line)

    if start is not None:
        _append(blocks, text, start, max(end, start), tag)

    for i, block in enumerate(blocks):
        blocks[i] = Block(
            text=block.text, start=block.start, end=block.end, tag=block.tag, index=i
        )
    return blocks


def _append(
    blocks: list[Block], text: str, start: int, end: int, tag: str
) -> None:
    segment = text[start:end]
    body = segment.strip()
    if not body or not any(ch.isalnum() for ch in body):
        return
    lead = len(segment) - len(segment.lstrip())
    trail = len(segment) - len(segment.rstrip())
    blocks.append(Block(body, start + lead, end - trail, tag))


def parse_text(
    source: str,
    *,
    url: str | None = None,
    language: str | None = None,
) -> Document:
    text = normalize(source)
    meta = {"language": language} if language else {}
    if url:
        meta["url"] = url
    return Document(
        text=text,
        blocks=paragraphs(text),
        meta=meta,
        content_type="text/plain",
    )
