"""Query routes for dense, sparse, and hybrid search."""

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Protocol

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from minirag.api.models.query import QueryRequest, QueryResponse, QueryResult
from minirag.api.responses import error_response, success_response
from minirag.api.utils import ensure_healthy, get_corpus_manager
from minirag.orchestration import Orchestration
from minirag.search.types import SearchResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/corpus/{corpus}/query")


class QuerySearchFn(Protocol):
    """Typed query search callable used by query route dispatch."""

    def __call__(self, *, query: str, top_k: int) -> list[SearchResult]:
        """Execute one query mode and return search results."""
        ...


async def _parse_query_request(request: Request) -> QueryRequest | JSONResponse:
    """Parse and validate query request body."""
    try:
        body_object = await request.json()
    except json.JSONDecodeError as exc:
        return error_response(status=400, message=str(exc))

    try:
        return QueryRequest.model_validate(body_object)
    except ValidationError as exc:
        logger.debug("Validation error on query request: %s", exc)
        return error_response(status=422, message=str(exc))


def _build_query_response(results: list[SearchResult]) -> QueryResponse:
    """Convert domain search results into API model response."""
    response_results = [
        QueryResult(
            chunk_id=result.chunk_id,
            document_id=result.document_id,
            citation_key=result.citation_key,
            text=result.text,
            score=result.score,
        )
        for result in results
    ]
    return QueryResponse(results=response_results)


async def _run_query(
    request: Request,
    corpus: str,
    search_name: str,
    search_fn_getter: Callable[[Orchestration], QuerySearchFn],
) -> JSONResponse:
    """Shared query handler for dense, sparse, and hybrid search."""
    guard_response = ensure_healthy(request)
    if guard_response is not None:
        return guard_response

    parsed_payload = await _parse_query_request(request)
    if isinstance(parsed_payload, JSONResponse):
        return parsed_payload

    query_display = parsed_payload.query[:120] + "..." if len(parsed_payload.query) > 120 else parsed_payload.query
    logger.info('%s corpus=%s query="%s" top_k=%d', search_name, corpus, query_display, parsed_payload.top_k)

    corpus_manager = get_corpus_manager(request)
    try:
        orchestration = await asyncio.to_thread(corpus_manager.get, corpus)
    except ValueError as exc:
        return error_response(status=400, message=str(exc))

    search_fn = search_fn_getter(orchestration)
    try:
        results = await asyncio.to_thread(
            search_fn,
            query=parsed_payload.query,
            top_k=parsed_payload.top_k,
        )
    except ValueError as exc:
        return error_response(status=400, message=str(exc))
    except RuntimeError as exc:
        logger.exception("Failed to execute %s search, corpus=%s", search_name, corpus)
        return error_response(status=500, message=str(exc))
    except Exception:
        logger.exception("Failed to execute %s search, corpus=%s", search_name, corpus)
        return error_response(status=500, message="Internal server error")

    response_model = _build_query_response(results)
    return success_response(status=200, data=response_model.model_dump())


@router.post("/dense")
async def query_dense(request: Request, corpus: str) -> JSONResponse:
    """Run dense search query."""
    return await _run_query(
        request=request,
        corpus=corpus,
        search_name="dense",
        search_fn_getter=lambda orchestration: orchestration.search_dense,
    )


@router.post("/sparse")
async def query_sparse(request: Request, corpus: str) -> JSONResponse:
    """Run sparse search query."""
    return await _run_query(
        request=request,
        corpus=corpus,
        search_name="sparse",
        search_fn_getter=lambda orchestration: orchestration.search_sparse,
    )


def _hybrid_search_fn(orchestration: Orchestration) -> QuerySearchFn:
    """Wrap search_hybrid into a QuerySearchFn by binding alpha and use_reranking to None."""

    def _search(*, query: str, top_k: int) -> list[SearchResult]:
        return orchestration.search_hybrid(query=query, top_k=top_k, alpha=None, use_reranking=None)

    return _search


@router.post("/hybrid")
async def query_hybrid(request: Request, corpus: str) -> JSONResponse:
    """Run hybrid search query."""
    return await _run_query(
        request=request,
        corpus=corpus,
        search_name="hybrid",
        search_fn_getter=_hybrid_search_fn,
    )
