from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch

import httpx
import pytest

from careof.url_cli import fetch_url, main


class FakeResponse:
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = chunks
        self.headers = {"Content-Type": "text/html; charset=utf-8"}
        self.url = "https://example.test/contact"

    def raise_for_status(self) -> None:
        return None

    def iter_bytes(self):
        yield from self.chunks


class FakeClient:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response

    def __enter__(self) -> object:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    @contextmanager
    def stream(self, method: str, url: str):
        assert method == "GET"
        assert url == "https://example.test/contact"
        yield self.response


def test_fetch_url_returns_body_type_and_redirected_url() -> None:
    response = FakeResponse([b"<html>", b"address</html>"])
    with patch("httpx.Client", return_value=FakeClient(response)):
        body, content_type, final_url = fetch_url("https://example.test/contact")

    assert body == b"<html>address</html>"
    assert content_type == "text/html; charset=utf-8"
    assert final_url == "https://example.test/contact"


def test_fetch_url_rejects_non_http_schemes() -> None:
    with pytest.raises(ValueError, match="http:// or https://"):
        fetch_url("file:///etc/passwd")


def test_fetch_url_enforces_response_size_limit() -> None:
    response = FakeResponse([b"12345", b"67890"])
    with (
        patch("httpx.Client", return_value=FakeClient(response)),
        pytest.raises(ValueError, match="size limit"),
    ):
        fetch_url("https://example.test/contact", max_bytes=8)


def test_url_command_fetches_then_extracts(capsys: pytest.CaptureFixture[str]) -> None:
    html = b"<html><body><p>123 Main Street, Springfield, IL 62704</p></body></html>"
    response = FakeResponse([html])
    with patch("httpx.Client", return_value=FakeClient(response)):
        status = main(
            ["https://example.test/contact", "--extractor", "heuristic", "--ndjson"]
        )

    assert status == 0
    assert '"raw": "123 Main Street, Springfield, IL 62704"' in capsys.readouterr().out


def test_url_command_reports_http_errors(capsys: pytest.CaptureFixture[str]) -> None:
    with patch("httpx.Client", side_effect=httpx.ConnectError("connection refused")):
        status = main(["https://example.test/contact"])

    assert status == 2
    assert "request failed" in capsys.readouterr().err
