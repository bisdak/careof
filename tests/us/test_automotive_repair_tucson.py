from __future__ import annotations

from pathlib import Path

from careof import extract
from careof.parse import NullParser

FIXTURE = Path(__file__).with_name("automotiverepairtucson.html")


def test_extracts_current_automotive_recalibration_center_address() -> None:
    results = extract(
        FIXTURE.read_bytes(),
        "text/html",
        language="en",
        country="us",
        extractor="heuristic",
        parser=NullParser(),
    )

    assert [address.raw for address in results] == [
        "Automotive Recalibration Center, Inc. 2455 S Craycroft Rd, Tucson, AZ 85711"
    ]
