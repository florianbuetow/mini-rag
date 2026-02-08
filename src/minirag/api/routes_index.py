"""Index management routes."""

import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from minirag.api.models.index import IndexRequest, IndexResponse
from minirag.api.utils import ensure_healthy, error_response, get_orchestration, success_response

router = APIRouter(prefix="/v1")


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
async def index_document(request: Request) -> JSONResponse:
    """Index a single document into storage and retrieval backends."""
    guard_response = ensure_healthy(request)
    if guard_response is not None:
        return guard_response

    parsed_payload = await _parse_index_request(request)
    if isinstance(parsed_payload, JSONResponse):
        return parsed_payload

    orchestration = get_orchestration(request)

    try:
        document_id, chunk_ids = orchestration.index_document(parsed_payload.document)
    except Exception as exc:
        return error_response(status=500, message=str(exc))

    response_model = IndexResponse(
        document_id=document_id,
        chunks_indexed=len(chunk_ids),
        chunk_ids=chunk_ids,
    )
    return success_response(status=200, data=response_model.model_dump())


@router.delete("/index")
async def destroy_index(request: Request) -> JSONResponse:
    """Destroy the full index across all backends."""
    guard_response = ensure_healthy(request)
    if guard_response is not None:
        return guard_response

    orchestration = get_orchestration(request)
    try:
        orchestration.destroy_index()
    except Exception as exc:
        return error_response(status=500, message=str(exc))

    return success_response(status=200, data={"message": "index destroyed"})
