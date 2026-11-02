from __future__ import annotations

from careof.adapters.html import parse_html
from careof.adapters.markdown import markdown_to_text
from careof.adapters.text import normalize
from careof.candidates import build_candidates, score_block


def test_masking_preserves_length() -> None:
    source = """# Contact

Our office is at **123 Mabini Street, Makati City 1223**.

```
999 Fake Street, Nowhereville 0000
```

[Map](https://example.com/maps?q=456+Luna+St) and `789 Hidden St`.
"""
    masked = markdown_to_text(source)
    assert len(masked) == len(normalize(source))


def test_markdown_hides_code_but_keeps_addresses() -> None:
    text = markdown_to_text(
        "**123 Mabini Street, Makati City 1223**\n\n```\n999 Fake St\n```\n"
    )
    assert "123 Mabini Street" in text
    assert "999 Fake St" not in text


def test_navigation_blocks_are_not_candidates() -> None:
    source = (
        "<html><body><nav>Home About Contact</nav>"
        "<h1>Our office</h1><p>123 Mabini Street, Makati City 1223</p>"
        "</body></html>"
    )
    document = parse_html(source)
    candidates = build_candidates(document)
    assert candidates
    assert all("Home About" not in candidate.text for candidate in candidates)
    assert any("123 Mabini" in candidate.text for candidate in candidates)


def test_score_prefers_address_blocks() -> None:
    assert score_block("123 Mabini Street, Makati City 1223") >= 4
    assert score_block("Home About Contact") < 2


def test_country_signal_uses_country_catalog_and_common_aliases() -> None:
    assert score_block("Austria") == 1.0
    assert score_block("United States") == 1.0
    assert score_block("UK") == 1.0
