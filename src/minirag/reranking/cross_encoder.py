"""Cross-encoder reranker for hybrid search results."""

import importlib
import logging
import math
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol, cast

from minirag.search.types import SearchResult

logger = logging.getLogger(__name__)


class CrossEncoderModel(Protocol):
    """Subset of sentence_transformers.CrossEncoder API used by this adapter."""

    def predict(self, sentences: list[list[str]]) -> object:
        """Score sentence pairs and return array of relevance scores."""


class CrossEncoderConstructor(Protocol):
    """Callable signature used to construct CrossEncoder models."""

    def __call__(self, model_name: str, **kwargs: object) -> object:
        """Construct a cross-encoder model."""


class CrossEncoderReranker:
    """Rerank candidates using a sentence-transformers cross-encoder model."""

    def __init__(self, model_name: str, model_cache_dir: Path, candidate_multiplier: int) -> None:
        """Load the configured cross-encoder model."""
        if model_name.strip() == "":
            raise ValueError("model_name must not be empty")

        if candidate_multiplier <= 0:
            raise ValueError("candidate_multiplier must be greater than 0")

        model_cache_dir.mkdir(parents=True, exist_ok=True)

        sentence_transformers_module = importlib.import_module("sentence_transformers")
        if not hasattr(sentence_transformers_module, "CrossEncoder"):
            raise RuntimeError("sentence_transformers.CrossEncoder is not available")

        cross_encoder_ctor = cast(CrossEncoderConstructor, sentence_transformers_module.CrossEncoder)
        loaded_model = self._load_model_with_cache(
            cross_encoder_ctor=cross_encoder_ctor,
            model_name=model_name,
            model_cache_dir=model_cache_dir,
        )

        self._model = cast(CrossEncoderModel, loaded_model)
        self._model_name = model_name
        self._candidate_multiplier = candidate_multiplier

        logger.info(
            "Initialized cross-encoder reranker with model=%s and candidate_multiplier=%s",
            model_name,
            candidate_multiplier,
        )

    def _load_model_with_cache(self, cross_encoder_ctor: CrossEncoderConstructor, model_name: str, model_cache_dir: Path) -> object:
        """Load CrossEncoder while explicitly attempting supported cache parameters."""
        cache_directory = str(model_cache_dir)
        constructor_attempts: list[tuple[str, dict[str, object]]] = [
            ("cache_folder", {"cache_folder": cache_directory}),
            ("cache_dir", {"cache_dir": cache_directory}),
            ("model_kwargs", {"model_kwargs": {"cache_dir": cache_directory}}),
        ]

        for parameter_name, kwargs in constructor_attempts:
            try:
                model = cross_encoder_ctor(model_name, **kwargs)
                logger.info(
                    "Initialized cross-encoder model=%s using constructor parameter=%s",
                    model_name,
                    parameter_name,
                )
                return model
            except TypeError as exc:
                if "unexpected keyword argument" not in str(exc):
                    raise

        logger.warning(
            "CrossEncoder constructor for model=%s does not accept cache directory parameters; loading without explicit cache directory",
            model_name,
        )
        return cross_encoder_ctor(model_name)

    def candidate_count(self, top_k: int) -> int:
        """Return candidate count needed before reranking."""
        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")

        return top_k * self._candidate_multiplier

    def rerank(self, query: str, results: list[SearchResult], top_k: int) -> list[SearchResult]:
        """Re-score and re-rank candidate results for the given query."""
        if query.strip() == "":
            raise ValueError("query must not be empty")

        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")

        if len(results) == 0:
            return []

        sentence_pairs = [[query, result.text] for result in results]
        raw_scores = self._model.predict(sentence_pairs)
        float_scores = self._to_float_scores(raw_scores=raw_scores)

        if len(float_scores) != len(results):
            raise RuntimeError(f"reranker score count mismatch: expected={len(results)}, got={len(float_scores)}; model={self._model_name}")

        rescored_results = [
            SearchResult(
                chunk_id=result.chunk_id,
                text=result.text,
                score=self._sigmoid(score),
            )
            for result, score in zip(results, float_scores, strict=True)
        ]
        ranked_results = sorted(rescored_results, key=lambda result: result.score, reverse=True)
        return ranked_results[:top_k]

    def _to_float_scores(self, raw_scores: object) -> list[float]:
        """Convert score container returned by the model into a float list."""
        iterable_scores = cast(Iterable[float], raw_scores)
        return [float(score) for score in iterable_scores]

    def _sigmoid(self, score: float) -> float:
        """Normalize an unbounded logit score into the [0.0, 1.0] range."""
        if score >= 0.0:
            return 1.0 / (1.0 + math.exp(-score))

        exp_score = math.exp(score)
        return exp_score / (1.0 + exp_score)
