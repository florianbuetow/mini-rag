"""Chunk provenance routes for dereferencing chunk IDs back to their source."""

import asyncio
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from minirag.api.models.chunk import ChunkResponse, ChunkSourceResponse
from minirag.api.responses import error_response, success_response
from minirag.api.utils import ensure_healthy, get_corpus_manager, get_data_dir
from minirag.storage.interface import ChunkWithDocument

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/corpus/{corpus}/chunk")


async def _load_chunk(request: Request, corpus: str, chunk_id: int) -> tuple[ChunkWithDocument, str] | JSONResponse:
    """Resolve the corpus and fetch the chunk record with its citation key."""
    if chunk_id <= 0:
        return error_response(status=400, message="chunk_id must be greater than 0")

    try:
        corpus_manager = get_corpus_manager(request)
        orchestration = await asyncio.to_thread(corpus_manager.get, corpus)
    except ValueError as exc:
        return error_response(status=400, message=str(exc))
    except Exception as exc:
        logger.exception("Failed to load corpus for chunk lookup, corpus=%s, chunk_id=%s", corpus, chunk_id)
        return error_response(status=500, message=str(exc))

    try:
        return await asyncio.to_thread(orchestration.get_chunk, chunk_id)
    except ValueError as exc:
        return error_response(status=404, message=str(exc))
    except Exception as exc:
        logger.exception("Failed to get chunk, corpus=%s, chunk_id=%s", corpus, chunk_id)
        return error_response(status=500, message=str(exc))


@router.get("/{chunk_id}")
async def get_chunk(request: Request, corpus: str, chunk_id: int) -> JSONResponse:
    """Return chunk text plus full source provenance for a chunk ID."""
    guard_response = ensure_healthy(request)
    if guard_response is not None:
        return guard_response

    loaded = await _load_chunk(request, corpus, chunk_id)
    if isinstance(loaded, JSONResponse):
        return loaded
    chunk_record, citation_key = loaded

    response_model = ChunkResponse(
        chunk_id=chunk_id,
        document_id=chunk_record.document_id,
        citation_key=citation_key,
        source_path=chunk_record.source_path,
        chunk_index=chunk_record.chunk_index,
        char_start=chunk_record.char_start,
        char_end=chunk_record.char_end,
        line_from=chunk_record.line_from,
        line_to=chunk_record.line_to,
        text=chunk_record.content,
    )
    return success_response(status=200, data=response_model.model_dump())


@router.get("/{chunk_id}/source")
async def get_chunk_source(request: Request, corpus: str, chunk_id: int) -> JSONResponse:
    """Return the exact original text slice for a chunk from the corpus input directory."""
    guard_response = ensure_healthy(request)
    if guard_response is not None:
        return guard_response

    loaded = await _load_chunk(request, corpus, chunk_id)
    if isinstance(loaded, JSONResponse):
        return loaded
    chunk_record, citation_key = loaded

    input_dir = get_data_dir(request) / "input" / corpus / "txt"
    resolved_file = (input_dir / chunk_record.source_path).resolve()
    if not resolved_file.is_relative_to(input_dir.resolve()):
        return error_response(
            status=400,
            message=f"source_path resolves outside the corpus input directory: {chunk_record.source_path}",
        )

    if not resolved_file.is_file():
        return error_response(status=404, message=f"source file not found: {chunk_record.source_path}")

    try:
        file_text = await asyncio.to_thread(resolved_file.read_text, "utf-8")
    except OSError as exc:
        logger.exception("Failed to read source file, corpus=%s, chunk_id=%s", corpus, chunk_id)
        return error_response(status=500, message=str(exc))

    if len(file_text) < chunk_record.char_end:
        return error_response(
            status=409,
            message=f"source file has changed since ingestion: {chunk_record.source_path} is shorter than the recorded span",
        )

    response_model = ChunkSourceResponse(
        chunk_id=chunk_id,
        document_id=chunk_record.document_id,
        citation_key=citation_key,
        source_path=chunk_record.source_path,
        char_start=chunk_record.char_start,
        char_end=chunk_record.char_end,
        line_from=chunk_record.line_from,
        line_to=chunk_record.line_to,
        original_text=file_text[chunk_record.char_start : chunk_record.char_end],
    )
    return success_response(status=200, data=response_model.model_dump())
