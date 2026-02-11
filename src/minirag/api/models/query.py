"""Query endpoint API models."""

from pydantic import BaseModel, ConfigDict, field_validator


class QueryRequest(BaseModel):
    """Request model for search operations."""

    model_config = ConfigDict(extra="forbid")

    query: str
    top_k: int

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        """Require non-empty query text."""
        if value.strip() == "":
            raise ValueError("query must not be empty")
        return value

    @field_validator("top_k")
    @classmethod
    def validate_top_k(cls, value: int) -> int:
        """Require positive top_k."""
        if value <= 0:
            raise ValueError("top_k must be greater than 0")
        return value


class QueryResult(BaseModel):
    """One query result item with chunk ID, text, and relevance score."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: int
    document_id: int
    citation_key: str
    text: str
    score: float

    @field_validator("chunk_id")
    @classmethod
    def validate_chunk_id(cls, value: int) -> int:
        """Require positive chunk_id."""
        if value <= 0:
            raise ValueError("chunk_id must be greater than 0")
        return value

    @field_validator("document_id")
    @classmethod
    def validate_document_id(cls, value: int) -> int:
        """Require positive document_id."""
        if value <= 0:
            raise ValueError("document_id must be greater than 0")
        return value

    @field_validator("citation_key")
    @classmethod
    def validate_citation_key(cls, value: str) -> str:
        """Require non-empty citation_key."""
        if value.strip() == "":
            raise ValueError("citation_key must not be empty")
        return value

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        """Require non-empty text."""
        if value.strip() == "":
            raise ValueError("text must not be empty")
        return value

    @field_validator("score")
    @classmethod
    def validate_score(cls, value: float) -> float:
        """Require score in [0.0, 1.0]."""
        if value < 0.0:
            raise ValueError("score must be greater than or equal to 0.0")
        if value > 1.0:
            raise ValueError("score must be less than or equal to 1.0")
        return value


class QueryResponse(BaseModel):
    """Response model for search operations."""

    model_config = ConfigDict(extra="forbid")

    results: list[QueryResult]
