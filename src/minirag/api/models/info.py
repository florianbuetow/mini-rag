"""Admin endpoint API models."""

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Health response payload."""

    model_config = ConfigDict(extra="forbid")

    status: str


class InfoResponse(BaseModel):
    """Info response payload."""

    model_config = ConfigDict(extra="forbid")

    config: dict[str, object]


class ShutdownResponse(BaseModel):
    """Shutdown response payload."""

    model_config = ConfigDict(extra="forbid")

    message: str
