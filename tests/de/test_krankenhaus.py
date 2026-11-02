from __future__ import annotations

from pathlib import Path

from careof import extract
from careof.parse import NullParser

FIXTURE = Path(__file__).with_name("krankenhaus.html")


def test_extracts_addresses_from_krankenhaus_impressum() -> None:
    results = extract(
        FIXTURE.read_bytes(),
        "text/html",
        language="de",
        country="de",
        extractor="heuristic",
        parser=NullParser(),
    )

    found = {address.raw for address in results}
    assert found == {
        "Prötzeler Chaussee 5 15344 Strausberg",
        "Sonnenburger Weg 3 16269 Wriezen",
        "Dreifertstraße 12 03044 Cottbus",
    }

    # Telephone lines should not be absorbed into the address spans.
    assert all("Telefon" not in address.raw and "Tel." not in address.raw for address in results)
