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
    text: str
    score: float


class QueryResponse(BaseModel):
    """Response model for search operations."""

    model_config = ConfigDict(extra="forbid")

    results: list[QueryResult]
