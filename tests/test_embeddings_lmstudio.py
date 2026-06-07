"""Unit tests for the LM Studio embeddings provider."""

import json
import logging
import math
from collections.abc import Callable

import httpx
import pytest
import tiktoken

from minirag.search.embedding_agent import EmbeddingAgent
from minirag.search.embeddings_lmstudio import LMStudioEmbeddings


def _provider(handler: Callable[[httpx.Request], httpx.Response], *, dimension: int, max_tokens: int | None = None) -> LMStudioEmbeddings:
    agent = EmbeddingAgent(
        base_url="http://test-host:1234/v1",
        model="bge",
        batch_size=32,
        timeout_seconds=5.0,
        transport=httpx.MockTransport(handler),
    )
    return LMStudioEmbeddings(agent=agent, expected_dimension=dimension, max_tokens=max_tokens)


def _embedding_response(vectors: list[list[float]]) -> httpx.Response:
    data = [{"embedding": vector, "index": index} for index, vector in enumerate(vectors)]
    return httpx.Response(200, json={"data": data, "object": "list"})


def test_lmstudio_vectors_unit_normalized() -> None:
    """An un-normalized model vector is returned unit-normalized."""

    def handler(_: httpx.Request) -> httpx.Response:
        return _embedding_response([[3.0, 4.0]])

    [vector] = _provider(handler, dimension=2).embed(["x"])

    assert math.isclose(math.sqrt(sum(value * value for value in vector)), 1.0, abs_tol=1e-9)
    assert math.isclose(vector[0], 0.6, abs_tol=1e-9)
    assert math.isclose(vector[1], 0.8, abs_tol=1e-9)


def test_embed_rejects_mismatched_vector_length() -> None:
    """A document embedding whose length differs from the configured dimension errors."""

    def handler(_: httpx.Request) -> httpx.Response:
        return _embedding_response([[0.1] * 300])

    with pytest.raises(ValueError, match=r"configured=1024.*actual=300"):
        _provider(handler, dimension=1024).embed(["a document chunk"])


def test_query_embed_rejects_mismatched_vector_length() -> None:
    """A query embedding whose length differs from the configured dimension errors."""

    def handler(_: httpx.Request) -> httpx.Response:
        return _embedding_response([[0.1] * 300])

    with pytest.raises(ValueError, match=r"configured=1024.*actual=300"):
        _provider(handler, dimension=1024).embed(["a user query"])


def test_zero_vector_is_rejected() -> None:
    """A zero-norm vector cannot be normalized and is rejected."""

    def handler(_: httpx.Request) -> httpx.Response:
        return _embedding_response([[0.0, 0.0]])

    with pytest.raises(ValueError, match="norm must be greater than 0"):
        _provider(handler, dimension=2).embed(["x"])


def test_overbudget_query_warns_and_truncates(caplog: pytest.LogCaptureFixture) -> None:
    """An over-budget query is reduced to the budget with a warning, never silently."""
    sent_inputs: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        inputs = json.loads(request.content.decode())["input"]
        sent_inputs.extend(inputs)
        return _embedding_response([[1.0, 0.0]] * len(inputs))

    provider = _provider(handler, dimension=2, max_tokens=5)
    long_query = " ".join(f"word{index}" for index in range(40))

    with caplog.at_level(logging.WARNING):
        provider.embed([long_query])

    assert any("over-budget" in record.message.lower() for record in caplog.records)
    encoding = tiktoken.get_encoding("cl100k_base")
    assert len(encoding.encode(sent_inputs[0])) <= 5


def test_within_budget_input_is_not_truncated() -> None:
    """An input already within budget is sent unchanged with no warning."""
    sent_inputs: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        inputs = json.loads(request.content.decode())["input"]
        sent_inputs.extend(inputs)
        return _embedding_response([[1.0, 0.0]] * len(inputs))

    _provider(handler, dimension=2, max_tokens=512).embed(["a short query"])

    assert sent_inputs == ["a short query"]
