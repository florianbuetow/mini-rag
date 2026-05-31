"""Unit tests for configuration parsing and startup validation."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from minirag.config import Config
from minirag.startup_validation import validate_startup_environment


def write_config(path: Path, data_dir: str) -> None:
    """Write a minimal valid config yaml."""
    path.write_text(
        "\n".join(
            [
                "service:",
                '  host: "127.0.0.1"',
                "  port: 7001",
                "  reload: true",
                '  log_level: "INFO"',
                "data:",
                f'  data_dir: "{data_dir}"',
                "index:",
                "  chunking:",
                "    chunk_size: 300",
                "    overlap: 0.3",
                "  embeddings:",
                '    model_name: "cc.en.300.bin"',
                "    dimension: 300",
                "  storage:",
                '    db_filename: "minirag.db"',
                "  faiss:",
                '    index_type: "IndexFlatIP"',
                "    nprobe: 1",
                "  tantivy:",
                '    language: "en"',
                "    stemming: true",
                "search:",
                "  hybrid:",
                "    alpha: 0.5",
                "  dense: {}",
                "  sparse: {}",
                "  reranking:",
                "    enabled: false",
                '    model_name: "cross-encoder/ms-marco-MiniLM-L12-v2"',
                "    candidate_multiplier: 3",
            ]
        ),
        encoding="utf-8",
    )


def test_config_from_yaml_and_validate_startup(tmp_path: Path) -> None:
    """Config should parse and pass startup validation when paths exist."""
    data_dir = tmp_path / "data"
    model_dir = data_dir / "models"
    model_dir.mkdir(parents=True)
    (model_dir / "cc.en.300.bin").write_bytes(b"model")

    config_path = tmp_path / "config.yaml"
    write_config(config_path, data_dir=str(data_dir))

    config = Config.from_yaml(config_path)

    assert config.get_service_config().port == 7001
    assert config.get_index_config().embeddings.dimension == 300
    assert config.get_search_config().context_pruning.document_context_fraction == 0.6
    assert config.get_search_config().context_pruning.fallback_context_window_tokens == 4096

    validate_startup_environment(config=config, project_root=tmp_path)


def test_config_missing_file_raises(tmp_path: Path) -> None:
    """Loading missing config file should fail."""
    missing_path = tmp_path / "missing.yaml"
    with pytest.raises(FileNotFoundError):
        Config.from_yaml(missing_path)


def _make_config(tmp_path: Path, data_dir: str) -> Config:
    """Write config yaml and parse it."""
    config_path = tmp_path / "config.yaml"
    write_config(config_path, data_dir=data_dir)
    return Config.from_yaml(config_path)


def test_validate_startup_missing_data_dir(tmp_path: Path) -> None:
    """Startup validation should fail when data directory does not exist."""
    config = _make_config(tmp_path, data_dir=str(tmp_path / "nonexistent"))
    with pytest.raises(FileNotFoundError, match="data directory not found"):
        validate_startup_environment(config=config, project_root=tmp_path)


def test_validate_startup_data_dir_is_file(tmp_path: Path) -> None:
    """Startup validation should fail when data path is a file, not directory."""
    fake_dir = tmp_path / "data"
    fake_dir.write_text("not a directory")
    config = _make_config(tmp_path, data_dir=str(fake_dir))
    with pytest.raises(ValueError, match="data path is not a directory"):
        validate_startup_environment(config=config, project_root=tmp_path)


def test_validate_startup_missing_model(tmp_path: Path) -> None:
    """Startup validation should fail when embedding model file is missing."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    config = _make_config(tmp_path, data_dir=str(data_dir))
    with pytest.raises(FileNotFoundError, match="embedding model file not found"):
        validate_startup_environment(config=config, project_root=tmp_path)


def test_validate_startup_model_is_directory(tmp_path: Path) -> None:
    """Startup validation should fail when model path is a directory."""
    data_dir = tmp_path / "data"
    model_path = data_dir / "models" / "cc.en.300.bin"
    model_path.mkdir(parents=True)
    config = _make_config(tmp_path, data_dir=str(data_dir))
    with pytest.raises(ValueError, match="embedding model path is not a file"):
        validate_startup_environment(config=config, project_root=tmp_path)


def test_config_missing_required_key_raises(tmp_path: Path) -> None:
    """Missing required nested key should fail pydantic validation."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "service:",
                '  host: "127.0.0.1"',
                "  port: 7001",
                "  reload: true",
                '  log_level: "INFO"',
                "data:",
                '  data_dir: "data"',
                "index:",
                "  chunking:",
                "    chunk_size: 300",
                "    overlap: 0.3",
                "  embeddings:",
                "    dimension: 300",
                "  storage:",
                '    db_filename: "minirag.db"',
                "  faiss:",
                '    index_type: "IndexFlatIP"',
                "    nprobe: 1",
                "  tantivy:",
                '    language: "en"',
                "    stemming: true",
                "search:",
                "  hybrid:",
                "    alpha: 0.5",
                "  dense: {}",
                "  sparse: {}",
                "  reranking:",
                "    enabled: false",
                '    model_name: "cross-encoder/ms-marco-MiniLM-L12-v2"',
                "    candidate_multiplier: 3",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        Config.from_yaml(config_path)
