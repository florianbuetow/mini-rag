# Corpus Listing — Behavioral Specification

## Objective

Provide an API endpoint that returns the list of available corpora in the mini-rag system, enabling clients (including the Chat UI) to discover which document collections are available for querying.

## User Stories & Acceptance Criteria

US-1: As an API consumer, I want to retrieve a list of all available corpora, so that I can present corpus options to users or select a corpus for querying.

Acceptance Criteria:
  AC-1.1: A `GET /v1/corpora` request returns HTTP 200 with a JSON body `{"status": "success", "data": {"corpora": [...]}}` where `corpora` is an array of corpus name strings.
  AC-1.2: The `corpora` array is sorted alphabetically (case-insensitive, ascending).
  AC-1.3: Each entry in the `corpora` array is a non-empty string representing a corpus name.
  AC-1.4: When the service is not in "healthy" status, `GET /v1/corpora` returns HTTP 503 with an appropriate error response.

## Constraints

- **Technical:** The endpoint is part of the existing FastAPI application under the `/v1` route prefix.
- **Technical:** The endpoint must use the existing corpus manager to discover corpora — it must not scan the filesystem independently.
- **Operational:** The endpoint must be available whenever the mini-rag service is running and healthy.

## Edge Cases

- **No corpora exist:** The endpoint returns HTTP 200 with `{"status": "success", "data": {"corpora": []}}` (empty array, not an error).
- **Service unhealthy:** The endpoint returns HTTP 503 before attempting to list corpora.

## Non-Goals

- **Corpus creation or deletion via this endpoint.** This endpoint is read-only. Corpus management is handled through the ingestion pipeline.
- **Pagination.** The number of corpora is expected to be small (tens, not thousands). No pagination is needed.
- **Filtering or search.** Clients receive the full list and filter client-side.

## Open Questions

None.
