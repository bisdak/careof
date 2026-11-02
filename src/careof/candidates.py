"""Cheap, high-recall windows for the expensive model.

Regexes are used for *candidate selection*, never for parsing an address. A
window of a few hundred characters around a street-ish pattern is enough for
GLiNER to work with, and it keeps a whole homepage from being tokenised.
"""

from __future__ import annotations

import re2

from .adapters.base import Document
from .schema import Block, Candidate

STREET_SUFFIX = (
    r"(?:street|st\.?|avenue|ave\.?|road|rd\.?|boulevard|blvd\.?|lane|ln\.?|"
    r"drive|dr\.?|court|ct\.?|highway|hwy\.?|parkway|pkwy\.?|place|pl\.?|"
    r"terrace|ter\.?|circle|cir\.?|square|sq\.?|trail|trl\.?|route|rte\.?)"
)

HOUSE_NUMBER = r"\b\d{1,6}[A-Za-z]?(?:[-/]\d{1,6}[A-Za-z]?)?\b"

STRONG = re2.compile(
    rf"(?i){HOUSE_NUMBER}[^\n]{{0,80}}?\b{STREET_SUFFIX}\b"
)
GERMAN_STREET = re2.compile(
    r"(?i)\b(?:(?:[\p{L}][\p{L}.'-]*[ \t]+){0,2}"
    r"(?:straße|str\.?|weg|chaussee|allee|platz|ring|gasse|damm|ufer)|"
    r"[\p{L}][\p{L}.'-]*(?:straße|str\.?))"
    r"[ \t]+\d{1,6}[a-z]?(?:[-/]\d{1,6}[a-z]?)?\b"
)
POBOX = re2.compile(r"(?i)\b(?:p\.?\s*o\.?\s*box|post office box)\s*\d+\b")
UNIT = re2.compile(
    r"(?i)\b(?:unit|suite|ste\.?|floor|fl\.?|room|rm\.?|bldg\.?|building|tower)"
    r"\s*#?\s*[A-Za-z0-9-]+\b"
)
POSTCODE = re2.compile(r"\b\d{4,5}(?:-\d{4})?\b")
POSTAL_5 = re2.compile(r"\b\d{5}(?:-\d{4})?\b")
COUNTRY = re2.compile(
    r"(?i)\b(?:philippines|united states|usa|canada|australia|"
    r"united kingdom|uk|singapore|japan|malaysia|indonesia|thailand|"
    r"vietnam|india|new zealand|germany|france|spain|italy|netherlands)\b"
)
CONTACT = re2.compile(
    r"(?i)\b(?:address|contact|office|headquarters|location|visit us|"
    r"find us|where we are|mailing)\b"
)
LANDMARK = re2.compile(
    r"(?i)\b(?:near|beside|across from|opposite)\b"
)
NOISE = re2.compile(
    r"(?i)@|\+?\d[\d ()-]{5,}\d|"
    r"\b(?:tel|telefon|telefax|telephone|phone|fax|mobile|email|home|about|contact|menu|"
    r"login|sign in|privacy|terms|subscribe)\b"
)
TRAILING_PUNCT = re2.compile(r"\s[.,;:]$")
POSTCODE_PERIOD = re2.compile(r"\b\d{4,5}(?:-\d{4})?\.")
NOISE_INLINE = re2.compile(
    r"(?i)\s(?:contact|email|e-mail|tel|telephone|phone|fax|mobile)\b.*$"
)
LEGAL_ENTITY = re2.compile(
    r"(?i)\b(?:gmbh|ag|kg|ohg|ug|e\.?\s*v\.?|inc\.?|llc|ltd\.?|"
    r"corp\.?|corporation|limited)\b"
)

_LINE = "\n"


def score_block(text: str) -> float:
    score = 0.0
    if STRONG.search(text):
        score += 4.0
    if GERMAN_STREET.search(text):
        score += 4.0
    if POBOX.search(text):
        score += 2.0
    if UNIT.search(text):
        score += 1.0
    if LANDMARK.search(text):
        score += 1.5
    if COUNTRY.search(text):
        score += 1.0
    if CONTACT.search(text):
        score += 1.0
    if POSTCODE.search(text):
        score += 0.5
    if len(text) > 2000:
        score -= 1.0
    return score


