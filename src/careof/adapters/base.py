from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..schema import Block, StructuredAddress


@dataclass
class Document:
    """Normalised text plus enough offsets to trace every result home."""

    text: str
    blocks: list[Block]
    structured: list[StructuredAddress] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)
    content_type: str = "text/plain"
