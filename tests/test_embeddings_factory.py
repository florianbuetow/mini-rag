"""Unit tests for the embedding provider factory."""

from pathlib import Path

import pytest

import minirag.backend_factory as factory_module
from minirag.config import EmbeddingsConfig, LMStudioEmbeddingsConfig
from minirag.search.embeddings_lmstudio import LMStudioEmbeddings


def test_factory_builds_fasttext_provider(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The fasttext provider is constructed from the local model path and dimension."""
    captured: dict[str, object] = {}

    class FakeFastText:
        def __init__(self, model_path: Path, expected_dimension: int) -> None:
            captured["model_path"] = model_path
            captured["dimension"] = expected_dimension

    monkeypatch.setattr(factory_module, "FastTextEmbeddings", FakeFastText)
    config = EmbeddingsConfig(provider="fasttext", model_name="cc.en.300.bin", dimension=300)

    result = factory_module.build_embeddings(config, tmp_path)

    assert isinstance(result, FakeFastText)
    assert captured["model_path"] == tmp_path / "models" / "cc.en.300.bin"
    assert captured["dimension"] == 300


def test_factory_builds_lmstudio_provider(tmp_path: Path) -> None:
    """The lmstudio provider is constructed when selected, without a local model file."""
    config = EmbeddingsConfig(
        provider="lmstudio",
        model_name="cc.en.300.bin",
        dimension=300,
        lmstudio=LMStudioEmbeddingsConfig(
            base_url="http://127.0.0.1:1234/v1",
            model_name="text-embedding-bge-large-en-v1.5@f16",
            dimension=1024,
            max_input_tokens=512,
        ),
    )

    result = factory_module.build_embeddings(config, tmp_path)

    assert isinstance(result, LMStudioEmbeddings)
