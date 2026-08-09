"""Tests for the one-shot hybrid search script."""

import argparse
import json
from typing import Any

import httpx

import scripts.hybrid_search as hybrid_search


class FakeClient:
    """Minimal HTTP client fake for script request tests."""

    def __init__(self, responses: list[httpx.Response]) -> None:
        self.responses = iter(responses)
        self.requests: list[httpx.Request] = []

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, *_args: Any) -> None:
        return None

    def get(self, url: str) -> httpx.Response:
        request = httpx.Request("GET", url)
        self.requests.append(request)
        response = next(self.responses)
        response.request = request
        return response

    def post(self, url: str, *, json: dict[str, Any]) -> httpx.Response:
        request = httpx.Request("POST", url, json=json)
        self.requests.append(request)
        response = next(self.responses)
        response.request = request
        return response


def test_run_search_preserves_api_envelope_and_sends_alpha(monkeypatch: Any) -> None:
    """The script should print the same envelope and pass optional alpha to REST."""
    fake_client = FakeClient(
        [
            httpx.Response(200, json={"status": 200, "data": {"status": "healthy"}}),
            httpx.Response(200, json={"status": 200, "data": {"results": []}}),
        ]
    )
    monkeypatch.setattr(hybrid_search.httpx, "Client", lambda **_kwargs: fake_client)
    args = argparse.Namespace(corpus="test", query="hello world", alpha=0.25, top_k=7)

    result = hybrid_search.run_search(args)

    assert result == {"status": 200, "data": {"results": []}}
    assert fake_client.requests[1].url.path == "/v1/corpus/test/query/hybrid"
    assert json.loads(fake_client.requests[1].content) == {"query": "hello world", "top_k": 7, "alpha": 0.25}


def test_run_search_omits_alpha_when_defaulted(monkeypatch: Any) -> None:
    """The default alpha should remain service-configured like the MCP tool."""
    fake_client = FakeClient(
        [
            httpx.Response(200, json={"status": 200, "data": {"status": "healthy"}}),
            httpx.Response(200, json={"status": 200, "data": {"results": []}}),
        ]
    )
    monkeypatch.setattr(hybrid_search.httpx, "Client", lambda **_kwargs: fake_client)
    args = argparse.Namespace(corpus="test", query="hello", alpha=None, top_k=10)

    hybrid_search.run_search(args)

    assert json.loads(fake_client.requests[1].content) == {"query": "hello", "top_k": 10}
