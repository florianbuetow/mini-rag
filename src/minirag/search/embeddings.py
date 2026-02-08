"""FastText embedding generation and normalization."""

import importlib
import math
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol, cast


class FastTextModel(Protocol):
    """Protocol for the subset of FastText model methods this app uses."""

    def get_sentence_vector(self, text: str) -> object:
        """Return a sentence embedding for the given text."""


class FastTextEmbeddings:
    """FastText embedding wrapper with strict startup validation."""

    def __init__(self, model_path: Path, expected_dimension: int) -> None:
        """Load and validate the FastText model.

        Args:
            model_path: Absolute or relative path to the FastText `.bin` model.
            expected_dimension: Required embedding dimension.

        Raises:
            FileNotFoundError: If the model file does not exist.
            ValueError: If expected dimension is invalid or mismatched.
            RuntimeError: If model loading fails.
        """
        if expected_dimension <= 0:
            raise ValueError("expected_dimension must be greater than 0")

        if not model_path.exists():
            raise FileNotFoundError(f"embedding model file not found: {model_path}")

        if not model_path.is_file():
            raise ValueError(f"embedding model path is not a file: {model_path}")

        fasttext_module = importlib.import_module("fasttext")
        if not hasattr(fasttext_module, "load_model"):
            raise RuntimeError("fasttext.load_model is not available")

        load_model = fasttext_module.load_model
        loaded_model = load_model(str(model_path))
        self._model = cast(FastTextModel, loaded_model)
        self._dimension = expected_dimension

        raw_probe_vector = self._model.get_sentence_vector("dimension validation probe")
        probe_vector = self._vector_to_float_list(cast(Iterable[float], raw_probe_vector))
        probe_dimension = len(probe_vector)
        if probe_dimension != expected_dimension:
            raise ValueError(f"embedding dimension mismatch: configured={expected_dimension}, model={probe_dimension}")

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts and return unit-normalized vectors.

        Args:
            texts: Texts to embed.

        Returns:
            Unit-normalized vectors of length `expected_dimension`.
        """
        vectors: list[list[float]] = []

        for text in texts:
            raw_vector = self._model.get_sentence_vector(text)
            float_vector = self._vector_to_float_list(cast(Iterable[float], raw_vector))

            if len(float_vector) != self._dimension:
                raise ValueError(f"embedding dimension mismatch: configured={self._dimension}, computed={len(float_vector)}")

            vectors.append(self._normalize(float_vector))

        return vectors

    def _vector_to_float_list(self, vector: Iterable[float]) -> list[float]:
        """Convert a vector-like value into a Python float list."""
        return [float(value) for value in vector]

    def _normalize(self, vector: list[float]) -> list[float]:
        """Normalize a vector to unit length."""
        norm = math.sqrt(sum(value * value for value in vector))
        if norm <= 0.0:
            raise ValueError("embedding vector norm must be greater than 0")

        normalized_vector = [value / norm for value in vector]
        return normalized_vector
