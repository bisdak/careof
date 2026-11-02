from __future__ import annotations

from careof import extract
from careof.parse import NullParser

HTML = """
<html lang="en"><head>
<script type="application/ld+json">
{"@type": "PostalAddress", "streetAddress": "123 Mabini Street",
 "addressLocality": "Makati City", "postalCode": "1223"}
</script>
</head><body>
<address>123 Mabini Street<br>Makati City 1223</address>
<p>Call us at +63 2 1234 5678</p>
</body></html>
"""


def test_end_to_end_dedupes_sources() -> None:
    results = extract(HTML, "text/html", extractor="heuristic", parser=NullParser())
    assert len(results) == 1
    address = results[0]
    kinds = {source.kind for source in address.sources}
    assert "json-ld" in kinds
    assert "heuristic" in kinds
    assert address.confidence > 0.9
    assert address.key == "123 mabini street makati city 1223"


def test_structured_only_mode_skips_the_extractor() -> None:
    results = extract(HTML, "text/html", extractor=None, parser=NullParser())
    assert len(results) == 1
    kinds = {source.kind for source in results[0].sources}
    assert "heuristic" not in kinds
    assert {"json-ld", "address-tag"} <= kinds


def test_markdown_code_fences_are_ignored() -> None:
    markdown = """Our office is at **123 Mabini Street, Makati City 1223**.

```
999 Fake Street, Nowhereville 0000
```
"""
    results = extract(markdown, extractor="heuristic", parser=NullParser())
    assert len(results) == 1
    assert "Mabini" in results[0].raw
    assert "Fake" not in results[0].raw


def test_german_street_suffix_after_house_name() -> None:
    source = """<html lang="de"><body>
    <p>Sonnenburger Weg 3<br>16269 Wriezen<br>Tel. 033456 / 40-0</p>
    <p>Krankenhaus Märkisch-Oderland GmbH<br>Prötzeler Chaussee 5<br>
    15344 Strausberg<br>Telefon: 03341 / 52-0</p>
    <p>Dreifertstraße 12<br>03044 Cottbus</p>
    </body></html>"""
    results = extract(
        source,
        "text/html",
        extractor="heuristic",
        parser=NullParser(),
        country="de",
    )
    raw = {address.raw for address in results}
    assert "Sonnenburger Weg 3 16269 Wriezen" in raw
    assert "Prötzeler Chaussee 5 15344 Strausberg" in raw
    assert "Dreifertstraße 12 03044 Cottbus" in raw


def test_phone_only_block_is_not_an_address() -> None:
    results = extract(
        "<html><body><p>+63 2 1234 5678</p></body></html>",
        "text/html",
        extractor="heuristic",
        parser=NullParser(),
    )
    assert results == []


def test_results_are_ranked_by_confidence() -> None:
    source = """<html><body>
    <p>42 Rizal St, Quezon City 1100</p>
    <address>1 Bonifacio Ave, Pasig 1600</address>
    </body></html>"""
    results = extract(source, "text/html", extractor="heuristic", parser=NullParser())
    assert [item.confidence for item in results] == sorted(
        (item.confidence for item in results), reverse=True
    )


def test_empty_input_returns_empty_list() -> None:
    assert extract("", "text/html", extractor="heuristic") == []


def test_version_is_exposed() -> None:
    import careof

    assert careof.__version__
    assert careof.__version__.count(".") >= 1


def test_apache_default_page_address_tag_is_ignored() -> None:
    source = (
        "<html><body><address>Apache/2.4.52 (Ubuntu) Server at "
        "example.com Port 443</address></body></html>"
    )
    assert extract(source, "text/html", extractor="heuristic") == []
