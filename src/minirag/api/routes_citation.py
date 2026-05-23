"""Citation routes for retrieving document citation metadata."""

import asyncio
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

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

    try:
        corpus_manager = get_corpus_manager(request)
        orchestration = await asyncio.to_thread(corpus_manager.get, corpus)
    except ValueError as exc:
        return error_response(status=400, message=str(exc))
    except Exception as exc:
        logger.exception("Failed to load corpus for citation lookup, corpus=%s, citation_key=%s", corpus, citation_key)
        return error_response(status=500, message=str(exc))

    try:
        citation_data = await asyncio.to_thread(orchestration.get_citation, citation_key)
    except ValueError as exc:
        return error_response(status=400, message=str(exc))
    except Exception as exc:
        logger.exception("Failed to get citation, corpus=%s, citation_key=%s", corpus, citation_key)
        return error_response(status=500, message=str(exc))

    if citation_data is None:
        return error_response(status=404, message=f"citation not found: {citation_key}")

    try:
        response_model = CitationResponse.model_validate(citation_data)
    except (KeyError, TypeError, ValidationError) as exc:
        logger.error("Malformed citation data for corpus=%s, citation_key=%s: %s — data=%s", corpus, citation_key, exc, citation_data)
        return error_response(status=500, message=f"malformed citation data for key: {citation_key}")

    return success_response(status=200, data=response_model.model_dump())
