"""Query routes for dense, sparse, and hybrid search."""

import asyncio
import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from minirag.api.models.query import QueryRequest, QueryResponse, QueryResult
from minirag.api.utils import ensure_healthy, error_response, get_corpus_manager, success_response
from minirag.search.types import SearchResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/corpus/{corpus}/query")


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
    response_results = [QueryResult(chunk_id=result.chunk_id, text=result.text, score=result.score) for result in results]
    return QueryResponse(results=response_results)


@router.post("/dense")
async def query_dense(request: Request, corpus: str) -> JSONResponse:
    """Run dense search query."""
    guard_response = ensure_healthy(request)
    if guard_response is not None:
        return guard_response

    parsed_payload = await _parse_query_request(request)
    if isinstance(parsed_payload, JSONResponse):
        return parsed_payload

    query_display = parsed_payload.query[:120] + "..." if len(parsed_payload.query) > 120 else parsed_payload.query
    logger.debug('corpus=%s query="%s" top_k=%d', corpus, query_display, parsed_payload.top_k)

    corpus_manager = get_corpus_manager(request)
    try:
        orchestration = corpus_manager.get(corpus)
    except ValueError as exc:
        return error_response(status=400, message=str(exc))

    try:
        results = await asyncio.to_thread(
            orchestration.search_dense,
            query=parsed_payload.query,
            top_k=parsed_payload.top_k,
        )
    except ValueError as exc:
        return error_response(status=400, message=str(exc))
    except RuntimeError as exc:
        logger.exception("Failed to execute dense search, corpus=%s", corpus)
        return error_response(status=500, message=str(exc))
    except Exception:
        logger.exception("Failed to execute dense search, corpus=%s", corpus)
        return error_response(status=500, message="Internal server error")

    response_model = _build_query_response(results)
    return success_response(status=200, data=response_model.model_dump())


@router.post("/sparse")
async def query_sparse(request: Request, corpus: str) -> JSONResponse:
    """Run sparse search query."""
    guard_response = ensure_healthy(request)
    if guard_response is not None:
        return guard_response

    parsed_payload = await _parse_query_request(request)
    if isinstance(parsed_payload, JSONResponse):
        return parsed_payload

    query_display = parsed_payload.query[:120] + "..." if len(parsed_payload.query) > 120 else parsed_payload.query
    logger.debug('corpus=%s query="%s" top_k=%d', corpus, query_display, parsed_payload.top_k)

    corpus_manager = get_corpus_manager(request)
    try:
        orchestration = corpus_manager.get(corpus)
    except ValueError as exc:
        return error_response(status=400, message=str(exc))

    try:
        results = await asyncio.to_thread(
            orchestration.search_sparse,
            query=parsed_payload.query,
            top_k=parsed_payload.top_k,
        )
    except ValueError as exc:
        return error_response(status=400, message=str(exc))
    except RuntimeError as exc:
        logger.exception("Failed to execute sparse search, corpus=%s", corpus)
        return error_response(status=500, message=str(exc))
    except Exception:
        logger.exception("Failed to execute sparse search, corpus=%s", corpus)
        return error_response(status=500, message="Internal server error")

    response_model = _build_query_response(results)
    return success_response(status=200, data=response_model.model_dump())


@router.post("/hybrid")
async def query_hybrid(request: Request, corpus: str) -> JSONResponse:
    """Run hybrid search query."""
    guard_response = ensure_healthy(request)
    if guard_response is not None:
        return guard_response

    parsed_payload = await _parse_query_request(request)
    if isinstance(parsed_payload, JSONResponse):
        return parsed_payload

    query_display = parsed_payload.query[:120] + "..." if len(parsed_payload.query) > 120 else parsed_payload.query
    logger.debug('corpus=%s query="%s" top_k=%d', corpus, query_display, parsed_payload.top_k)

    corpus_manager = get_corpus_manager(request)
    try:
        orchestration = corpus_manager.get(corpus)
    except ValueError as exc:
        return error_response(status=400, message=str(exc))

    try:
        results = await asyncio.to_thread(
            orchestration.search_hybrid,
            query=parsed_payload.query,
            top_k=parsed_payload.top_k,
        )
    except ValueError as exc:
        return error_response(status=400, message=str(exc))
    except RuntimeError as exc:
        logger.exception("Failed to execute hybrid search, corpus=%s", corpus)
        return error_response(status=500, message=str(exc))
    except Exception:
        logger.exception("Failed to execute hybrid search, corpus=%s", corpus)
        return error_response(status=500, message="Internal server error")

    response_model = _build_query_response(results)
    return success_response(status=200, data=response_model.model_dump())
