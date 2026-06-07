"""Unit tests for the LM Studio embedding agent."""

import json
from collections.abc import Callable

import httpx
import pytest

from minirag.search.embedding_agent import EmbeddingAgent

BASE_URL = "http://test-host:1234/v1"


def _agent(handler: Callable[[httpx.Request], httpx.Response], *, batch_size: int = 32) -> EmbeddingAgent:
    return EmbeddingAgent(
        base_url=BASE_URL,
        model="bge",
        batch_size=batch_size,
        timeout_seconds=5.0,
        transport=httpx.MockTransport(handler),
    )


def _embedding_response(vectors: list[list[float]]) -> httpx.Response:
    data = [{"embedding": vector, "index": index} for index, vector in enumerate(vectors)]
    return httpx.Response(200, json={"data": data, "object": "list"})


def test_agent_returns_1024_dim_vector() -> None:
    """A single input yields one 1024-dimensional vector."""

    def handler(_: httpx.Request) -> httpx.Response:
        return _embedding_response([[0.1] * 1024])

    vectors = _agent(handler).embed_batches(["hello"])

    assert len(vectors) == 1
    assert len(vectors[0]) == 1024


def test_agent_posts_to_embeddings_path() -> None:
    """The agent posts to the OpenAI-compatible /v1/embeddings path."""
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return _embedding_response([[0.5]])

    _agent(handler).embed_batches(["x"])

    assert seen["url"] == "http://test-host:1234/v1/embeddings"


def test_agent_unreachable_endpoint_errors() -> None:
    """An unreachable endpoint raises an explicit error naming the endpoint."""

    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    with pytest.raises(RuntimeError, match=r"http://test-host:1234/v1"):
        _agent(handler).embed_batches(["hello"])


def test_agent_http_500_errors() -> None:
    """A non-success status raises an explicit error and returns no vector."""

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    with pytest.raises(RuntimeError):
        _agent(handler).embed_batches(["hello"])


def test_agent_missing_vectors_errors() -> None:
    """A response with fewer vectors than inputs raises a count-mismatch error."""

    def handler(_: httpx.Request) -> httpx.Response:
        return _embedding_response([[0.1] * 4, [0.2] * 4])

    with pytest.raises(RuntimeError, match="2 embeddings for 3 inputs"):
        _agent(handler).embed_batches(["a", "b", "c"])


def test_batches_preserve_order_across_requests() -> None:
    """Inputs exceeding batch_size are split into sequential requests, order preserved."""
    batch_sizes: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        inputs = json.loads(request.content.decode())["input"]
        batch_sizes.append(len(inputs))
        data = [{"embedding": [float(len(text))], "index": index} for index, text in enumerate(inputs)]
        return httpx.Response(200, json={"data": data})

    vectors = _agent(handler, batch_size=2).embed_batches(["a", "bb", "ccc", "dddd", "eeeee"])

    assert [vector[0] for vector in vectors] == [1.0, 2.0, 3.0, 4.0, 5.0]
    assert batch_sizes == [2, 2, 1]


def test_vectors_sorted_by_index() -> None:
    """Vectors are returned in input order even if the response is out of order."""

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"data": [{"embedding": [2.0], "index": 1}, {"embedding": [1.0], "index": 0}]},
        )

    vectors = _agent(handler).embed_batches(["a", "b"])

    assert [vector[0] for vector in vectors] == [1.0, 2.0]


def test_empty_input_returns_no_vectors() -> None:
    """Embedding an empty list makes no request and returns no vectors."""

    def handler(_: httpx.Request) -> httpx.Response:
        raise AssertionError("no request should be made for empty input")

    assert _agent(handler).embed_batches([]) == []
