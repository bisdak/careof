"""The public pipeline: document in, ranked addresses out."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from .adapters import load_document
from .candidates import build_candidates
from .merge import make_address, merge
from .ner import DEFAULT_LABELS, Extractor, plausible, resolve
from .parse import LibpostalHTTPParser, NullParser, PostalParser
from .schema import Address

PARSER = PostalParser | LibpostalHTTPParser | NullParser


def extract(
    source: str | bytes,
    content_type: str | None = None,
    *,
    url: str | None = None,
    language: str | None = None,
    country: str | None = None,
    libpostal_url: str | None = None,
    threshold: float = 0.4,
    labels: Sequence[str] = DEFAULT_LABELS,
    extractor: Extractor | str | None = "auto",
    parser: PARSER | None = None,
    max_candidates: int = 40,
    structured: bool = True,
) -> list[Address]:
    """Extract addresses from HTML, Markdown, or plain text.

    ``extractor=None`` skips the model and returns only structured results,
    which is useful for cheap crawls. ``parser`` can be a ``NullParser`` in
    tests or on machines without libpostal.
    """
    document = load_document(source, content_type, url=url, language=language)
    lang = language or document.meta.get("language")
    if parser is None:
        if libpostal_url:
            parser = LibpostalHTTPParser(
                libpostal_url, language=lang, country=country
            )
        else:
            parser = PostalParser(language=lang, country=country)

    addresses: list[Address] = []

    if structured:
        for item in document.structured:
            addresses.append(
                make_address(
                    item.raw,
                    item.components,
                    score=item.score,
                    source=item.source,
                    parser=parser,
                    language=lang,
                    country=country,
                    start=item.start,
                    end=item.end,
                )
            )

    if extractor is not None:
        engine = resolve(extractor)
        spans: list[tuple[int, int, float, int | None]] = []
        for candidate in build_candidates(document, max_candidates=max_candidates):
            for span in engine.extract(candidate.text, labels, threshold):
                start = candidate.start + span.start
                end = candidate.start + span.end
                segment = document.text[start:end]
                raw = segment.strip()
                if not plausible(raw):
                    continue
                lead = len(segment) - len(segment.lstrip())
                start += lead
                end = start + len(raw)
                spans.append((start, end, span.score, candidate.block))

        for start, end, score, block in _dedupe_spans(spans):
            raw = document.text[start:end].strip()
            addresses.append(
                make_address(
                    raw,
                    None,
                    score=score,
                    source=engine.name,
                    parser=parser,
                    language=lang,
                    country=country,
                    start=start,
                    end=end,
                    block=block,
                )
            )

    return merge(addresses)


def _dedupe_spans(
    spans: list[tuple[int, int, float, int | None]],
) -> list[tuple[int, int, float, int | None]]:
    """Overlapping candidates can surface the same span twice."""
    spans.sort(key=lambda item: (-item[2], -(item[1] - item[0])))
    kept: list[tuple[int, int, float, int | None]] = []
    for span in spans:
        if any(_overlap(span, other) > 0.6 for other in kept):
            continue
        kept.append(span)
    kept.sort(key=lambda item: item[0])
    return kept


def _overlap(
    a: tuple[int, int, float, int | None],
    b: tuple[int, int, float, int | None],
) -> float:
    start = max(a[0], b[0])
    end = min(a[1], b[1])
    if end <= start:
        return 0.0
    shortest = min(a[1] - a[0], b[1] - b[0])
    return (end - start) / max(1, shortest)


def extract_file(
    path: str | Path,
    *,
    content_type: str | None = None,
    **kwargs: object,
) -> list[Address]:
    file = Path(path)
    data = file.read_bytes()
    url = kwargs.pop("url", None) or str(file)
    return extract(data, content_type, url=url, **kwargs)  # type: ignore[arg-type]
