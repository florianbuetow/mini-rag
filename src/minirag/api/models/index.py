"""Index endpoint API models."""

from pathlib import PurePosixPath

from pydantic import BaseModel, ConfigDict, field_validator

from minirag.api.models.citation import CitationInput


class IndexRequest(BaseModel):
    """Request model for indexing a single document."""

    model_config = ConfigDict(extra="forbid")

    document: str
    source_path: str
    citation: CitationInput | None = None

    @field_validator("document")
    @classmethod
    def validate_document(cls, value: str) -> str:
        """Require non-empty document text."""
        if value.strip() == "":
            raise ValueError("document text must not be empty")
        return value

    @field_validator("source_path")
    @classmethod
    def validate_source_path(cls, value: str) -> str:
        """Require a non-empty relative path without parent traversal."""
        if value.strip() == "":
            raise ValueError("source_path must not be empty")
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("source_path must be a relative path without '..' components")
        return value


class IndexResponse(BaseModel):
    """Response model for successful document indexing."""

    model_config = ConfigDict(extra="forbid")

    document_id: int
    chunk_ids: list[int]
    chunks_indexed: int
