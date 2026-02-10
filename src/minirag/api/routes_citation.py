"""Citation routes for retrieving document citation metadata."""

import asyncio
import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from minirag.api.models.citation import CitationResponse
from minirag.api.responses import error_response, success_response
from minirag.api.utils import ensure_healthy, get_corpus_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/corpus/{corpus}")


@router.get("/citation/{citation_key}")
async def get_citation(request: Request, corpus: str, citation_key: str) -> JSONResponse:
    """Return full citation data for a given citation_key."""
    guard_response = ensure_healthy(request)
    if guard_response is not None:
        return guard_response

    corpus_manager = get_corpus_manager(request)
    try:
        orchestration = await asyncio.to_thread(corpus_manager.get, corpus)
    except ValueError as exc:
        return error_response(status=400, message=str(exc))

    try:
        citation_json = await asyncio.to_thread(orchestration.get_citation, citation_key)
    except ValueError as exc:
        return error_response(status=400, message=str(exc))
    except Exception:
        logger.exception("Failed to get citation, corpus=%s, citation_key=%s", corpus, citation_key)
        return error_response(status=500, message="Internal server error")

    if citation_json is None:
        return error_response(status=404, message=f"citation not found: {citation_key}")

    parsed = json.loads(citation_json)
    response_model = CitationResponse(
        citation_key=parsed["citation_key"],
        source_type=parsed["source_type"],
        common=parsed["common"],
        source_data=parsed["source_data"],
    )
    return success_response(status=200, data=response_model.model_dump())
