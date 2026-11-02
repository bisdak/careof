"""libpostal integration.

libpostal is not a pip-installable parser: the ``postal`` package is ctypes
bindings and needs the C library plus its ~2 GB data set. Everything here
degrades to an empty component dict when that is missing, so the extractor is
still useful without it.
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache

import re2

from .schema import COMPONENT_ORDER

try:  # pragma: no cover - depends on the host
    from postal.expand import expand_address as _expand_address
    from postal.parser import parse_address as _parse_address
except Exception:  # noqa: BLE001 - missing libpostal raises ImportError or OSError
    _expand_address = None
    _parse_address = None

_WS = re2.compile(r"\s+")
_PUNCT = re2.compile(r"[,.;]")
_STREET_NUMBER = re2.compile(r"^\s*(\d{1,6}[A-Za-z]?(?:[-/]\d{1,6}[A-Za-z]?)?)\s+(.+?)\s*$")

#: Labels worth keeping. libpostal emits a long tail of rare ones; they are
#: preserved but only these count towards confidence.
CORE = frozenset(
    {
        "house_number",
        "road",
        "unit",
        "po_box",
        "suburb",
        "city",
        "state",
        "postcode",
        "country",
    }
)


def available() -> bool:
    return _parse_address is not None


@lru_cache(maxsize=8192)
def _parse_cached(
    raw: str, language: str | None, country: str | None
) -> tuple[tuple[str, str], ...]:
    assert _parse_address is not None
    parsed = _parse_address(raw, language=language, country=country)
    return tuple((str(label), str(value)) for label, value in parsed)


@lru_cache(maxsize=4096)
def _expand_cached(raw: str, language: str | None) -> tuple[str, ...]:
    assert _expand_address is not None
    if language:
        result = _expand_address(raw, languages=[language])
    else:
        result = _expand_address(raw)
    return tuple(str(item) for item in result)


class PostalParser:
    name = "libpostal"

    def __init__(self, language: str | None = None, country: str | None = None):
        self.language = language
        self.country = country
        self.available = available()

    def parse(
        self,
        raw: str,
        *,
        language: str | None = None,
        country: str | None = None,
    ) -> dict[str, str]:
        raw = raw.strip()
        if not self.available or not raw:
            return {}
        try:
            pairs = _parse_cached(
                raw,
                language or self.language,
                country or self.country,
            )
        except Exception:  # noqa: BLE001 - bad input should never crash us
            return {}
        return normalize_components(dict(pairs))

    def expand(self, raw: str, *, language: str | None = None) -> str | None:
        if not self.available or not raw:
            return None
        try:
            expansions = _expand_cached(raw.strip(), language or self.language)
        except Exception:  # noqa: BLE001 - expansion failures are non-fatal
            return None
        return expansions[0] if expansions else None

    def key(
        self,
        raw: str,
        components: Mapping[str, str] | None = None,
        *,
        language: str | None = None,
    ) -> str:
        expanded = self.expand(raw, language=language)
        if expanded:
            return normalize_key(expanded)
        if components:
            values = [components[k] for k in COMPONENT_ORDER if components.get(k)]
            values.extend(
                v for k, v in components.items() if k not in COMPONENT_ORDER and v
            )
            return normalize_key(" ".join(str(v) for v in values))
        return normalize_key(raw)


class NullParser:
    """Parser for tests and for hosts without libpostal."""

    name = "null"
    available = False

    def parse(self, raw: str, **_: object) -> dict[str, str]:
        return {}

    def expand(self, raw: str, **_: object) -> str | None:
        return None

    def key(
        self,
        raw: str,
        components: Mapping[str, str] | None = None,
        **_: object,
    ) -> str:
        if components:
            values = [components[k] for k in COMPONENT_ORDER if components.get(k)]
            values.extend(
                v for k, v in components.items() if k not in COMPONENT_ORDER and v
            )
            return normalize_key(" ".join(str(v) for v in values))
        return normalize_key(raw)


def normalize_key(value: str) -> str:
    value = _PUNCT.sub(" ", value.lower())
    return _WS.sub(" ", value).strip()


def normalize_components(components: Mapping[str, str]) -> dict[str, str]:
    """Canonical labels, trimmed values, and schema.org ``street`` split up."""
    out: dict[str, str] = {}
    for key, value in components.items():
        key = str(key).strip().lower().replace(" ", "_")
        value = _WS.sub(" ", str(value)).strip(" ,")
        if key and value:
            out[key] = value

    street = out.pop("street", None)
    if street and "road" not in out:
        match = _STREET_NUMBER.match(street)
        if match:
            out.setdefault("house_number", match.group(1))
            out["road"] = match.group(2)
        else:
            out["road"] = street

    return out
