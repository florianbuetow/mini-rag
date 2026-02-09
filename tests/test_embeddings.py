"""Unit tests for FastText embeddings wrapper."""

import importlib
from pathlib import Path

import pytest

from minirag.search.embeddings import FastTextEmbeddings


class FakeFastTextModel:
    """Fake FastText model for deterministic embedding vectors."""

    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self._vectors = vectors

    def get_sentence_vector(self, text: str) -> object:
        if text in self._vectors:
            return self._vectors[text]
        return self._vectors["default"]


class FakeFastTextModule:
    """Fake fasttext.FastText module exposing _FastText constructor."""

    def __init__(self, model: FakeFastTextModel) -> None:
        self._model = model

    def _FastText(self, _: str) -> FakeFastTextModel:
        return self._model


def test_embeddings_load_and_embed_normalized(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Embedding wrapper should normalize vectors and validate dimensions."""
    model_path = tmp_path / "cc.en.300.bin"
    model_path.write_bytes(b"x")

    fake_model = FakeFastTextModel(
        {
            "dimension validation probe": [3.0, 4.0],
            "hello": [3.0, 4.0],
            "default": [0.0, 5.0],
        }
    )
    fake_module = FakeFastTextModule(fake_model)

    def fake_import_module(name: str) -> object:
        if name == "fasttext.FastText":
            return fake_module
        raise RuntimeError(f"unexpected module import: {name}")

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    embeddings = FastTextEmbeddings(model_path=model_path, expected_dimension=2)
    vectors = embeddings.embed(["hello", "other"])

    assert len(vectors) == 2
    assert abs(vectors[0][0] - 0.6) < 1e-9
    assert abs(vectors[0][1] - 0.8) < 1e-9
    assert abs(vectors[1][0] - 0.0) < 1e-9
    assert abs(vectors[1][1] - 1.0) < 1e-9


def test_embeddings_dimension_mismatch_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Dimension mismatch at load should fail fast."""
    model_path = tmp_path / "cc.en.300.bin"
    model_path.write_bytes(b"x")

    fake_model = FakeFastTextModel({"dimension validation probe": [1.0, 2.0], "default": [1.0, 2.0]})
    fake_module = FakeFastTextModule(fake_model)

    def fake_import_module(name: str) -> object:
        if name == "fasttext.FastText":
            return fake_module
        raise RuntimeError(f"unexpected module import: {name}")

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    with pytest.raises(ValueError):
        FastTextEmbeddings(model_path=model_path, expected_dimension=3)
