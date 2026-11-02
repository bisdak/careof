from __future__ import annotations

import itertools

from careof import extract
from careof.ner import Span, _chunks
from careof.parse import NullParser


class FakeExtractor:
    name = "fake"

    def __init__(self, needle: str) -> None:
        self.needle = needle

    def extract(self, text, labels, threshold):  # type: ignore[no-untyped-def]
        index = text.find(self.needle)
        if index == -1:
            return []
        return [
            Span(
                start=index,
                end=index + len(self.needle),
                text=self.needle,
                score=0.9,
            )
        ]


def test_candidate_offsets_are_translated_to_document_offsets() -> None:
    source = "<html><body><p>Intro paragraph.</p><p>123 Main St</p></body></html>"
    results = extract(
        source,
        "text/html",
        extractor=FakeExtractor("123 Main St"),
        parser=NullParser(),
    )
    assert len(results) == 1
    address = results[0]
    assert address.raw == "123 Main St"
    source_info = address.sources[0]
    assert source_info.start is not None
    assert address.raw in source


def test_chunks_cover_a_long_text() -> None:
    text = "word " * 500
    chunks = _chunks(text.strip(), size=200, overlap=40)
    assert chunks[0][0] == 0
    assert chunks[-1][1] == len(text.strip())
    for (_, end), (start, _) in itertools.pairwise(chunks):
        assert start <= end
