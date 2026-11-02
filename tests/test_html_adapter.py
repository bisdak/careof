from __future__ import annotations

from careof.adapters.html import parse_html


def test_offsets_point_at_block_text() -> None:
    source = """
    <html><body>
      <h1>Contact</h1>
      <p>Our office is at <b>123 Mabini St.</b><br>Makati City 1223</p>
      <div>Unit 4B, 77 Ayala Ave<div>Tel: 123-4567</div></div>
    </body></html>
    """
    document = parse_html(source)
    assert document.blocks
    for block in document.blocks:
        assert document.text[block.start : block.end] == block.text


def test_br_and_nested_divs_do_not_glue_text() -> None:
    source = (
        "<html><body><div>Unit 4B, 77 Ayala Ave<br>Makati City"
        "<div>Tel: 123-4567</div></div></body></html>"
    )
    document = parse_html(source)
    joined = "\n".join(block.text for block in document.blocks)
    assert "77 Ayala Ave\nMakati City" in joined
    assert "Tel: 123-4567" in joined


def test_script_and_style_are_not_text() -> None:
    source = """
    <html><head><style>.x { color: red }</style></head>
    <body><script>var address = "999 Script St";</script>
    <p>42 Real St, Springfield</p></body></html>
    """
    document = parse_html(source)
    assert "999 Script St" not in document.text
    assert "color: red" not in document.text
    assert "42 Real St" in document.text


def test_lang_and_title_metadata() -> None:
    document = parse_html(
        '<html lang="en-PH"><head><title>Contact us</title></head><body>x</body></html>'
    )
    assert document.meta["language"] == "en"
    assert document.meta["title"] == "Contact us"


def test_empty_document_is_safe() -> None:
    document = parse_html("")
    assert document.text == ""
    assert document.blocks == []
    assert document.structured == []


def test_xml_declaration_is_tolerated() -> None:
    source = (
        '<?xml version="1.0" encoding="utf-8"?>'
        "<html><body><p>12 Rizal St, Quezon City 1100</p></body></html>"
    )
    document = parse_html(source)
    assert "12 Rizal St" in document.text


def test_broken_map_url_is_ignored() -> None:
    source = (
        '<html><body><a href="http://[::1">bad</a>'
        "<p>12 Rizal St, Quezon City 1100</p></body></html>"
    )
    document = parse_html(source)
    assert all(item.source != "map-link" for item in document.structured)
