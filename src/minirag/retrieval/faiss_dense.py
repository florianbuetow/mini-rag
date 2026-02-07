"""FAISS dense retrieval implementation."""

import importlib
import logging
from pathlib import Path
from typing import Protocol, cast

import numpy as np

from minirag.retrieval.dense_interface import DenseRetrieval

logger = logging.getLogger(__name__)


class FaissIndex(Protocol):
    """Subset of FAISS index methods used by this adapter."""

    ntotal: int

    def add_with_ids(self, vectors: np.ndarray, ids: np.ndarray) -> None:
        """Insert vectors with external IDs."""
        ...

    def search(self, query_vectors: np.ndarray, top_k: int) -> tuple[np.ndarray, np.ndarray]:
        """Search for nearest vectors by inner product."""
        ...


class FaissModule(Protocol):
    """Subset of FAISS module API used by this adapter."""

    def IndexFlatIP(self, dimension: int) -> object:
        """Create IndexFlatIP index."""
        ...

    def IndexIDMap(self, index: object) -> FaissIndex:
        """Wrap an index with external ID mapping."""
        ...

    def write_index(self, index: FaissIndex, path: str) -> None:
        """Persist an index to disk."""
        ...

    def read_index(self, path: str) -> FaissIndex:
        """Load an index from disk."""
        ...


class FAISSDense(DenseRetrieval):
    """FAISS dense retrieval using IndexIDMap(IndexFlatIP)."""

    def __init__(self, dimension: int, index_dir: Path, nprobe: int) -> None:
        """Initialize and load or create FAISS index.

        Args:
            dimension: Embedding dimension.
            index_dir: Directory for FAISS index persistence.
            nprobe: Probe count for FAISS indexes that support it.
        """
        if dimension <= 0:
            raise ValueError("dimension must be greater than 0")

        if nprobe <= 0:
            raise ValueError("nprobe must be greater than 0")

        self._dimension = dimension
        self._index_dir = index_dir
        self._index_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self._index_dir / "index.faiss"

        faiss_module = importlib.import_module("faiss")
        self._faiss = cast(FaissModule, faiss_module)

        if self._index_path.exists():
            self._index = self._faiss.read_index(str(self._index_path))
            logger.info("Loaded FAISS index from %s", self._index_path)
        else:
            self._index = self._create_index()
            self._persist_index()
            logger.info("Created FAISS index at %s", self._index_path)

    def _create_index(self) -> FaissIndex:
        """Create an empty IndexIDMap(IndexFlatIP) index."""
        inner_index = self._faiss.IndexFlatIP(self._dimension)
        return self._faiss.IndexIDMap(inner_index)

    def _persist_index(self) -> None:
        """Write the in-memory index to disk."""
        self._faiss.write_index(self._index, str(self._index_path))

    def _to_normalized_matrix(self, vector: list[float]) -> np.ndarray:
        """Convert a vector to a normalized FAISS matrix row."""
        if len(vector) != self._dimension:
            raise ValueError(f"embedding dimension mismatch: configured={self._dimension}, provided={len(vector)}")

        array = np.array(vector, dtype=np.float32)
        norm = np.linalg.norm(array)
        if norm <= 0.0:
            raise ValueError("embedding norm must be greater than 0")

        normalized = array / norm
        matrix = normalized.reshape(1, self._dimension)
        return matrix

    def index(self, chunk_id: int, embedding: list[float]) -> None:
        """Index one chunk embedding by chunk ID."""
        if chunk_id <= 0:
            raise ValueError("chunk_id must be greater than 0")

        vector_matrix = self._to_normalized_matrix(embedding)
        id_vector = np.array([chunk_id], dtype=np.int64)
        self._index.add_with_ids(vector_matrix, id_vector)
        self._persist_index()

    def search(self, query_embedding: list[float], top_k: int) -> list[tuple[int, float]]:
        """Search for nearest chunk IDs by cosine similarity."""
        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")

        if self._index.ntotal == 0:
            return []

        query_matrix = self._to_normalized_matrix(query_embedding)
        score_matrix, id_matrix = self._index.search(query_matrix, top_k)
        scores = score_matrix[0].tolist()
        ids = id_matrix[0].tolist()

        results: list[tuple[int, float]] = []
        for chunk_id, score in zip(ids, scores, strict=True):
            if chunk_id == -1:
                continue

            normalized_score = float(score)
            if normalized_score < 0.0:
                normalized_score = 0.0
            if normalized_score > 1.0:
                normalized_score = 1.0

            results.append((int(chunk_id), normalized_score))

        return results

    def destroy(self) -> None:
        """Destroy and recreate the FAISS index."""
        self._index = self._create_index()
        self._persist_index()
        logger.info("Destroyed FAISS index at %s", self._index_path)
