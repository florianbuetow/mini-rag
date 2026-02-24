"""Citation endpoint API models."""

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CitationInput(BaseModel):
    """Request model for citation data supplied during indexing."""

    model_config = ConfigDict(extra="forbid")

    citation_key: str
    source_type: str
    common: dict[str, object] = Field(default_factory=dict)
    source_data: dict[str, object] = Field(default_factory=dict)

    @field_validator("citation_key")
    @classmethod
    def validate_citation_key(cls, value: str) -> str:
        """Require non-empty citation_key."""
        if value.strip() == "":
            raise ValueError("citation_key must not be empty")
        return value

    @field_validator("source_type")
    @classmethod
    def validate_source_type(cls, value: str) -> str:
        """Require non-empty source_type."""
        if value.strip() == "":
            raise ValueError("source_type must not be empty")
        return value


class CitationResponse(BaseModel):
    """Response model for citation data."""

    model_config = ConfigDict(extra="forbid")

    citation_key: str
    source_type: str
    common: dict[str, object]
    source_data: dict[str, object]

    @field_validator("citation_key")
    @classmethod
    def validate_citation_key(cls, value: str) -> str:
        """Require non-empty citation_key."""
        if value.strip() == "":
            raise ValueError("citation_key must not be empty")
        return value

    @field_validator("source_type")
    @classmethod
    def validate_source_type(cls, value: str) -> str:
        """Require non-empty source_type."""
        if value.strip() == "":
            raise ValueError("source_type must not be empty")
        return value
