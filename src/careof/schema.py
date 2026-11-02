"""Small, dependency-free data types shared by every stage."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

# The order libpostal uses, minus the long tail of rare labels. Anything else
# a parser returns is appended after these.
COMPONENT_ORDER = (
    "house_number",
    "road",
    "unit",
    "po_box",
    "suburb",
    "city",
    "state",
    "postcode",
    "country",
)

CORE_COMPONENTS = frozenset(COMPONENT_ORDER)


@dataclass(frozen=True, slots=True)
class Block:
    """A contiguous run of text that belongs together, in document offsets."""

    text: str
    start: int
    end: int
    tag: str = "text"
    index: int = 0


@dataclass(frozen=True, slots=True)
class Candidate:
    """A window of the document worth showing to the model."""

    text: str
    start: int
    end: int
    source: str = "text"
    score: float = 0.0
    block: int | None = None


@dataclass(frozen=True, slots=True)
class Span:
    """An address (or address part) found inside a candidate."""

    start: int
    end: int
    text: str
    label: str = "address"
    score: float = 1.0


@dataclass(frozen=True, slots=True)
class Source:
    """Where a result came from. Offsets are document-relative when known."""

    kind: str
    start: int | None = None
    end: int | None = None
    block: int | None = None
    score: float | None = None


@dataclass(frozen=True, slots=True)
class StructuredAddress:
    """An address found without the model: JSON-LD, microdata, <address>, ..."""

    raw: str
    components: Mapping[str, str] = field(default_factory=dict)
    source: str = "structured"
    score: float = 0.95
    start: int | None = None
    end: int | None = None


@dataclass
class Address:
    raw: str
    components: dict[str, str] = field(default_factory=dict)
    confidence: float = 0.0
    key: str = ""
    sources: list[Source] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        components = {k: self.components[k] for k in COMPONENT_ORDER if k in self.components}
        components.update({k: v for k, v in self.components.items() if k not in components})
        return {
            "raw": self.raw,
            "components": components,
            "confidence": round(self.confidence, 3),
            "key": self.key,
            "sources": [
                {
                    k: v
                    for k, v in (
                        ("kind", s.kind),
                        ("start", s.start),
                        ("end", s.end),
                        ("block", s.block),
                        ("score", s.score),
                    )
                    if v is not None
                }
                for s in self.sources
            ],
        }


def ordered(components: Mapping[str, str]) -> dict[str, str]:
    """Return components in a stable, human-friendly order."""
    out = {k: components[k] for k in COMPONENT_ORDER if components.get(k)}
    out.update({k: v for k, v in components.items() if v and k not in out})
    return out
