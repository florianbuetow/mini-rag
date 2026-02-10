"""Embeddings abstraction used by orchestration and backend composition."""

from typing import Protocol


class Embeddings(Protocol):
    """Contract for embedding providers used by query/index pipelines."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed each input text into a dense vector."""
        ...
