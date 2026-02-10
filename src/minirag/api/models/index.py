"""Index endpoint API models."""

from pydantic import BaseModel, ConfigDict, field_validator


class IndexRequest(BaseModel):
    """Request model for indexing a single document."""

    model_config = ConfigDict(extra="forbid")

    document: str
    citation: dict[str, object] | None = None

    @field_validator("document")
    @classmethod
    def validate_document(cls, value: str) -> str:
        """Require non-empty document text."""
        if value.strip() == "":
            raise ValueError("document text must not be empty")
        return value


class IndexResponse(BaseModel):
    """Response model for successful document indexing."""

    model_config = ConfigDict(extra="forbid")

    document_id: int
    chunk_ids: list[int]
    chunks_indexed: int
