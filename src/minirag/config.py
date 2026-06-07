"""Configuration models and loader for mini-rag."""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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


class LMStudioEmbeddingsConfig(BaseModel):
    """LM Studio (OpenAI-compatible) embedding provider settings."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    base_url: str
    model_name: str
    dimension: int
    max_input_tokens: int
    safety_fraction: float = 0.80
    batch_size: int = 32
    timeout_seconds: float = 30.0

    @field_validator("base_url", "model_name")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        """Ensure required text fields are non-empty."""
        if value.strip() == "":
            raise ValueError("index.embeddings.lmstudio text fields must not be empty")
        return value

    @field_validator("dimension")
    @classmethod
    def validate_dimension(cls, value: int) -> int:
        """Ensure embedding dimension is strictly positive."""
        if value <= 0:
            raise ValueError("index.embeddings.lmstudio.dimension must be greater than 0")
        return value

    @field_validator("max_input_tokens")
    @classmethod
    def validate_max_input_tokens(cls, value: int) -> int:
        """Ensure the model token window is strictly positive."""
        if value <= 0:
            raise ValueError("index.embeddings.lmstudio.max_input_tokens must be greater than 0")
        return value

    @field_validator("safety_fraction")
    @classmethod
    def validate_safety_fraction(cls, value: float) -> float:
        """Ensure the safety fraction is in the half-open range (0.0, 1.0]."""
        if value <= 0.0:
            raise ValueError("index.embeddings.lmstudio.safety_fraction must be greater than 0.0")
        if value > 1.0:
            raise ValueError("index.embeddings.lmstudio.safety_fraction must be less than or equal to 1.0")
        return value

    @field_validator("batch_size")
    @classmethod
    def validate_batch_size(cls, value: int) -> int:
        """Ensure the request batch size is strictly positive."""
        if value <= 0:
            raise ValueError("index.embeddings.lmstudio.batch_size must be greater than 0")
        return value

    @field_validator("timeout_seconds")
    @classmethod
    def validate_timeout_seconds(cls, value: float) -> float:
        """Ensure the request timeout is strictly positive."""
        if value <= 0.0:
            raise ValueError("index.embeddings.lmstudio.timeout_seconds must be greater than 0.0")
        return value

    def token_budget(self) -> int:
        """Return the per-chunk token ceiling (token window times safety fraction)."""
        return max(1, int(self.max_input_tokens * self.safety_fraction))


class EmbeddingsConfig(BaseModel):
    """Embedding model settings.

    `provider` selects the active embedding backend. `model_name` and `dimension`
    configure the fastText backend (preserved for backward compatibility); the
    `lmstudio` section configures the LM Studio backend.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str = "fasttext"
    model_name: str
    dimension: int
    lmstudio: LMStudioEmbeddingsConfig | None = None

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        """Ensure the provider selector is one of the supported backends."""
        allowed_providers = ("fasttext", "lmstudio")
        if value not in allowed_providers:
            raise ValueError(f"index.embeddings.provider must be one of {allowed_providers}; got {value!r}")
        return value

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

    @model_validator(mode="after")
    def validate_lmstudio_present_for_provider(self) -> "EmbeddingsConfig":
        """Require the LM Studio section when the lmstudio provider is selected."""
        if self.provider == "lmstudio" and self.lmstudio is None:
            raise ValueError("index.embeddings.lmstudio section is required when provider is 'lmstudio'")
        return self

    def active_dimension(self) -> int:
        """Return the embedding dimension of the active provider."""
        if self.provider == "lmstudio" and self.lmstudio is not None:
            return self.lmstudio.dimension
        return self.dimension


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


class RerankingConfig(BaseModel):
    """Reranking settings for hybrid search post-processing."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: bool
    model_name: str
    candidate_multiplier: int

    @field_validator("model_name")
    @classmethod
    def validate_model_name(cls, value: str) -> str:
        """Ensure reranker model name is non-empty text."""
        if value.strip() == "":
            raise ValueError("search.reranking.model_name must not be empty")
        return value

    @field_validator("candidate_multiplier")
    @classmethod
    def validate_candidate_multiplier(cls, value: int) -> int:
        """Ensure candidate multiplier is strictly positive."""
        if value <= 0:
            raise ValueError("search.reranking.candidate_multiplier must be greater than 0")
        return value


class ContextPruningConfig(BaseModel):
    """Token-budget pruning settings for retrieved document context."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    document_context_fraction: float = 0.6
    fallback_context_window_tokens: int = 4096

    @field_validator("document_context_fraction")
    @classmethod
    def validate_document_context_fraction(cls, value: float) -> float:
        """Ensure the document context fraction is in (0.0, 1.0]."""
        if value <= 0.0:
            raise ValueError("search.context_pruning.document_context_fraction must be greater than 0.0")
        if value > 1.0:
            raise ValueError("search.context_pruning.document_context_fraction must be less than or equal to 1.0")
        return value

    @field_validator("fallback_context_window_tokens")
    @classmethod
    def validate_fallback_context_window_tokens(cls, value: int) -> int:
        """Ensure fallback context window is strictly positive."""
        if value <= 0:
            raise ValueError("search.context_pruning.fallback_context_window_tokens must be greater than 0")
        return value


class SearchConfig(BaseModel):
    """Search subsystem settings."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    hybrid: HybridConfig
    dense: DenseSearchConfig
    sparse: SparseSearchConfig
    reranking: RerankingConfig
    context_pruning: ContextPruningConfig = Field(default_factory=ContextPruningConfig)


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
