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
