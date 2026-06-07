"""LM Studio embedding provider implementing the Embeddings contract."""

import logging
import math

import tiktoken

from minirag.search.embedding_agent import EmbeddingAgent

logger = logging.getLogger(__name__)


class LMStudioEmbeddings:
    """Embeddings provider backed by an LM Studio embedding model."""

    def __init__(self, agent: EmbeddingAgent, expected_dimension: int, *, max_tokens: int | None) -> None:
        """Initialize the provider.

        Args:
            agent: Embedding agent that performs the batched LM Studio calls.
            expected_dimension: Required embedding dimension for the active model.
            max_tokens: Per-input token ceiling, or ``None`` to disable the guard.
                Inputs exceeding it are reduced with a warning so the model never
                silently truncates them. Token counts use the ``cl100k_base`` encoding.

        Raises:
            ValueError: If the expected dimension or max_tokens is not positive.
        """
        if expected_dimension <= 0:
            raise ValueError("expected_dimension must be greater than 0")
        if max_tokens is not None and max_tokens <= 0:
            raise ValueError("max_tokens must be greater than 0")
        self._agent = agent
        self._dimension = expected_dimension
        self._max_tokens = max_tokens

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed each text into a unit-normalized vector of the configured dimension.

        Raises:
            ValueError: If a returned vector does not match the configured dimension.
            RuntimeError: If the embedding endpoint is unreachable or returns an
                inconsistent number of vectors (propagated from the agent).
        """
        prepared = [self._within_budget(text) for text in texts]
        raw_vectors = self._agent.embed_batches(prepared)
        normalized: list[list[float]] = []
        for vector in raw_vectors:
            if len(vector) != self._dimension:
                raise ValueError(f"embedding dimension mismatch: configured={self._dimension}, actual={len(vector)}")
            normalized.append(_normalize(vector))
        return normalized

    def _within_budget(self, text: str) -> str:
        """Reduce an input to the token budget, warning if truncation is needed."""
        if self._max_tokens is None:
            return text
        encoding = tiktoken.get_encoding("cl100k_base")
        tokens = encoding.encode(text)
        if len(tokens) <= self._max_tokens:
            return text
        logger.warning(
            "Reducing over-budget embedding input from %d to %d tokens to avoid silent truncation",
            len(tokens),
            self._max_tokens,
        )
        return encoding.decode(tokens[: self._max_tokens])


def _normalize(vector: list[float]) -> list[float]:
    """Normalize a vector to unit length."""
    norm = math.sqrt(sum(value * value for value in vector))
    if norm <= 0.0:
        raise ValueError("embedding vector norm must be greater than 0")
    return [value / norm for value in vector]