def _intervals(block: Block, text: str, score: float) -> list[tuple[int, int]]:
    """Windows around every strong signal in the block, with context."""
    found: list[tuple[int, int]] = []
    for match in STRONG.finditer(block.text):
        found.append((match.start(), match.end()))
    for match in GERMAN_STREET.finditer(block.text):
        found.append((match.start(), match.end()))
    for match in POBOX.finditer(block.text):
        found.append((match.start(), match.end()))

    if not found:
        # Keyword-only blocks (contact pages, footers) are worth one look,
        # but only if they are short enough to be about one thing.
        if len(block.text) <= 400:
            found.append((0, len(block.text)))
        else:
            return []

    windows: list[tuple[int, int]] = []
    for start, end in found:
        left = max(0, block.start + start - 160)
        right = min(len(text), block.start + end + 220)
        windows.append((left, right))

    windows.sort()
    merged: list[tuple[int, int]] = []
    for start, end in windows:
        if merged and start <= merged[-1][1] + 40:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _snap(text: str, start: int, end: int) -> tuple[int, int]:
    if start > 0 and text[start - 1].isalnum():
        space = text.rfind(" ", max(0, start - 40), start)
        if space != -1:
            start = space + 1
    if end < len(text) and text[end].isalnum():
        space = text.find(" ", end, min(len(text), end + 40))
        if space != -1:
            end = space
    return start, end


def build_candidates(document: Document, max_candidates: int = 40) -> list[Candidate]:
    scored: list[tuple[float, Block]] = []
    for block in document.blocks:
        score = score_block(block.text)
        if score >= 2.0:
            scored.append((score, block))

    scored.sort(key=lambda item: (-item[0], item[1].start))

    candidates: list[Candidate] = []
    seen: set[tuple[int, int]] = set()
    for score, block in scored:
        for start, end in _intervals(block, document.text, score):
            start, end = _snap(document.text, start, end)
            if end - start < 8:
                continue
            span = (start, end)
            if span in seen:
                continue
            seen.add(span)
            candidates.append(
                Candidate(
                    text=document.text[start:end],
                    start=start,
                    end=end,
                    source="regex-window",
                    score=score,
                    block=block.index,
                )
            )

    candidates.sort(key=lambda c: (-c.score, c.start))
    return candidates[:max_candidates]


def address_line_span(
    text: str, start: int, end: int, max_lines: int = 3
) -> tuple[int, int]:
    """Expand a match to the surrounding address-ish lines (for no-model mode)."""
    line_start = text.rfind(_LINE, 0, start) + 1
    line_end = text.find(_LINE, end)
    if line_end == -1:
        line_end = len(text)

    # "Our office is at 123 Main St" should yield the address, not the
    # sentence. Keep the prefix when it is a label ("Address:") or carries
    # unit/landmark information ("Unit 4B,", "near the main entrance").
    prefix = text[line_start:start]
    if prefix.strip():
        words = prefix.split()
        if (
            len(words) >= 2
            and not UNIT.search(prefix)
            and not LANDMARK.search(prefix)
        ):
            line_start = start

    # Company names commonly occupy the line just above the street address.
    # Include one such line when it ends with a recognizable legal entity form.
    previous_end = line_start - 1
    while previous_end >= 0:
        previous_start = text.rfind(_LINE, 0, previous_end) + 1
        previous = text[previous_start:previous_end].strip()
        if previous:
            if len(previous) <= 120 and LEGAL_ENTITY.search(previous):
                line_start = previous_start
            break
        previous_end = previous_start - 1

    taken = 1
    while taken < max_lines:
        next_start = line_end + 1
        next_end = text.find(_LINE, next_start)
        if next_end == -1:
            next_end = len(text)
        following = text[next_start:next_end].strip()
        if not following:
            line_end = next_end
            if next_end >= len(text):
                break
            continue
        if NOISE.search(following):
            break
        if STRONG.search(following):
            break
        if len(following) > 120:
            break
        line_end = next_end
        taken += 1
        if POSTCODE.search(following) and any(char.isalpha() for char in following):
            break

    segment = text[line_start:line_end]
    body = segment.strip()
    # "Makati City 1223. We are open Monday..." -> stop at the postcode.
    cut = POSTCODE_PERIOD.search(body)
    if cut and cut.end() < len(body):
        body = body[: cut.end()]
    inline = NOISE_INLINE.search(body)
    if inline and inline.start() > 0:
        body = body[: inline.start()].rstrip()
    # Markdown masking can leave "1223 ." behind. Only drop punctuation that
    # is preceded by whitespace, so "St." survives.
    while TRAILING_PUNCT.search(body):
        body = body[:-2].rstrip()
    if not body:
        return start, end
    offset = line_start + len(segment) - len(segment.lstrip())
    return offset, offset + len(body)
