"""Address extractors.

GLiNER is used directly rather than through ``gliner_spacy``: no spaCy
dependency, no stale wrapper, and the model hands back character offsets that
line up with the document.
"""

from __future__ import annotations

import importlib.util
import warnings
from collections.abc import Sequence
from typing import Protocol

import re2

from .candidates import (
    LANDMARK,
    PH,
    POBOX,
    POSTAL_5,
    STRONG,
    TAGALOG_LANDMARK,
    address_line_span,
)
from .schema import Span

DEFAULT_LABELS = ("address", "street address", "postal address")
COMMA_SEP = re2.compile(r",\s|\s,|,$")


class Extractor(Protocol):
    name: str

    def extract(
        self, text: str, labels: Sequence[str], threshold: float
    ) -> list[Span]: ...


class HeuristicExtractor:
    """No-model fallback. Good enough to smoke-test the pipeline."""

    name = "heuristic"

    def extract(
        self, text: str, labels: Sequence[str] = DEFAULT_LABELS, threshold: float = 0.4
    ) -> list[Span]:
        found: list[Span] = []
        patterns = (STRONG, POBOX)
        for pattern in patterns:
            for match in pattern.finditer(text):
                start, end = address_line_span(text, match.start(), match.end())
                raw = text[start:end].strip()
                if plausible(raw):
                    found.append(Span(start=start, end=end, text=raw, score=0.55))

        # Philippine landmark addresses ("sa likod ng simbahan") have no
        # street number, so they need their own pass.
        for match in PH.finditer(text):
            start, end = address_line_span(text, match.start(), match.end())
            raw = text[start:end].strip()
            if plausible(raw):
                found.append(Span(start=start, end=end, text=raw, score=0.4))
        for match in LANDMARK.finditer(text):
            start, end = address_line_span(text, match.start(), match.end())
            raw = text[start:end].strip()
            if plausible(raw):
                found.append(Span(start=start, end=end, text=raw, score=0.5))

        return _dedupe(found)


class GlinerExtractor:
    """Thin wrapper around GLiNER with chunking and offset translation."""

    name = "gliner"

    def __init__(
        self,
        model_name: str = "urchade/gliner_multi-v2.1",
        device: str | None = None,
        *,
        chunk_chars: int = 700,
        overlap: int = 120,
    ) -> None:
        from gliner import GLiNER

        self.model_name = model_name
        self.model = GLiNER.from_pretrained(model_name)
        if device:
            self.model.to(device)
        self.model.eval()
        self.chunk_chars = chunk_chars
        self.overlap = overlap

    def extract(
        self, text: str, labels: Sequence[str] = DEFAULT_LABELS, threshold: float = 0.4
    ) -> list[Span]:
        spans: list[Span] = []
        for start, end in _chunks(text, self.chunk_chars, self.overlap):
            chunk = text[start:end]
            entities = self.model.predict_entities(
                chunk, list(labels), threshold=threshold, flat_ner=True
            )
            for entity in entities:
                local_start = int(entity["start"])
                local_end = int(entity["end"])
                raw = chunk[local_start:local_end].strip()
                if not plausible(raw):
                    continue
                spans.append(
                    Span(
                        start=start + local_start,
                        end=start + local_end,
                        text=raw,
                        label=str(entity.get("label", "address")),
                        score=float(entity.get("score", 0.5)),
                    )
                )
        return _dedupe(spans)


def resolve(extractor: Extractor | str | None = "auto") -> Extractor:
    if isinstance(extractor, str):
        choice = extractor.lower()
        if choice == "heuristic":
            return HeuristicExtractor()
        if choice == "gliner":
            return GlinerExtractor()
        if choice != "auto":
            raise ValueError(f"unknown extractor: {extractor!r}")
    elif extractor is not None:
        return extractor

    if importlib.util.find_spec("gliner") is not None:
        try:
            return GlinerExtractor()
        except Exception as exc:  # noqa: BLE001 - any load failure means fallback
            warnings.warn(
                f"careof: GLiNER unavailable ({exc}); falling back to regex",
                RuntimeWarning,
                stacklevel=2,
            )
    return HeuristicExtractor()


def plausible(raw: str) -> bool:
    raw = raw.strip()
    if not 6 <= len(raw) <= 400:
        return False
    if not any(ch.isalpha() for ch in raw):
        return False
    if not any(ch.isdigit() for ch in raw) and not (
        PH.search(raw) or LANDMARK.search(raw)
    ):
        return False
    if "@" in raw and not STRONG.search(raw) and "\n" not in raw:
        return False
    if "[" in raw or "]" in raw:
        return False
    words = raw.split()
    if len(words) > 6:
        if not COMMA_SEP.search(raw) and not TAGALOG_LANDMARK.search(raw):
            return False
        if (
            len(words) > 10
            and not POSTAL_5.search(raw[-40:])
            and not TAGALOG_LANDMARK.search(raw)
        ):
            return False
    return True


def _overlaps(a: Span, b: Span) -> bool:
    start = max(a.start, b.start)
    end = min(a.end, b.end)
    if end <= start:
        return False
    shortest = min(a.end - a.start, b.end - b.start)
    return (end - start) / max(1, shortest) > 0.6


def _dedupe(spans: list[Span]) -> list[Span]:
    spans.sort(key=lambda s: (-s.score, -(s.end - s.start)))
    kept: list[Span] = []
    for span in spans:
        if any(_overlaps(span, other) for other in kept):
            continue
        kept.append(span)
    kept.sort(key=lambda s: s.start)
    return kept


def _chunks(text: str, size: int, overlap: int) -> list[tuple[int, int]]:
    if len(text) <= size:
        return [(0, len(text))]
    out: list[tuple[int, int]] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            space = text.rfind(" ", start + size // 2, end)
            if space != -1:
                end = space
        out.append((start, end))
        if end >= len(text):
            break
        next_start = max(start + 1, end - overlap)
        space = text.find(" ", next_start, min(len(text), next_start + 40))
        start = space + 1 if space != -1 else next_start
    return out
