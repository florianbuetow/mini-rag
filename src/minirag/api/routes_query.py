"""Query routes for dense, sparse, and hybrid search."""

import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from minirag.api.models.query import QueryRequest, QueryResponse, QueryResult
from minirag.api.utils import ensure_healthy, error_response, get_orchestration, success_response
from minirag.search.types import SearchResult

router = APIRouter(prefix="/v1/query")


async def _parse_query_request(request: Request) -> QueryRequest | JSONResponse:
    """Parse and validate query request body."""
    try:
        body_object = await request.json()
    except json.JSONDecodeError as exc:
        return error_response(status=400, message=str(exc))

    try:
        return QueryRequest.model_validate(body_object)
    except ValidationError as exc:
        return error_response(status=422, message=str(exc))


def _build_query_response(results: list[SearchResult]) -> QueryResponse:
    """Convert domain search results into API model response."""
    response_results = [QueryResult(text=result.text, score=result.score) for result in results]
    return QueryResponse(results=response_results)


@router.get("/dense")
async def query_dense(request: Request) -> JSONResponse:
    """Run dense search query."""
    guard_response = ensure_healthy(request)
    if guard_response is not None:
        return guard_response

    parsed_payload = await _parse_query_request(request)
    if isinstance(parsed_payload, JSONResponse):
        return parsed_payload

    orchestration = get_orchestration(request)
    try:
        results = orchestration.search_dense(
            query=parsed_payload.query,
            top_k=parsed_payload.top_k,
        )
    except Exception as exc:
        return error_response(status=500, message=str(exc))

    response_model = _build_query_response(results)
    return success_response(status=200, data=response_model.model_dump())


@router.get("/sparse")
async def query_sparse(request: Request) -> JSONResponse:
    """Run sparse search query."""
    guard_response = ensure_healthy(request)
    if guard_response is not None:
        return guard_response

    parsed_payload = await _parse_query_request(request)
    if isinstance(parsed_payload, JSONResponse):
        return parsed_payload

    orchestration = get_orchestration(request)
    try:
        results = orchestration.search_sparse(
            query=parsed_payload.query,
            top_k=parsed_payload.top_k,
        )
    except Exception as exc:
        return error_response(status=500, message=str(exc))

    response_model = _build_query_response(results)
    return success_response(status=200, data=response_model.model_dump())


@router.get("/hybrid")
async def query_hybrid(request: Request) -> JSONResponse:
    """Run hybrid search query."""
    guard_response = ensure_healthy(request)
    if guard_response is not None:
        return guard_response

    parsed_payload = await _parse_query_request(request)
    if isinstance(parsed_payload, JSONResponse):
        return parsed_payload

    orchestration = get_orchestration(request)
    try:
        results = orchestration.search_hybrid(
            query=parsed_payload.query,
            top_k=parsed_payload.top_k,
        )
    except Exception as exc:
        return error_response(status=500, message=str(exc))

    response_model = _build_query_response(results)
    return success_response(status=200, data=response_model.model_dump())
