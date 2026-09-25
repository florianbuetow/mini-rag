"""FAISS dense retrieval implementation."""

import importlib
import json
import logging
import re
import zipfile
from pathlib import Path
from typing import Protocol, cast

import numpy as np

from minirag.retrieval.dense_interface import DenseRetrieval
from minirag.retrieval.errors import IndexConfigurationError
from minirag.search.types import ScoredChunk

logger = logging.getLogger(__name__)

_IVF_FLAT_PATTERN = re.compile(r"IVF([1-9][0-9]*),Flat")
_INDEX_METADATA_VERSION = 1


def normalize_faiss_index_type(index_type: str) -> str:
    """Validate and canonicalize a supported FAISS index type."""
    normalized = index_type.strip()
    if normalized in {"IndexFlatIP", "Flat"}:
        return "IndexFlatIP"
    if _IVF_FLAT_PATTERN.fullmatch(normalized) is not None:
        return normalized
    raise ValueError(
        f"index.faiss.index_type must be 'IndexFlatIP', 'Flat', or 'IVF<nlist>,Flat' with a positive nlist; got {index_type!r}"
    )


class FaissIndex(Protocol):
    """Subset of FAISS index methods used by this adapter."""

    ntotal: int
    d: int
    is_trained: bool
    metric_type: int
    index: object

    def add_with_ids(self, vectors: np.ndarray, ids: np.ndarray) -> None:
        """Insert vectors with external IDs."""
        ...

    def train(self, vectors: np.ndarray) -> None:
        """Train an index that requires representative vectors."""
        ...

    def search(self, query_vectors: np.ndarray, top_k: int) -> tuple[np.ndarray, np.ndarray]:
        """Search by inner product on unit-normalized vectors."""
        ...

    def remove_ids(self, ids: np.ndarray) -> int:
        """Remove vectors by external IDs."""
        ...


class FaissIVFIndex(Protocol):
    """Subset of IVF properties used by this adapter."""

    nlist: int


class FaissClusteringParameters(Protocol):
    """FAISS clustering thresholds used to decide when to train."""

    min_points_per_centroid: int


class FaissParameterSpace(Protocol):
    """FAISS runtime parameter setter."""

    def set_index_parameter(self, index: FaissIndex, name: str, value: float) -> None:
        """Set one search-time parameter through index wrappers."""
        ...


class FaissModule(Protocol):
    """Subset of FAISS module API used by this adapter."""

    METRIC_INNER_PRODUCT: int

    def index_factory(self, dimension: int, description: str, metric: int) -> object:
        """Create an index from a factory description."""
        ...

    def IndexIDMap2(self, index: object) -> FaissIndex:
        """Wrap an index with external ID mapping."""
        ...

    def ClusteringParameters(self) -> FaissClusteringParameters:
        """Return the default clustering parameters."""
        ...

    def ParameterSpace(self) -> FaissParameterSpace:
        """Create a runtime parameter setter."""
        ...

    def extract_index_ivf(self, index: FaissIndex) -> FaissIVFIndex:
        """Extract an IVF index through wrappers."""
        ...

    def downcast_index(self, index: object) -> object:
        """Return the concrete Python wrapper for an index."""
        ...

    def write_index(self, index: FaissIndex, path: str) -> None:
        """Persist an index to disk."""
        ...

    def read_index(self, path: str) -> FaissIndex:
        """Load an index from disk."""
        ...


