"""Configuration models and loader for mini-rag."""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, field_validator


class ServiceConfig(BaseModel):
    """Service process settings."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    host: str
    port: int
    reload: bool
    log_level: str

    @field_validator("host")
    @classmethod
    def validate_host(cls, value: str) -> str:
        """Ensure host is non-empty text."""
        if value.strip() == "":
            raise ValueError("service.host must not be empty")
        return value

    @field_validator("port")
    @classmethod
    def validate_port(cls, value: int) -> int:
        """Ensure port is within the TCP port range."""
        if value <= 0:
            raise ValueError("service.port must be greater than 0")
        if value > 65535:
            raise ValueError("service.port must be less than or equal to 65535")
        return value

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        """Ensure log level is non-empty text."""
        if value.strip() == "":
            raise ValueError("service.log_level must not be empty")
        return value


class DataConfig(BaseModel):
    """Data directory settings."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    data_dir: str

    @field_validator("data_dir")
    @classmethod
    def validate_data_dir(cls, value: str) -> str:
        """Ensure data directory path text is non-empty."""
        if value.strip() == "":
            raise ValueError("data.data_dir must not be empty")
        return value


class ChunkingConfig(BaseModel):
    """Chunking strategy settings."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_size: int
    overlap: float

    @field_validator("chunk_size")
    @classmethod
    def validate_chunk_size(cls, value: int) -> int:
        """Ensure chunk size is strictly positive."""
        if value <= 0:
            raise ValueError("index.chunking.chunk_size must be greater than 0")
        return value

    @field_validator("overlap")
    @classmethod
    def validate_overlap(cls, value: float) -> float:
        """Ensure overlap is in [0.0, 1.0)."""
        if value < 0.0:
            raise ValueError("index.chunking.overlap must be greater than or equal to 0.0")
        if value >= 1.0:
            raise ValueError("index.chunking.overlap must be less than 1.0")
        return value


class EmbeddingsConfig(BaseModel):
    """Embedding model settings."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model_name: str
    dimension: int

    @field_validator("model_name")
    @classmethod
    def validate_model_name(cls, value: str) -> str:
        """Ensure model file name is non-empty text."""
        if value.strip() == "":
            raise ValueError("index.embeddings.model_name must not be empty")
        return value

    @field_validator("dimension")
    @classmethod
    def validate_dimension(cls, value: int) -> int:
        """Ensure embedding dimension is strictly positive."""
        if value <= 0:
            raise ValueError("index.embeddings.dimension must be greater than 0")
        return value


class StorageConfig(BaseModel):
    """Storage settings."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    db_filename: str

    @field_validator("db_filename")
    @classmethod
    def validate_db_filename(cls, value: str) -> str:
        """Ensure database file name is non-empty text."""
        if value.strip() == "":
            raise ValueError("index.storage.db_filename must not be empty")
        return value


class FAISSConfig(BaseModel):
    """FAISS index settings."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    index_type: str
    nprobe: int

    @field_validator("index_type")
    @classmethod
    def validate_index_type(cls, value: str) -> str:
        """Ensure FAISS index type is non-empty text."""
        if value.strip() == "":
            raise ValueError("index.faiss.index_type must not be empty")
        return value

    @field_validator("nprobe")
    @classmethod
    def validate_nprobe(cls, value: int) -> int:
        """Ensure nprobe is strictly positive."""
        if value <= 0:
            raise ValueError("index.faiss.nprobe must be greater than 0")
        return value


class TantivyConfig(BaseModel):
    """Tantivy index settings."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    language: str
    stemming: bool

    @field_validator("language")
    @classmethod
    def validate_language(cls, value: str) -> str:
        """Ensure language is non-empty text."""
        if value.strip() == "":
            raise ValueError("index.tantivy.language must not be empty")
        return value


class IndexConfig(BaseModel):
    """Indexing subsystem settings."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    chunking: ChunkingConfig
    embeddings: EmbeddingsConfig
    storage: StorageConfig
    faiss: FAISSConfig
    tantivy: TantivyConfig


class HybridConfig(BaseModel):
    """Hybrid search weighting settings."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    alpha: float

    @field_validator("alpha")
    @classmethod
    def validate_alpha(cls, value: float) -> float:
        """Ensure alpha is in [0.0, 1.0]."""
        if value < 0.0:
            raise ValueError("search.hybrid.alpha must be greater than or equal to 0.0")
        if value > 1.0:
            raise ValueError("search.hybrid.alpha must be less than or equal to 1.0")
        return value


class DenseSearchConfig(BaseModel):
    """Dense search query-time configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class SparseSearchConfig(BaseModel):
    """Sparse search query-time configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class SearchConfig(BaseModel):
    """Search subsystem settings."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    hybrid: HybridConfig
    dense: DenseSearchConfig
    sparse: SparseSearchConfig


class Config(BaseModel):
    """Root application configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    service: ServiceConfig
    data: DataConfig
    index: IndexConfig
    search: SearchConfig

    @classmethod
    def from_yaml(cls, config_path: Path) -> "Config":
        """Load and validate configuration from a YAML file."""
        if not config_path.exists():
            raise FileNotFoundError(f"config file not found: {config_path}")

        with config_path.open("r", encoding="utf-8") as file_handle:
            loaded: object = yaml.safe_load(file_handle)

        if not isinstance(loaded, dict):
            raise ValueError("config root must be a mapping")

        return cls.model_validate(loaded)

    def get_service_config(self) -> ServiceConfig:
        """Return service configuration."""
        return self.service

    def get_data_config(self) -> DataConfig:
        """Return data configuration."""
        return self.data

    def get_index_config(self) -> IndexConfig:
        """Return index configuration."""
        return self.index

    def get_search_config(self) -> SearchConfig:
        """Return search configuration."""
        return self.search

    def resolve_data_dir(self, project_root: Path) -> Path:
        """Resolve data directory relative to project root when needed."""
        configured_path = Path(self.data.data_dir)
        if configured_path.is_absolute():
            return configured_path
        return project_root / configured_path

    def validate_startup(self, project_root: Path) -> None:
        """Validate filesystem prerequisites required to boot the service."""
        data_dir = self.resolve_data_dir(project_root)

        if not data_dir.exists():
            raise FileNotFoundError(f"data directory not found: {data_dir}")

        if not data_dir.is_dir():
            raise ValueError(f"data path is not a directory: {data_dir}")

        model_path = data_dir / "models" / self.index.embeddings.model_name
        if not model_path.exists():
            raise FileNotFoundError(f"embedding model file not found: {model_path}")

        if not model_path.is_file():
            raise ValueError(f"embedding model path is not a file: {model_path}")

        probe_path = data_dir / ".minirag_write_probe"
        try:
            with probe_path.open("w", encoding="utf-8") as file_handle:
                file_handle.write("probe")
        except OSError as exc:
            raise OSError(f"data directory is not writable: {data_dir}") from exc
        finally:
            if probe_path.exists():
                probe_path.unlink()
