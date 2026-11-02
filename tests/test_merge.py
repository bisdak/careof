from __future__ import annotations

from careof.merge import merge
from careof.parse import normalize_components
from careof.schema import Address, Source


def test_percent_street_splits_into_house_number_and_road() -> None:
    components = normalize_components(
        {"street": "123 Mabini Street", "city": "Makati City", "postcode": "1223"}
    )
    assert components["house_number"] == "123"
    assert components["road"] == "Mabini Street"


def test_street_without_a_number_becomes_the_road() -> None:
    components = normalize_components({"street": "Ayala Avenue"})
    assert components == {"road": "Ayala Avenue"}


def test_exact_keys_merge_and_keep_provenance() -> None:
    first = Address(
        raw="123 Mabini Street, Makati City 1223",
        key="123 mabini street makati city 1223",
        confidence=0.8,
        sources=[Source(kind="json-ld")],
    )
    second = Address(
        raw="123 Mabini Street Makati City 1223",
        key="123 mabini street makati city 1223",
        confidence=0.5,
        sources=[Source(kind="heuristic", start=10, end=48)],
    )
    results = merge([first, second])
    assert len(results) == 1
    assert {source.kind for source in results[0].sources} == {"json-ld", "heuristic"}
    assert results[0].confidence > 0.8


def test_different_units_do_not_merge() -> None:
    a = Address(
        raw="Unit 4A, 77 Ayala Ave",
        key="unit 4a 77 ayala ave",
        confidence=0.5,
        components={"house_number": "77", "unit": "4A"},
    )
    b = Address(
        raw="Unit 4B, 77 Ayala Ave",
        key="unit 4b 77 ayala ave",
        confidence=0.5,
        components={"house_number": "77", "unit": "4B"},
    )
    assert len(merge([a, b])) == 2
