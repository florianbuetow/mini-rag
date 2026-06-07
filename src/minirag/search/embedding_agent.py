"""LM Studio embedding agent: batched calls to an OpenAI-compatible endpoint.

Encapsulates the embedding HTTP call so the provider layer only deals with vectors.
Chunks are sent in batches of ``batch_size`` per request, sequentially — a single
local LM Studio instance serializes embedding work, so client-side request
concurrency is intentionally omitted.
"""

import logging
from collections.abc import Mapping
from typing import cast

import httpx

logger = logging.getLogger(__name__)


class EmbeddingAgent:
    """Embed batches of text via an LM Studio (OpenAI-compatible) endpoint."""

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        batch_size: int,
        timeout_seconds: float,
        transport: httpx.BaseTransport | None,
    ) -> None:
        """Initialize the agent.

        Args:
            base_url: OpenAI-compatible base URL (e.g. ``http://127.0.0.1:1234/v1``).
            model: Embedding model identifier as exposed by the endpoint.
            batch_size: Maximum number of chunks per request.
            timeout_seconds: Per-request timeout.
            transport: httpx transport to use; pass ``None`` for a real network
                client, or a mock transport in tests.
        """
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than 0")
        self._embeddings_url = base_url.rstrip("/") + "/embeddings"
        self._endpoint = base_url
        self._model = model
        self._batch_size = batch_size
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    def embed_batches(self, chunks: list[str]) -> list[list[float]]:
        """Embed every chunk, returning vectors in the same order as the input.

        Raises:
            RuntimeError: If the endpoint is unreachable/errors, or returns a number
                of vectors that does not match the number of inputs.
        """
        if len(chunks) == 0:
            return []

        vectors: list[list[float]] = []
        with httpx.Client(timeout=self._timeout_seconds, transport=self._transport) as client:
            for batch_start in range(0, len(chunks), self._batch_size):
                batch = chunks[batch_start : batch_start + self._batch_size]
                vectors.extend(self._embed_one_batch(client, batch))
        return vectors

    def _embed_one_batch(self, client: httpx.Client, batch: list[str]) -> list[list[float]]:
        """Embed a single batch and validate the response shape."""
        payload = {"model": self._model, "input": batch}
        try:
            response = client.post(self._embeddings_url, json=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("LM Studio embeddings request to %s failed: %s", self._endpoint, exc)
            raise RuntimeError(f"LM Studio embeddings request to {self._endpoint} failed: {exc}") from exc

        vectors = _vectors_from_response(response.json())
        if len(vectors) != len(batch):
            raise RuntimeError(f"LM Studio returned {len(vectors)} embeddings for {len(batch)} inputs from {self._endpoint}")
        return vectors


def _vectors_from_response(payload: object) -> list[list[float]]:
    """Extract embedding vectors from an OpenAI-compatible response, ordered by index."""
    if not isinstance(payload, dict):
        raise RuntimeError("LM Studio embeddings response was not a JSON object")
    payload_map = cast(Mapping[str, object], payload)
    data = payload_map.get("data")
    if not isinstance(data, list):
        raise RuntimeError("LM Studio embeddings response did not contain a 'data' list")

    data_items = cast(list[object], data)
    indexed: list[tuple[int, list[float]]] = []
    for position, item in enumerate(data_items):
        if not isinstance(item, dict):
            raise RuntimeError("LM Studio embeddings response contained a non-object data item")
        item_map = cast(Mapping[str, object], item)
        raw_embedding = item_map.get("embedding")
        if not isinstance(raw_embedding, list):
            raise RuntimeError("LM Studio embeddings response item had no 'embedding' list")
        raw_values = cast(list[object], raw_embedding)
        vector = [_to_float(value) for value in raw_values]
        index_value = item_map.get("index")
        order = index_value if isinstance(index_value, int) and not isinstance(index_value, bool) else position
        indexed.append((order, vector))

    indexed.sort(key=lambda pair: pair[0])
    return [vector for _, vector in indexed]


def _to_float(value: object) -> float:
    """Convert a JSON-decoded numeric value to float, rejecting non-numbers."""
    if isinstance(value, bool):
        raise RuntimeError("LM Studio embeddings response contained a boolean value")
    if isinstance(value, (int, float)):
        return float(value)
    raise RuntimeError("LM Studio embeddings response contained a non-numeric embedding value")
