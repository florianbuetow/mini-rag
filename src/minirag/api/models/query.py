"""Query endpoint API models."""

from typing import Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


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


class HybridQueryRequest(QueryRequest):
    """Request model for hybrid search with an optional dense-weight override."""

    alpha: float | None = None

    @field_validator("alpha")
    @classmethod
    def validate_alpha(cls, value: float | None) -> float | None:
        """Require alpha to be within the hybrid weighting range when provided."""
        if value is not None and not 0.0 <= value <= 1.0:
            raise ValueError("alpha must be between 0.0 and 1.0")
        return value


class QueryResult(BaseModel):
    """One query result item with chunk ID, text, relevance score, and source provenance."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: int
    document_id: int
    citation_key: str
    text: str
    score: float
    source_path: str
    chunk_index: int
    char_start: int
    char_end: int
    line_from: int
    line_to: int

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

    @field_validator("source_path")
    @classmethod
    def validate_source_path(cls, value: str) -> str:
        """Require non-empty source_path."""
        if value.strip() == "":
            raise ValueError("source_path must not be empty")
        return value

    @field_validator("chunk_index")
    @classmethod
    def validate_chunk_index(cls, value: int) -> int:
        """Require non-negative chunk_index."""
        if value < 0:
            raise ValueError("chunk_index must be greater than or equal to 0")
        return value

    @field_validator("char_start")
    @classmethod
    def validate_char_start(cls, value: int) -> int:
        """Require non-negative char_start."""
        if value < 0:
            raise ValueError("char_start must be greater than or equal to 0")
        return value

    @field_validator("line_from")
    @classmethod
    def validate_line_from(cls, value: int) -> int:
        """Require 1-based line_from."""
        if value < 1:
            raise ValueError("line_from must be greater than or equal to 1")
        return value

    @model_validator(mode="after")
    def validate_span_consistency(self) -> Self:
        """Require a non-empty char span and an ordered line range."""
        if self.char_end <= self.char_start:
            raise ValueError("char_end must be greater than char_start")
        if self.line_to < self.line_from:
            raise ValueError("line_to must be greater than or equal to line_from")
        return self


class QueryResponse(BaseModel):
    """Response model for search operations."""

    model_config = ConfigDict(extra="forbid")

    results: list[QueryResult]
