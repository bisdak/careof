from __future__ import annotations

from careof.adapters.html import parse_html


def test_json_ld_postal_address() -> None:
    source = """
    <html><head><script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "LocalBusiness",
      "address": {
        "@type": "PostalAddress",
        "streetAddress": "123 Mabini Street",
        "addressLocality": "Makati City",
        "addressRegion": "Metro Manila",
        "postalCode": "1223",
        "addressCountry": "PH"
      }
    }
    </script></head><body>Hello</body></html>
    """
    document = parse_html(source)
    assert len(document.structured) == 1
    address = document.structured[0]
    assert address.source == "json-ld"
    assert address.components["city"] == "Makati City"
    assert address.components["postcode"] == "1223"


def test_json_ld_with_trailing_commas() -> None:
    source = """
    <html><head><script type="application/ld+json">
    {"@type": "PostalAddress", "streetAddress": "9 Ayala Ave",
     "addressLocality": "Makati", "postalCode": "1226",}
    </script></head><body></body></html>
    """
    document = parse_html(source)
    assert document.structured
    assert document.structured[0].components["street"] == "9 Ayala Ave"


def test_microdata_postal_address() -> None:
    source = """
    <html><body>
    <div itemscope itemtype="https://schema.org/PostalAddress">
      <span itemprop="streetAddress">7 Rizal St</span>
      <span itemprop="addressLocality">Quezon City</span>
      <span itemprop="postalCode">1100</span>
      <span itemprop="addressCountry">PH</span>
    </div>
    </body></html>
    """
    document = parse_html(source)
    assert len(document.structured) == 1
    address = document.structured[0]
    assert address.source == "microdata"
    assert address.components["street"] == "7 Rizal St"
    assert address.components["postcode"] == "1100"


def test_address_tag_and_offsets() -> None:
    source = (
        "<html><body><p>Intro</p>"
        "<address>456 Luna St.<br>Makati City 1223</address>"
        "</body></html>"
    )
    document = parse_html(source)
    tagged = [item for item in document.structured if item.source == "address-tag"]
    assert len(tagged) == 1
    assert tagged[0].start is not None
    assert "456 Luna St." in tagged[0].raw
    assert "456 Luna St." in document.text


def test_og_meta_address() -> None:
    source = """
    <html><head>
      <meta property="og:street-address" content="1 Bonifacio Ave">
      <meta property="og:locality" content="Pasig">
      <meta property="og:postal-code" content="1600">
    </head><body></body></html>
    """
    document = parse_html(source)
    assert len(document.structured) == 1
    assert document.structured[0].components["street"] == "1 Bonifacio Ave"


def test_map_link_query_parameter() -> None:
    source = """
    <html><body><a href="https://www.google.com/maps?q=7+Rizal+St+Quezon+City">
    Directions</a></body></html>
    """
    document = parse_html(source)
    links = [item for item in document.structured if item.source == "map-link"]
    assert len(links) == 1
    assert "7 Rizal St" in links[0].raw
