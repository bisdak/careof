from __future__ import annotations

from pathlib import Path

from careof import extract
from careof.parse import NullParser

FIXTURE = Path(__file__).with_name("automationelectronics.html")


def test_extracts_automation_electronics_us_address() -> None:
    results = extract(
        FIXTURE.read_bytes(),
        "text/html",
        language="en",
        country="us",
        extractor="heuristic",
        parser=NullParser(),
    )

    assert [address.raw for address in results] == [
        "9640 Topanga Canyon Place Chatsworth, CA 91311"
    ]
