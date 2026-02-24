"""Index management routes."""

import asyncio
import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from minirag.api.models.index import IndexRequest, IndexResponse
from minirag.api.responses import error_response, success_response
from minirag.api.utils import ensure_healthy, get_corpus_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/corpus/{corpus}")


async def _parse_index_request(request: Request) -> IndexRequest | JSONResponse:
    """Parse and validate index request body."""
    try:
        body_object = await request.json()
    except json.JSONDecodeError as exc:
        return error_response(status=400, message=str(exc))

    try:
        return IndexRequest.model_validate(body_object)
    except ValidationError as exc:
        return error_response(status=422, message=str(exc))


@router.post("/index")
async def index_document(request: Request, corpus: str) -> JSONResponse:
    """Index a single document into storage and retrieval backends."""
    guard_response = ensure_healthy(request)
    if guard_response is not None:
        return guard_response

    parsed_payload = await _parse_index_request(request)
    if isinstance(parsed_payload, JSONResponse):
        return parsed_payload

    corpus_manager = get_corpus_manager(request)
    try:
        orchestration = await asyncio.to_thread(corpus_manager.get, corpus)
    except ValueError as exc:
        return error_response(status=400, message=str(exc))

    citation_payload = parsed_payload.citation.model_dump() if parsed_payload.citation is not None else None
    try:
        document_id, chunk_ids = await asyncio.to_thread(
            orchestration.index_document,
            parsed_payload.document,
            citation_payload,
        )
    except ValueError as exc:
        return error_response(status=400, message=str(exc))
    except RuntimeError as exc:
        logger.exception("Failed to index document, corpus=%s", corpus)
        return error_response(status=500, message=str(exc))
    except Exception:
        logger.exception("Failed to index document, corpus=%s", corpus)
        return error_response(status=500, message="Internal server error")

    response_model = IndexResponse(
        document_id=document_id,
        chunk_ids=chunk_ids,
        chunks_indexed=len(chunk_ids),
    )
    return success_response(status=200, data=response_model.model_dump())


@router.delete("/index")
async def destroy_index(request: Request, corpus: str) -> JSONResponse:
    """Destroy the index for a specific corpus."""
    guard_response = ensure_healthy(request)
    if guard_response is not None:
        return guard_response

    corpus_manager = get_corpus_manager(request)
    try:
        await asyncio.to_thread(corpus_manager.destroy, corpus)
    except ValueError as exc:
        return error_response(status=400, message=str(exc))
    except RuntimeError as exc:
        logger.exception("Failed to destroy index, corpus=%s", corpus)
        return error_response(status=500, message=str(exc))
    except Exception:
        logger.exception("Failed to destroy index, corpus=%s", corpus)
        return error_response(status=500, message="Internal server error")

    return success_response(status=200, data={"message": "index destroyed"})
