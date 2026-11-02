from __future__ import annotations

from pathlib import Path

from careof import extract
from careof.parse import NullParser

FIXTURE = Path(__file__).with_name("ardentuk.html")


def test_extracts_ardent_uk_address() -> None:
    results = extract(
        FIXTURE.read_bytes(),
        "text/html",
        language="en",
        country="gb",
        extractor="heuristic",
        parser=NullParser(),
    )

    assert [address.raw for address in results] == [
        "Colonia House Floor 2 16 Toft Green York YO1 6JT"
    ]
