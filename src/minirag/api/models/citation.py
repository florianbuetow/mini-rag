"""Citation endpoint API models."""

from pydantic import BaseModel, ConfigDict


class CitationResponse(BaseModel):
    """Response model for citation data."""

    model_config = ConfigDict(extra="forbid")

    citation_key: str
    source_type: str
    common: dict[str, object]
    source_data: dict[str, object]
