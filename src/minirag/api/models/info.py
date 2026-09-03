"""Admin endpoint API models."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Health response payload."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["healthy", "shutting_down"]


class InfoResponse(BaseModel):
    """Info response payload."""

    model_config = ConfigDict(extra="forbid")

    config: dict[str, object]


class ShutdownResponse(BaseModel):
    """Shutdown response payload."""

    model_config = ConfigDict(extra="forbid")

    message: str


class CorporaResponse(BaseModel):
    """Corpus list and parallel description map."""

    model_config = ConfigDict(extra="forbid")

    corpora: list[str]
    descriptions: dict[str, str]


class CorpusDescriptionResponse(BaseModel):
    """Resolved description for one corpus."""

    model_config = ConfigDict(extra="forbid")

    corpus: str
    description: str
