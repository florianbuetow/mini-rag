"""Unit tests for configuration parsing and startup validation."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from minirag.config import Config


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

    config.validate_startup(tmp_path)


def test_config_missing_file_raises(tmp_path: Path) -> None:
    """Loading missing config file should fail."""
    missing_path = tmp_path / "missing.yaml"
    with pytest.raises(FileNotFoundError):
        Config.from_yaml(missing_path)


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
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        Config.from_yaml(config_path)
