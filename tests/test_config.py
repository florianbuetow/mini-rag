"""Unit tests for configuration parsing and startup validation."""

from pathlib import Path
from typing import Any

import pytest
import yaml
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


def _base_config_dict(data_dir: str) -> dict[str, Any]:
    """Build a valid config mapping (fasttext provider by default)."""
    return {
        "service": {"host": "127.0.0.1", "port": 7001, "reload": True, "log_level": "INFO"},
        "data": {"data_dir": data_dir},
        "index": {
            "chunking": {"chunk_size": 300, "overlap": 0.3},
            "embeddings": {"provider": "fasttext", "model_name": "cc.en.300.bin", "dimension": 300},
            "storage": {"db_filename": "minirag.db"},
            "faiss": {"index_type": "IndexFlatIP", "nprobe": 1},
            "tantivy": {"language": "en", "stemming": True},
        },
        "search": {
            "hybrid": {"alpha": 0.5},
            "dense": {},
            "sparse": {},
            "reranking": {
                "enabled": False,
                "model_name": "cross-encoder/ms-marco-MiniLM-L12-v2",
                "candidate_multiplier": 3,
            },
        },
    }


def _lmstudio_section(**overrides: Any) -> dict[str, Any]:
    """Build a valid LM Studio embedding section, overridable per test."""
    section: dict[str, Any] = {
        "base_url": "http://127.0.0.1:1234/v1",
        "model_name": "text-embedding-bge-large-en-v1.5@f16",
        "dimension": 1024,
        "max_input_tokens": 512,
        "safety_fraction": 0.80,
        "batch_size": 32,
        "timeout_seconds": 30.0,
    }
    section.update(overrides)
    return section


def _write_and_load(tmp_path: Path, config_dict: dict[str, Any]) -> Config:
    """Dump a config mapping to YAML and parse it."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config_dict), encoding="utf-8")
    return Config.from_yaml(config_path)


def test_existing_config_without_provider_defaults_to_fasttext(tmp_path: Path) -> None:
    """A config omitting provider/lmstudio still loads (backward compatibility)."""
    cfg = _base_config_dict(str(tmp_path / "data"))
    del cfg["index"]["embeddings"]["provider"]

    embeddings = _write_and_load(tmp_path, cfg).get_index_config().embeddings

    assert embeddings.provider == "fasttext"
    assert embeddings.lmstudio is None
    assert embeddings.active_dimension() == 300


def test_rejects_unknown_provider_value(tmp_path: Path) -> None:
    """An unknown provider value is rejected, naming the field and value."""
    cfg = _base_config_dict(str(tmp_path / "data"))
    cfg["index"]["embeddings"]["provider"] = "word2vec"

    with pytest.raises(ValidationError, match=r"provider must be one of"):
        _write_and_load(tmp_path, cfg)


@pytest.mark.parametrize("bad_provider", ["", "fast_text", "bge", "openai", "FASTTEXT", "lmstudio "])
def test_provider_enum_is_closed(tmp_path: Path, bad_provider: str) -> None:
    """The provider selector rejects any value outside the supported set."""
    cfg = _base_config_dict(str(tmp_path / "data"))
    cfg["index"]["embeddings"]["provider"] = bad_provider

    with pytest.raises(ValidationError):
        _write_and_load(tmp_path, cfg)


def test_lmstudio_config_section_loads(tmp_path: Path) -> None:
    """The LM Studio section loads all settings and computes the active dimension."""
    cfg = _base_config_dict(str(tmp_path / "data"))
    cfg["index"]["embeddings"]["provider"] = "lmstudio"
    cfg["index"]["embeddings"]["lmstudio"] = _lmstudio_section()

    embeddings = _write_and_load(tmp_path, cfg).get_index_config().embeddings
    lmstudio = embeddings.lmstudio

    assert lmstudio is not None
    assert lmstudio.base_url == "http://127.0.0.1:1234/v1"
    assert lmstudio.model_name == "text-embedding-bge-large-en-v1.5@f16"
    assert lmstudio.dimension == 1024
    assert lmstudio.max_input_tokens == 512
    assert lmstudio.safety_fraction == 0.80
    assert embeddings.active_dimension() == 1024
    assert lmstudio.token_budget() == 409


def test_rejects_unknown_lmstudio_key(tmp_path: Path) -> None:
    """An unrecognized key in the LM Studio section is rejected."""
    cfg = _base_config_dict(str(tmp_path / "data"))
    cfg["index"]["embeddings"]["provider"] = "lmstudio"
    cfg["index"]["embeddings"]["lmstudio"] = _lmstudio_section(unexpected="x")

    with pytest.raises(ValidationError, match="unexpected"):
        _write_and_load(tmp_path, cfg)


def test_rejects_nonpositive_lmstudio_dimension(tmp_path: Path) -> None:
    """A non-positive LM Studio dimension is rejected."""
    cfg = _base_config_dict(str(tmp_path / "data"))
    cfg["index"]["embeddings"]["provider"] = "lmstudio"
    cfg["index"]["embeddings"]["lmstudio"] = _lmstudio_section(dimension=0)

    with pytest.raises(ValidationError, match="dimension must be greater than 0"):
        _write_and_load(tmp_path, cfg)


def test_rejects_nonpositive_token_window(tmp_path: Path) -> None:
    """A non-positive token window is rejected."""
    cfg = _base_config_dict(str(tmp_path / "data"))
    cfg["index"]["embeddings"]["provider"] = "lmstudio"
    cfg["index"]["embeddings"]["lmstudio"] = _lmstudio_section(max_input_tokens=0)

    with pytest.raises(ValidationError, match="max_input_tokens must be greater than 0"):
        _write_and_load(tmp_path, cfg)


@pytest.mark.parametrize(("fraction", "accepted"), [(0.0, False), (1.5, False), (1.0, True), (0.8, True)])
def test_safety_fraction_range(tmp_path: Path, fraction: float, accepted: bool) -> None:
    """The safety fraction is enforced to the half-open range (0.0, 1.0]."""
    cfg = _base_config_dict(str(tmp_path / "data"))
    cfg["index"]["embeddings"]["provider"] = "lmstudio"
    cfg["index"]["embeddings"]["lmstudio"] = _lmstudio_section(safety_fraction=fraction)

    if accepted:
        embeddings = _write_and_load(tmp_path, cfg).get_index_config().embeddings
        assert embeddings.lmstudio is not None
        assert embeddings.lmstudio.safety_fraction == fraction
    else:
        with pytest.raises(ValidationError):
            _write_and_load(tmp_path, cfg)


def test_lmstudio_selected_without_section_fails(tmp_path: Path) -> None:
    """Selecting lmstudio without its config section fails, naming the section."""
    cfg = _base_config_dict(str(tmp_path / "data"))
    cfg["index"]["embeddings"]["provider"] = "lmstudio"

    with pytest.raises(ValidationError, match="lmstudio section is required"):
        _write_and_load(tmp_path, cfg)


def test_lmstudio_startup_passes_without_model_file(tmp_path: Path) -> None:
    """Startup validation passes for lmstudio even without a local model file."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    cfg = _base_config_dict(str(data_dir))
    cfg["index"]["embeddings"]["provider"] = "lmstudio"
    cfg["index"]["embeddings"]["lmstudio"] = _lmstudio_section()
    config = _write_and_load(tmp_path, cfg)

    validate_startup_environment(config=config, project_root=tmp_path)
