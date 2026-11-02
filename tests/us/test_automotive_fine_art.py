from __future__ import annotations

from pathlib import Path

from careof import extract
from careof.parse import NullParser

FIXTURE = Path(__file__).with_name("automotivefineart.html")


def test_extracts_automotive_fine_art_address_without_notice_text() -> None:
    results = extract(
        FIXTURE.read_bytes(),
        "text/html",
        language="en",
        country="us",
        extractor="heuristic",
        parser=NullParser(),
    )

    assert [address.raw for address in results] == [
        "9341 N. NYBERG RD., HAYWARD, WI 54843-6635"
    ]
