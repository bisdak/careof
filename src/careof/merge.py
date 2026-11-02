"""Confidence scoring, deduplication, and final ordering."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from .parse import CORE, NullParser, PostalParser, normalize_components, normalize_key
from .schema import Address, Source, ordered

STRUCTURED = frozenset({"json-ld", "microdata", "og-meta", "address-tag"})
PARSER = PostalParser | NullParser


def make_address(
    raw: str,
    components: Mapping[str, str] | None,
    *,
    score: float,
    source: str,
    parser: PARSER,
    language: str | None = None,
    country: str | None = None,
    start: int | None = None,
    end: int | None = None,
    block: int | None = None,
) -> Address:
    raw = " ".join(raw.split())
    comps = normalize_components(components or {})

    if parser.available and raw:
        parsed = parser.parse(raw, language=language, country=country)
        for key, value in parsed.items():
            comps.setdefault(key, value)

    key = parser.key(raw, comps, language=language) if raw else normalize_key(raw)
    return Address(
        raw=raw,
        components=comps,
        confidence=confidence(comps, score, source),
        key=key,
        sources=[
            Source(kind=source, start=start, end=end, block=block, score=round(score, 3))
        ],
    )


def confidence(components: Mapping[str, str], score: float, source: str) -> float:
    core = sum(1 for key in CORE if components.get(key))
    value = 0.30 + 0.09 * core + 0.15 * max(0.0, min(1.0, score))
    if source in STRUCTURED:
        value += 0.20
    elif source == "map-link":
        value += 0.12
    if not components:
        value = min(value, 0.45)
    return min(value, 0.99)


def merge(addresses: Iterable[Address]) -> list[Address]:
    merged: list[Address] = []
    for address in sorted(addresses, key=lambda a: -a.confidence):
        match = _find(merged, address)
        if match is None:
            address.components = ordered(address.components)
            merged.append(address)
            continue
        _absorb(match, address)

    for address in merged:
        address.components = ordered(address.components)
    return sorted(merged, key=lambda a: (-a.confidence, a.raw))


def _find(existing: list[Address], candidate: Address) -> Address | None:
    if not candidate.key:
        return None
    for address in existing:
        if address.key == candidate.key:
            return address
    for address in existing:
        if _similar(address, candidate):
            return address
    return None


def _similar(a: Address, b: Address) -> bool:
    if not a.key or not b.key:
        return False
    ta, tb = set(a.key.split()), set(b.key.split())
    if not ta or not tb:
        return False
    small, large = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    if not small.issubset(large):
        return False
    if len(large) - len(small) > 3:
        return False
    for key in ("house_number", "unit", "postcode"):
        if (
            a.components.get(key)
            and b.components.get(key)
            and a.components[key] != b.components[key]
        ):
            return False
    return True


def _absorb(target: Address, extra: Address) -> None:
    for key, value in extra.components.items():
        current = target.components.get(key)
        if not current:
            target.components[key] = value
    for source in extra.sources:
        if not any(
            s.kind == source.kind and s.start == source.start and s.start is not None
            for s in target.sources
        ):
            target.sources.append(source)
    target.confidence = min(0.99, max(target.confidence, extra.confidence) + 0.02)
