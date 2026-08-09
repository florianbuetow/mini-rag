# Changelog

All notable changes to this project are documented in this file, organized
week by week from the full git history. The format draws on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); the project is not yet
tagged, so sections are grouped by ISO week instead of semantic version.

## [2026-W32] - 2026-08-03 to 2026-08-09

### Added

- Hybrid search script for command-line query execution with lexical, semantic, and hybrid modes.
- Comprehensive documentation on search workflows via the Justfile (HOW_TO_SEARCH.md).
- Showcase and usage examples for search features.

### Changed

- Query API model and routes for improved query parameter handling and flexibility.
- Test suite updated with hybrid search script tests.

## [2026-W31] - 2026-07-27

### Added

- Clean stop for a running ingest via a `STOP` file, honoured at document boundaries.
- Chunk retrieval endpoint for fetching a chunk and its source by ID.

### Changed

- Re-indexing an existing document now rebuilds it across storage and both indices.
- Interrupted ingests repair the affected document on resume instead of skipping it.

### Fixed

- Duplicate citation failures are no longer reported as successful indexing.

## [2026-W28] - 2026-07-07

### Changed

- Reworked the ingest script and citation handling for more reliable indexing.

## [2026-W27] - 2026-06-30

### Added

- MCP configuration help and percentage progress reporting during ingestion.

## [2026-W23] - 2026-06-06 to 2026-06-07

### Added

- Incremental corpus indexing so documents can be added without a full rebuild.
- Embedding-provider support, including LM Studio and the agent provider.

### Changed

- Accessibility and responsive UI pass across the chat interface.
- Theme toggle became an icon button; retrieval status now renders as an inline chip.
- Updated project dependencies and test helpers; ignored `.impeccable/`.

### Fixed

- Improved data durability and end-to-end test safety with UI refinements.

## [2026-W22] - 2026-05-31

### Added

- Status streaming and agent streaming integration.
- LM Studio support in the agent path.

## [2026-W21] - 2026-05-22 to 2026-05-23

### Changed

- Synced core agent, API routes, and test implementations.
- Raised dependency floors and synced local ignore rules for stable CI.

### Fixed

- Made chat theme switching resilient.

## [2026-W14] - 2026-03-31 to 2026-04-01

### Added

- PDF-to-text extraction script with Tesseract OCR support.
- E2E server error tracking, a console-error fixture, and a fail-fast test flag.
- `liteparse` dependency and an `expect_console_errors` test marker.

### Fixed

- Corrected MCP server default port (7001 to 9191) to match the actual service.
- Fixed E2E test failures by adding the missing `title_agent` and `expect_console_errors` markers.

### Security

- Upgraded cryptography, pygments, and requests to patch known vulnerabilities.

## [2026-W12] - 2026-03-18 to 2026-03-19

### Added

- ChatGPT-style web interface for conversational RAG.
- Conversational RAG agent with streaming chat completions.
- Chat persistence API with full CRUD endpoints.
- Wired the chat UI into the app with static serving and a models proxy.
- Overridable search parameters and improved ingestion paths.
- `/onboard` slash command for loading project context.
- Unit, integration, and E2E test suites covering chat features and LM Studio.

### Changed

- Updated dependencies and build configuration for the chat UI.

### Removed

- Removed tmux orchestration scripts and artifacts.

## [2026-W09] - 2026-02-24

### Added

- `list_corpora` MCP tool, a corpora API endpoint, and query logging.

### Fixed

- Addressed PR review findings across docs, safety, types, and tests.

## [2026-W08] - 2026-02-21

### Fixed

- Disabled reload in the config template to prevent high CPU usage.

## [2026-W07] - 2026-02-09 to 2026-02-15

### Added

- Multi-corpus support with `CorpusManager` and corpus-namespaced storage paths.
- Cross-encoder reranking with expanded e2e mode coverage.
- Document citation metadata in the search pipeline, with citation lookup and normalization.
- Evaluation tool and test corpus reporting ROUGE-L metrics.
- Justfile target to delete a corpus index and storage.

### Changed

- Refactored API, orchestration, and storage along SOLID boundaries.
- Increased default chunk size to 500 words and added a startup guard.
- Used typed callable dispatch for query routes and configured `data_dir` for exports.
- Hardened error handling, thread safety, and input validation.

### Removed

- Removed the unused prompts directory.

### Fixed

- Fixed publisher routing, hybrid search sentinels, and citation fallback (3 critical bugs).
- Fixed resource leaks, corpus validation, and `source_type` inference.

## [2026-W06] - 2026-02-07 to 2026-02-08

### Added

- Initial MiniRAG foundation: config, service setup, and core chunking/search components.
- Storage and retrieval backends (FAISS, Tantivy, SQLite) with an orchestration layer.
- FastAPI application layer with an app factory and uvicorn entrypoint.
- HTTP clients and an ingestion script (recursive scan, progress tracking, skips empty files).
- MCP server for hybrid search with client configuration docs.
- Markdown-to-text and interactive search scripts, plus a document chunk inspection tool.
- End-to-end and unit test suites for document indexing and search.
- `persist()`/`close()` lifecycle on storage interfaces and `chunk_id` on search results.

### Changed

- Switched query routes to POST with lifecycle and error handling.
- Switched ingestion and md2txt to fail-fast error handling.
- Restructured project config and CI tooling; added cross-file dead-code detection.

### Fixed

- Fixed async/sync mismatch, SQLite thread safety, and the e2e subprocess import error.

[2026-W31]: https://github.com/florianbuetow/mini-rag/commits/main
[2026-W28]: https://github.com/florianbuetow/mini-rag/commits/main
[2026-W27]: https://github.com/florianbuetow/mini-rag/commits/main
[2026-W23]: https://github.com/florianbuetow/mini-rag/commits/main
