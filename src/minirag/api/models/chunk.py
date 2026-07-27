"""Chunk endpoint API models."""

from pydantic import BaseModel, ConfigDict


class ChunkResponse(BaseModel):
    """Response model for chunk provenance lookup."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: int
    document_id: int
    citation_key: str
    source_path: str
    chunk_index: int
    char_start: int
    char_end: int
    line_from: int
    line_to: int
    text: str


class ChunkSourceResponse(BaseModel):
    """Response model for the original source slice of a chunk."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: int
    document_id: int
    citation_key: str
    source_path: str
    char_start: int
    char_end: int
    line_from: int
    line_to: int
    original_text: str
