"""HTML adapter: lxml for parsing, a block-aware serializer for text.

The important bit is that block boundaries become newlines. ``text_content()``
would turn ``123 Main St<br>Springfield`` into ``123 Main StSpringfield``.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import re2
from lxml import etree, html

from ..schema import Block, StructuredAddress
from .base import Document

DROP = frozenset(
    {
        "script",
        "style",
        "noscript",
        "template",
        "svg",
        "canvas",
        "iframe",
        "object",
        "embed",
        "nav",
    }
)

BLOCK = frozenset(
    {
        "address",
        "article",
        "aside",
        "blockquote",
        "body",
        "dd",
        "div",
        "dl",
        "dt",
        "figcaption",
        "footer",
        "form",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "li",
        "main",
        "p",
        "pre",
        "section",
        "table",
        "td",
        "th",
        "tr",
        "ul",
        "ol",
    }
)

SCHEMA_MAP = {
    "streetaddress": "street",    "addresslocality": "city",
    "addressregion": "state",
    "postalcode": "postcode",
    "addresscountry": "country",
    "postofficeboxnumber": "po_box",
}

OG_MAP = {    "og:street-address": "street",
    "og:locality": "city",
    "og:region": "state",
    "og:postal-code": "postcode",
    "og:country-name": "country",
    "geo.placename": "city",
}

_WS = re2.compile(r"\s+")
_HS = re2.compile(r"[ \t]+")
_NEWLINES = re2.compile(r"\n{2,}")
_POSTAL_CODE = re2.compile(
    r"(?i)\b(?:\d{5}(?:-\d{4})?|[A-Z]\d[A-Z][ -]?\d[A-Z]\d|"
    r"(?:[A-Z]{1,2}\d[A-Z\d]?|GIR)[ -]?\d[A-Z]{2})\b"
)
_ADDRESS_HINT = re2.compile(
    r"(?i)\b(?:street|st\.?|avenue|ave\.?|road|rd\.?|boulevard|blvd\.?|"
    r"lane|drive|unit|suite|floor|city|"
    r"province|address|po box)\b"
)


def parse_html(
    source: str | bytes,
    *,
    url: str | None = None,
    language: str | None = None,
) -> Document:
    if not source or (isinstance(source, str) and not source.strip()):
        return Document(text="", blocks=[], content_type="text/html")

    if isinstance(source, str):
        # lxml refuses str input that still carries an XML encoding
        # declaration; the declaration is meaningless once decoded.
        source = re2.sub(r"(?is)^\s*<\?xml[^>]*\?>", "", source, count=1)

    parser = html.HTMLParser(recover=True, remove_comments=True)
    try:
        root = html.document_fromstring(source, parser=parser)
    except (etree.ParserError, ValueError):
        return Document(text="", blocks=[], content_type="text/html")

    structured = list(_structured_addresses(root))
    text, blocks = _serialize(root)
    _attach_offsets(structured, text)

    lang = language or _language(root)
    meta: dict[str, Any] = {}
    title = root.find(".//title")
    if title is not None and title.text:
        meta["title"] = _WS.sub(" ", title.text).strip()
    if lang:
        meta["language"] = lang
    if url:
        meta["url"] = url

    return Document(
        text=text,
        blocks=blocks,
        structured=structured,
        meta=meta,
        content_type="text/html",
    )


def _localname(tag: Any) -> str:
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1].lower()


def _language(root: Any) -> str | None:
    if root.get("lang"):
        return root.get("lang").split("-")[0].lower()
    el = root.find(".//html")
    if el is not None and el.get("lang"):
        return el.get("lang").split("-")[0].lower()
    return None


class _Writer:
    """Accumulates text while keeping a running character count."""

    def __init__(self) -> None:
        self.parts: list[str] = []
        self.length = 0
        self._tail = ""

    def write(self, value: str | None) -> None:
        if not value:
            return
        value = value.replace("\xa0", " ").replace("\u200b", "")
        value = _HS.sub(" ", value)
        value = _NEWLINES.sub("\n", value)
        if self._tail.endswith("\n"):
            value = value.lstrip(" \t\n")
        if not value:
            return
        self.parts.append(value)
        self.length += len(value)
        self._tail = (self._tail + value)[-2:]

    def newline(self) -> None:
        if self.length == 0 or self._tail.endswith("\n"):
            return
        self.parts.append("\n")
        self.length += 1
        self._tail = (self._tail + "\n")[-2:]

    def text(self) -> str:
        return "".join(self.parts)


def _serialize(root: Any) -> tuple[str, list[Block]]:
    writer = _Writer()
    records: list[tuple[int, int, str]] = []

    def walk(el: Any) -> None:
        tag = _localname(el.tag)
        if tag in DROP:
            writer.write(el.tail)
            return
        if tag in ("br", "hr"):
            writer.write("\n")
            writer.write(el.tail)
            return

        is_block = tag in BLOCK
        if is_block:
            writer.newline()

        start = writer.length
        writer.write(el.text)
        for child in el:
            walk(child)
        writer.write(el.tail)

        if is_block:
            records.append((start, writer.length, tag))

    body = root.find(".//body")
    walk(body if body is not None else root)

    text = writer.text()
    raw_blocks: list[Block] = []
    for start, end, tag in records:
        segment = text[start:end]
        body_text = segment.strip()
        if not body_text or not any(ch.isalnum() for ch in body_text):
            continue
        lead = len(segment) - len(segment.lstrip())
        trail = len(segment) - len(segment.rstrip())
        raw_blocks.append(
            Block(
                text=body_text,
                start=start + lead,
                end=end - trail,
                tag=tag,
            )
        )

    # Nested block elements produce overlapping records (div > p). Keep the
    # deepest ones, then re-add whatever text the parents held outside their
    # children so nothing is silently lost.
    leaves: list[Block] = []
    for block in sorted(raw_blocks, key=lambda b: (b.end - b.start, b.start)):
        if any(
            block.start <= leaf.start and leaf.end <= block.end
            for leaf in leaves
        ):
            continue
        leaves.append(block)

    covered = _merge_intervals([(b.start, b.end) for b in leaves])
    leaf_spans = {(b.start, b.end, b.tag) for b in leaves}
    residual: list[Block] = []
    for block in raw_blocks:
        if (block.start, block.end, block.tag) in leaf_spans:
            continue
        for start, end in _subtract((block.start, block.end), covered):
            segment = text[start:end]
            body_text = segment.strip()
            if not body_text or not any(ch.isalnum() for ch in body_text):
                continue
            lead = len(segment) - len(segment.lstrip())
            trail = len(segment) - len(segment.rstrip())
            residual.append(
                Block(
                    text=body_text,
                    start=start + lead,
                    end=end - trail,
                    tag=block.tag,
                )
            )

    blocks = sorted(leaves + residual, key=lambda b: (b.start, b.end))
    deduped: list[Block] = []
    seen: set[tuple[int, int]] = set()
    for block in blocks:
        span = (block.start, block.end)
        if span in seen:
            continue
        seen.add(span)
        deduped.append(
            Block(
                text=block.text,
                start=block.start,
                end=block.end,
                tag=block.tag,
                index=len(deduped),
            )
        )

    if not deduped and text.strip():
        body_text = text.strip()
        start = text.find(body_text)
        deduped.append(
            Block(text=body_text, start=start, end=start + len(body_text), tag="body", index=0)
        )

    return text, deduped


def _merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _subtract(
    interval: tuple[int, int], covered: list[tuple[int, int]]
) -> list[tuple[int, int]]:
    start, end = interval
    pieces: list[tuple[int, int]] = []
    cursor = start
    for cover_start, cover_end in covered:
        if cover_end <= cursor:
            continue
        if cover_start >= end:
            break
        if cover_start > cursor:
            pieces.append((cursor, min(cover_start, end)))
        cursor = max(cursor, cover_end)
        if cursor >= end:
            break
    if cursor < end:
        pieces.append((cursor, end))
    return pieces


# ---------------------------------------------------------------------------
# Structured signals. These are cheap and more precise than any model, so they
# are collected first and allowed to short-circuit the NER path.
# ---------------------------------------------------------------------------


def _structured_addresses(root: Any) -> Iterator[StructuredAddress]:
    yield from _jsonld(root)
    yield from _microdata(root)
    yield from _meta(root)
    yield from _address_tags(root)
    yield from _map_links(root)


def _jsonld(root: Any) -> Iterator[StructuredAddress]:
    for el in root.iter():
        if _localname(el.tag) != "script":
            continue
        if "ld+json" not in (el.get("type") or "").lower():
            continue
        raw = (el.text or "").strip()
        if not raw:
            continue
        data = _loads(raw)
        if data is None:
            continue
        for item in _walk_jsonld(data):
            yield StructuredAddress(
                raw=item["raw"],
                components=item["components"],
                source="json-ld",
                score=0.99,
            )


def _loads(raw: str) -> Any | None:
    raw = raw.lstrip("\ufeff").strip()
    for candidate in (raw, _strip_trailing_commas(raw)):
        try:
            return json.loads(candidate)
        except (ValueError, TypeError):
            continue
    return None


def _strip_trailing_commas(raw: str) -> str:
    """JSON-LD in the wild often has trailing commas. Fix without a regex."""
    out: list[str] = []
    i = 0
    n = len(raw)
    in_string = False
    escaped = False
    while i < n:
        ch = raw[i]
        if in_string:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue
        if ch == ",":
            j = i + 1
            while j < n and raw[j] in " \t\r\n":
                j += 1
            if j < n and raw[j] in "}]":
                i += 1
                continue
        out.append(ch)
        i += 1
    return "".join(out)


def _walk_jsonld(data: Any) -> Iterator[dict[str, Any]]:
    if isinstance(data, list):
        for item in data:
            yield from _walk_jsonld(item)
        return
    if not isinstance(data, dict):
        return

    types = data.get("@type")
    types = types if isinstance(types, list) else [types]
    is_address = any(
        isinstance(t, str) and t.lower().endswith("postaladdress") for t in types
    )
    looks_like_address = any(
        key in data for key in ("streetAddress", "postalCode", "addressLocality")
    )
    if is_address or looks_like_address:
        item = _schema_address(data)
        if item:
            yield item

    for value in data.values():
        if isinstance(value, (dict, list)):
            yield from _walk_jsonld(value)


def _scalar(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("name", "@id", "streetAddress"):
            if value.get(key):
                return str(value[key])
        return ""
    if isinstance(value, list):
        return _scalar(value[0]) if value else ""
    if value is None:
        return ""
    return str(value)


def _schema_address(data: dict[str, Any]) -> dict[str, Any] | None:
    components: dict[str, str] = {}
    for key, value in data.items():
        mapped = SCHEMA_MAP.get(str(key).lower())
        if mapped:
            text = _scalar(value).strip()
            if text:
                components[mapped] = text
    if not components:
        return None
    raw = _join_components(components)
    if not raw:
        return None
    return {"raw": raw, "components": components}


def _join_components(components: dict[str, str]) -> str:
    order = ("street", "unit", "po_box", "suburb", "city", "state", "postcode", "country")
    seen: set[str] = set()
    parts: list[str] = []
    for key in order:
        value = components.get(key)
        if value and value not in seen:
            parts.append(value)
            seen.add(value)
    for key, value in components.items():
        if key not in order and value and value not in seen:
            parts.append(value)
            seen.add(value)
    return ", ".join(parts)


def _microdata(root: Any) -> Iterator[StructuredAddress]:
    for el in root.iter():
        itemtype = (el.get("itemtype") or "").lower()
        if "postaladdress" not in itemtype:
            continue
        components: dict[str, str] = {}
        for child in el.iter():
            prop = (child.get("itemprop") or "").strip().lower()
            mapped = SCHEMA_MAP.get(prop)
            if not mapped:
                continue
            value = (
                child.get("content")
                or child.get("value")
                or " ".join(child.itertext())
            )
            value = _WS.sub(" ", value).strip()
            if value:
                components[mapped] = value
        if components:
            raw = _join_components(components)
            if raw:
                yield StructuredAddress(
                    raw=raw,
                    components=components,
                    source="microdata",
                    score=0.97,
                )


def _meta(root: Any) -> Iterator[StructuredAddress]:
    values: dict[str, str] = {}
    for el in root.iter():
        if _localname(el.tag) != "meta":
            continue
        key = (el.get("property") or el.get("name") or "").strip().lower()
        mapped = OG_MAP.get(key)
        if not mapped:
            continue
        value = _WS.sub(" ", el.get("content") or "").strip()
        if value:
            values[mapped] = value
    if not values:
        return
    if not (values.get("street") or (values.get("postcode") and values.get("city"))):
        return
    raw = _join_components(values)
    if raw:
        yield StructuredAddress(
            raw=raw, components=values, source="og-meta", score=0.8
        )


def _address_tags(root: Any) -> Iterator[StructuredAddress]:
    for el in root.iter():
        if _localname(el.tag) != "address":
            continue
        raw = _clean_address_tag(_element_lines(el))
        if raw and any(ch.isdigit() for ch in raw) and _ADDRESS_HINT.search(raw):
            yield StructuredAddress(raw=raw, source="address-tag", score=0.9)


def _element_lines(el: Any) -> str:
    """Collect text with <br> and block children as newlines."""
    parts: list[str] = []

    def collect(node: Any) -> None:
        if _localname(node.tag) in ("br", "hr"):
            parts.append("\n")
            return
        if node.text:
            parts.append(node.text)
        for child in node:
            collect(child)
            if child.tail:
                parts.append(child.tail)

    collect(el)
    return "".join(parts)


def _clean_address_tag(value: str) -> str:
    lines = [_WS.sub(" ", line).strip() for line in value.splitlines()]
    lines = [line for line in lines if line]
    # <address> blocks often start with a company name. Drop leading lines
    # that look like a name rather than an address.
    while len(lines) > 1 and not _ADDRESS_HINT.search(lines[0]):
        lines.pop(0)

    # Address tags may also wrap hours or notices. Stop after the postal line
    # instead of treating the rest of the element as part of the address.
    for index, line in enumerate(lines):
        match = _POSTAL_CODE.search(line)
        if match and (match.start() > 0 or match.group(0)[0].isalpha()):
            lines = lines[: index + 1]
            break
    return ", ".join(lines)


def _map_links(root: Any) -> Iterator[StructuredAddress]:
    for el in root.iter():
        if _localname(el.tag) != "a":
            continue
        href = (el.get("href") or "").strip()
        if not href:
            continue
        raw = _address_from_url(href)
        if raw:
            yield StructuredAddress(raw=raw, source="map-link", score=0.85)


def _address_from_url(href: str) -> str | None:
    if href.lower().startswith("geo:"):
        query = href.split("?", 1)
        if len(query) == 2:
            return _clean_candidate(parse_qs(query[1]).get("q", [""])[0])
        return None

    try:
        parsed = urlparse(href if "://" in href else "https://" + href)
    except ValueError:
        return None
    host = parsed.netloc.lower()
    if "google." not in host and "maps.apple.com" not in host:
        return None

    params = parse_qs(parsed.query)
    for key in ("q", "daddr", "destination", "address"):
        for value in params.get(key, []):
            candidate = _clean_candidate(value)
            if candidate:
                return candidate

    path = unquote(parsed.path)
    marker = "/maps/place/"
    if marker in path:
        tail = path.split(marker, 1)[1].split("/@", 1)[0]
        return _clean_candidate(tail.replace("+", " "))
    return None


def _clean_candidate(value: str) -> str | None:
    value = _WS.sub(" ", value.replace("+", " ")).strip(" ,")
    if not value:
        return None
    if not any(ch.isalpha() for ch in value):
        return None
    if not (any(ch.isdigit() for ch in value) or "," in value):
        return None
    return value


def _attach_offsets(items: list[StructuredAddress], text: str) -> list[StructuredAddress]:
    """Best-effort offsets. JSON-LD lives in <head>, so it often has none."""
    for i, item in enumerate(items):
        index = -1
        for length in (len(item.raw), 60, 40, 20, 12):
            if length <= 0:
                continue
            index = text.find(item.raw[:length])
            if index != -1:
                break
        if index == -1:
            continue
        items[i] = StructuredAddress(
            raw=item.raw,
            components=item.components,
            source=item.source,
            score=item.score,
            start=index,
            end=min(len(text), index + len(item.raw)),
        )
    return items
