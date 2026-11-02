from __future__ import annotations

from pathlib import Path

from careof import extract
from careof.parse import NullParser

FIXTURE = Path(__file__).with_name("beautifulpets.html")


def test_extracts_beautiful_pets_canadian_address() -> None:
    results = extract(
        FIXTURE.read_bytes(),
        "text/html",
        language="en",
        country="ca",
        extractor="heuristic",
        parser=NullParser(),
    )

    matches = [
        address.raw
        for address in results
        if "16 Guelph Street" in address.raw
    ]
    assert matches == ["16 Guelph Street Georgetown Ontario L7G 3Z2"]
    assert all("905-702-9333" not in raw and "Hours" not in raw for raw in matches)
