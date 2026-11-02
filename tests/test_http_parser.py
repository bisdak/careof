from __future__ import annotations

import json
from unittest.mock import patch

from careof.parse import LibpostalHTTPParser


class MockResponse:
    def __init__(self, body: object) -> None:
        self.body = json.dumps(body).encode()

    def __enter__(self) -> object:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


def test_http_parser_sends_hints_and_normalizes_response() -> None:
    parser = LibpostalHTTPParser(
        "http://localhost:8080/",
        language="de",
        country="at",
    )
    response = MockResponse(
        [
            {"label": "road", "value": "karl-farkas-gasse"},
            {"label": "house_number", "value": "22"},
            {"label": "postcode", "value": "1030"},
            {"label": "city", "value": "wien"},
        ]
    )

    with patch("careof.parse.urlopen", return_value=response) as open_url:
        result = parser.parse(
            "Karl-Farkas-Gasse 22 1030 Wien",
            language="de",
            country="at",
        )

    request = open_url.call_args.args[0]
    assert request.full_url == "http://localhost:8080/parser"
    assert json.loads(request.data) == {
        "query": "Karl-Farkas-Gasse 22 1030 Wien",
        "language": "de",
        "country": "at",
    }
    assert result == {
        "house_number": "22",
        "road": "karl-farkas-gasse",
        "city": "wien",
        "postcode": "1030",
    }


def test_http_expansion_returns_first_normalized_value() -> None:
    parser = LibpostalHTTPParser("http://localhost:8080")
    with patch(
        "careof.parse.urlopen",
        return_value=MockResponse(
            [
                "karl-farkas-gasse 22 1030 wien",
                "karl-farkas gasse 22 1030 wien",
            ]
        ),
    ) as open_url:
        result = parser.expand("Karl-Farkas-Gasse 22 1030 Wien")

    request = open_url.call_args.args[0]
    assert request.full_url == "http://localhost:8080/expand"
    assert result == "karl-farkas-gasse 22 1030 wien"


def test_http_errors_degrade_gracefully() -> None:
    parser = LibpostalHTTPParser("http://127.0.0.1:1", timeout=0.01)
    assert parser.parse("123 Main Street") == {}
    assert parser.expand("123 Main Street") is None
