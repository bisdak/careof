from __future__ import annotations

from pathlib import Path

from careof import extract
from careof.parse import NullParser

FIXTURE = Path(__file__).with_name("100percentweb_ca.html")


def test_extracts_100_percent_helpdesk_canadian_address() -> None:
    results = extract(
        FIXTURE.read_bytes(),
        "text/html",
        language="en",
        country="ca",
        extractor="heuristic",
        parser=NullParser(),
    )

    assert [address.raw for address in results] == [
        "100 Percent Helpdesk Ltd. UNIT 3 — 363 Broadway Winnipeg, MB R3C 3N9"
    ]