class FAISSDense(DenseRetrieval):
    """FAISS cosine-similarity retrieval with external chunk IDs."""

    def __init__(self, dimension: int, index_dir: Path, index_type: str, nprobe: int) -> None:
        """Initialize and load or create a configured FAISS index."""
        if dimension <= 0:
            raise ValueError("dimension must be greater than 0")
        if nprobe <= 0:
            raise ValueError("nprobe must be greater than 0")

        self._dimension = dimension
        self._index_type = normalize_faiss_index_type(index_type)
        self._factory_spec = "Flat" if self._index_type == "IndexFlatIP" else self._index_type
        ivf_match = _IVF_FLAT_PATTERN.fullmatch(self._index_type)
        self._ivf_nlist = int(ivf_match.group(1)) if ivf_match is not None else None
        self._nprobe = nprobe
        self._index_dir = index_dir
        self._index_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self._index_dir / "index.faiss"
        self._metadata_path = self._index_dir / "index.meta.json"
        self._pending_path = self._index_dir / "pending.npz"
        self._index_temp_path = self._index_dir / "index.faiss.tmp"
        self._metadata_temp_path = self._index_dir / "index.meta.json.tmp"
        self._pending_temp_path = self._index_dir / "pending.npz.tmp"
        self._pending: dict[int, np.ndarray] = {}

        faiss_module = importlib.import_module("faiss")
        self._faiss = cast(FaissModule, faiss_module)
        if self._ivf_nlist is None:
            self._minimum_training_vectors = 0
        else:
            clustering_parameters = self._faiss.ClusteringParameters()
            points_per_centroid = int(clustering_parameters.min_points_per_centroid)
            self._minimum_training_vectors = self._ivf_nlist * points_per_centroid

        if self._index_path.exists():
            try:
                self._index = self._faiss.read_index(str(self._index_path))
            except (OSError, RuntimeError) as exc:
                raise IndexConfigurationError(f"invalid FAISS index at {self._index_path}; re-index this corpus") from exc
            self._validate_loaded_index()
            self._load_pending()
            self._apply_search_parameters()
            logger.info("Loaded FAISS %s index from %s", self._index_type, self._index_path)
        else:
            if self._metadata_path.exists() or self._pending_path.exists():
                raise IndexConfigurationError(f"incomplete FAISS persistence state in {self._index_dir}; re-index this corpus")
            self._index = self._create_index()
            self._apply_search_parameters()
            self._persist_index()
            logger.info("Created FAISS %s index at %s", self._index_type, self._index_path)

    def _create_index(self) -> FaissIndex:
        """Create an empty configured index with external ID mapping."""
        inner_index = self._faiss.index_factory(
            self._dimension,
            self._factory_spec,
            self._faiss.METRIC_INNER_PRODUCT,
        )
        if self._ivf_nlist is not None:
            return cast(FaissIndex, inner_index)
        return self._faiss.IndexIDMap2(inner_index)

    def _validate_loaded_index(self) -> None:
        """Verify persisted structure and configuration before accepting it."""
        if self._index.d != self._dimension:
            raise IndexConfigurationError(
                f"persisted FAISS index dimension {self._index.d} does not match configured dimension "
                f"{self._dimension}; re-index this corpus after changing the embedding provider"
            )
        if self._index.metric_type != self._faiss.METRIC_INNER_PRODUCT:
            raise IndexConfigurationError("persisted FAISS index does not use inner-product similarity; re-index this corpus")
        self._validate_loaded_structure()
        self._validate_loaded_metadata()

    def _validate_loaded_structure(self) -> None:
        """Verify the concrete FAISS family matches configuration."""
        if self._ivf_nlist is None:
            if type(self._index).__name__ not in {"IndexIDMap", "IndexIDMap2"}:
                raise IndexConfigurationError("persisted flat FAISS index does not preserve external chunk IDs; re-index this corpus")
            inner_type = type(self._faiss.downcast_index(self._index.index)).__name__
            structure_matches = inner_type == "IndexFlatIP"
        else:
            inner_type = type(self._index).__name__
            try:
                persisted_nlist = self._faiss.extract_index_ivf(self._index).nlist
            except RuntimeError:
                structure_matches = False
            else:
                structure_matches = inner_type == "IndexIVFFlat" and persisted_nlist == self._ivf_nlist
        if not structure_matches:
            raise IndexConfigurationError(
                f"persisted FAISS index structure {inner_type!r} does not match configured type {self._index_type!r}; re-index this corpus"
            )

    def _validate_loaded_metadata(self) -> None:
        """Verify persisted metadata when present."""
        if self._metadata_path.exists():
            try:
                metadata = json.loads(self._metadata_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise IndexConfigurationError(f"invalid FAISS metadata at {self._metadata_path}; re-index this corpus") from exc
            expected = {"version": _INDEX_METADATA_VERSION, "index_type": self._index_type}
            if metadata != expected:
                raise IndexConfigurationError(
                    f"persisted FAISS metadata {metadata!r} does not match configured type {self._index_type!r}; re-index this corpus"
                )

    def _apply_search_parameters(self) -> None:
        """Apply query-time parameters to supported approximate indexes."""
        if self._ivf_nlist is not None:
            self._faiss.ParameterSpace().set_index_parameter(self._index, "nprobe", float(self._nprobe))

    def _load_pending(self) -> None:
        """Restore vectors waiting for IVF training."""
        if not self._pending_path.exists():
            return
        if self._index.is_trained or self._ivf_nlist is None:
            raise IndexConfigurationError(f"unexpected pending FAISS vectors at {self._pending_path}; re-index this corpus")
        try:
            with np.load(self._pending_path, allow_pickle=False) as pending:
                ids = pending["ids"]
                vectors = pending["vectors"]
        except (OSError, ValueError, KeyError, EOFError, zipfile.BadZipFile) as exc:
            raise IndexConfigurationError(f"invalid pending FAISS vectors at {self._pending_path}; re-index this corpus") from exc
        if ids.dtype != np.int64 or ids.ndim != 1:
            raise IndexConfigurationError(f"invalid pending FAISS IDs at {self._pending_path}; re-index this corpus")
        if vectors.dtype != np.float32 or vectors.shape != (len(ids), self._dimension):
            raise IndexConfigurationError(f"invalid pending FAISS vectors at {self._pending_path}; re-index this corpus")
        if len(set(ids.tolist())) != len(ids):
            raise IndexConfigurationError(f"duplicate pending FAISS IDs at {self._pending_path}; re-index this corpus")
        id_values = cast(list[int], ids.tolist())
        self._pending = {int(chunk_id): cast(np.ndarray, vectors[position]).copy() for position, chunk_id in enumerate(id_values)}

    def _persist_index(self) -> None:
        """Atomically replace each persisted index snapshot component."""
        if self._pending:
            ids = np.fromiter(self._pending, dtype=np.int64, count=len(self._pending))
            vectors = np.stack(list(self._pending.values())).astype(np.float32, copy=False)
            try:
                with self._pending_temp_path.open("wb") as pending_file:
                    np.savez_compressed(pending_file, ids=ids, vectors=vectors)
                self._pending_temp_path.replace(self._pending_path)
            finally:
                self._pending_temp_path.unlink(missing_ok=True)

        try:
            self._faiss.write_index(self._index, str(self._index_temp_path))
            self._index_temp_path.replace(self._index_path)
        finally:
            self._index_temp_path.unlink(missing_ok=True)

        metadata = {"version": _INDEX_METADATA_VERSION, "index_type": self._index_type}
        try:
            self._metadata_temp_path.write_text(json.dumps(metadata, sort_keys=True) + "\n", encoding="utf-8")
            self._metadata_temp_path.replace(self._metadata_path)
        finally:
            self._metadata_temp_path.unlink(missing_ok=True)

        if not self._pending:
            self._pending_path.unlink(missing_ok=True)

    def _to_normalized_matrix(self, vector: list[float]) -> np.ndarray:
        """Convert a vector to a normalized FAISS matrix row."""
        if len(vector) != self._dimension:
            raise ValueError(f"embedding dimension mismatch: configured={self._dimension}, provided={len(vector)}")
        array = np.array(vector, dtype=np.float32)
        norm = np.linalg.norm(array)
        if norm <= 0.0:
            raise ValueError("embedding norm must be greater than 0")
        return (array / norm).reshape(1, self._dimension)

    def _train_if_ready(self) -> None:
        """Train IVF once FAISS's recommended sample count is available."""
        if self._index.is_trained or self._ivf_nlist is None or len(self._pending) < self._minimum_training_vectors:
            return
        ids = np.fromiter(self._pending, dtype=np.int64, count=len(self._pending))
        vectors = np.stack(list(self._pending.values())).astype(np.float32, copy=False)
        self._index.train(vectors)
        self._index.add_with_ids(vectors, ids)
        self._pending.clear()
        self._apply_search_parameters()

    def index(self, chunk_id: int, embedding: list[float]) -> None:
        """Index one chunk embedding by chunk ID."""
        if chunk_id <= 0:
            raise ValueError("chunk_id must be greater than 0")
        vector_matrix = self._to_normalized_matrix(embedding)
        if not self._index.is_trained:
            self._pending[chunk_id] = vector_matrix[0]
            return
        id_vector = np.array([chunk_id], dtype=np.int64)
        self._index.add_with_ids(vector_matrix, id_vector)

    def remove_ids(self, chunk_ids: list[int]) -> int:
        """Remove vectors by chunk ID. Return the number removed."""
        if len(chunk_ids) == 0:
            return 0
        unique_ids = set(chunk_ids)
        pending_removed = sum(self._pending.pop(chunk_id, None) is not None for chunk_id in unique_ids)
        if self._index.ntotal == 0:
            return pending_removed
        id_vector = np.fromiter(unique_ids, dtype=np.int64, count=len(unique_ids))
        return pending_removed + int(self._index.remove_ids(id_vector))

    def persist(self) -> None:
        """Train when possible and persist the complete dense index state."""
        self._train_if_ready()
        self._persist_index()

    @staticmethod
    def _results_from_matrices(score_matrix: np.ndarray, id_matrix: np.ndarray) -> list[ScoredChunk]:
        """Convert FAISS-style result matrices to the public result type."""
        results: list[ScoredChunk] = []
        for chunk_id, score in zip(id_matrix[0].tolist(), score_matrix[0].tolist(), strict=True):
            if chunk_id == -1:
                continue
            results.append(ScoredChunk(chunk_id=int(chunk_id), score=min(1.0, max(0.0, float(score)))))
        return results

    def search(self, query_embedding: list[float], top_k: int) -> list[ScoredChunk]:
        """Search for nearest chunk IDs by cosine similarity."""
        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")
        query_matrix = self._to_normalized_matrix(query_embedding)
        if not self._index.is_trained:
            if not self._pending:
                return []
            ids = np.fromiter(self._pending, dtype=np.int64, count=len(self._pending))
            vectors = np.stack(list(self._pending.values()))
            scores = vectors @ query_matrix[0]
            result_count = min(top_k, len(ids))
            order = np.argsort(-scores, kind="stable")[:result_count]
            return self._results_from_matrices(scores[order].reshape(1, -1), ids[order].reshape(1, -1))
        if self._index.ntotal == 0:
            return []
        score_matrix, id_matrix = self._index.search(query_matrix, top_k)
        return self._results_from_matrices(score_matrix, id_matrix)

    def destroy(self) -> None:
        """Destroy and recreate the configured FAISS index."""
        self._pending.clear()
        self._index = self._create_index()
        self._apply_search_parameters()
        self._persist_index()
        logger.info("Destroyed FAISS index at %s", self._index_path)
