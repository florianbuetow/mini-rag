# Corpus Listing — Behavioral Specification

## Objective

Provide API endpoints that return the list of available corpora in the mini-rag system and optional Markdown descriptions for those corpora, enabling clients (including the Chat UI and MCP server) to discover which document collections are available for querying and display human-readable corpus information.

## User Stories & Acceptance Criteria

US-1: As an API consumer, I want to retrieve a list of all available corpora with their descriptions, so that I can present corpus options and explain what each corpus contains.

Acceptance Criteria:
  AC-1.1: A `GET /v1/corpora` request returns HTTP 200 with a JSON body `{"status": 200, "data": {"corpora": [...], "descriptions": {...}}}` where `corpora` is an array of corpus name strings and `descriptions` is an object keyed by corpus name.
  AC-1.2: The `corpora` array is sorted alphabetically (case-insensitive, ascending).
  AC-1.3: Each entry in the `corpora` array is a non-empty string representing a corpus name.
  AC-1.4: When the service is not in "healthy" status, `GET /v1/corpora` returns HTTP 503 with an appropriate error response.
  AC-1.5: `data.descriptions` contains exactly one string value for each corpus in `data.corpora`.
  AC-1.6: A loaded corpus without a stored description returns the exact placeholder `No description available.`.

US-2: As an API consumer, I want to retrieve one corpus description directly, so that I can refresh or inspect corpus information without fetching every corpus.

Acceptance Criteria:
  AC-2.1: A `GET /v1/corpus/{corpus}/description` request for a loaded corpus returns HTTP 200 with `{"status": 200, "data": {"corpus": "<corpus>", "description": "<markdown>"}}`.
  AC-2.2: A loaded corpus without a stored description returns HTTP 200 with `No description available.`.
  AC-2.3: An invalid corpus name returns HTTP 400.
  AC-2.4: A valid but unknown corpus returns HTTP 404.
  AC-2.5: An unreadable, non-file, symlinked, or invalid UTF-8 stored description returns HTTP 500.

US-3: As an operator, I want to ingest a Markdown corpus description without indexing it, so that corpus information is available to clients without affecting search results.

Acceptance Criteria:
  AC-3.1: `just describe-corpus <corpus>` prints the current description, while an optional `<markdown-file>` stores it at `data/storage/<corpus>/description.md`.
  AC-3.2: The source file must be a regular non-symlink UTF-8 `.md` file, must contain non-whitespace content, and must be at most 64 KiB.
  AC-3.3: Description ingestion requires an existing loaded corpus and must not create a new corpus.
  AC-3.4: Descriptions are not chunked, embedded, indexed, or recorded in the ingestion ledger.
  AC-3.5: Re-ingestion atomically replaces the previous description.
  AC-3.6: Index deletion and rebuild operations preserve `data/storage/<corpus>/description.md`.

## Constraints

- **Technical:** The endpoint is part of the existing FastAPI application under the `/v1` route prefix.
- **Technical:** Corpus endpoints must use the existing corpus manager to discover corpora and descriptions — routes must not scan the filesystem independently.
- **Operational:** The endpoint must be available whenever the mini-rag service is running and healthy.
- **Compatibility:** `GET /v1/corpora` must keep `data.corpora` as a top-level field in `data`; `data.descriptions` is additive.

## Edge Cases

- **No corpora exist:** The endpoint returns HTTP 200 with `{"status": 200, "data": {"corpora": [], "descriptions": {}}}` (empty array and empty object, not an error).
- **Service unhealthy:** The endpoint returns HTTP 503 before attempting to list corpora.
- **Missing description:** A loaded corpus with no `description.md` returns `No description available.`.
- **Unknown corpus:** The individual description endpoint returns HTTP 404.
- **Invalid stored description:** The API returns HTTP 500 rather than replacing the error with the missing-description placeholder.

## Non-Goals

- **Corpus creation or deletion via this endpoint.** This endpoint is read-only. Corpus management is handled through the ingestion pipeline.
- **Pagination.** The number of corpora is expected to be small (tens, not thousands). No pagination is needed.
- **Filtering or search.** Clients receive the full list and filter client-side.
- **Description indexing.** Corpus descriptions are metadata and must not influence retrieval results.

## Open Questions

None.
