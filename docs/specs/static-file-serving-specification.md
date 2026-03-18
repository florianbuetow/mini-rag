# Static File Serving — Behavioral Specification

## Objective

Serve the Chat UI's static files (HTML, CSS, images) from the mini-rag service so that users can access the web interface by navigating to the service's root URL without requiring a separate web server.

## User Stories & Acceptance Criteria

US-1: As a user, I want to access the Chat UI by navigating to the service root URL in my browser, so that I can use the chat interface without additional setup.

Acceptance Criteria:
  AC-1.1: A `GET /` request returns the contents of `web/index.html` with content type `text/html`.
  AC-1.2: A `GET /css/<filename>` request returns the corresponding file from `web/css/` with the appropriate CSS content type.
  AC-1.3: A `GET /gfx/<filename>` request returns the corresponding file from `web/gfx/` with the appropriate image content type.
  AC-1.4: Static files are served from the `web/` directory relative to the project root.

US-2: As a user, I want to receive clear error responses when requesting non-existent static files, so that I can distinguish between missing files and server errors.

Acceptance Criteria:
  AC-2.1: A `GET /nonexistent.html` request returns HTTP 404.
  AC-2.2: A `GET /css/nonexistent.css` request returns HTTP 404.

## Constraints

- **Technical:** Static files are served by the same FastAPI application that serves the API endpoints.
- **Technical:** API routes under `/v1/` must take precedence over static file serving — a request to `/v1/corpora` must hit the API router, not look for a static file.
- **Technical:** The `web/` directory structure is: `web/index.html`, `web/css/`, `web/gfx/`.
- **Operational:** The Chat UI is served on port 9191 (the same port as the mini-rag service or a dedicated port, per integration task).

## Edge Cases

- **`web/` directory does not exist:** The service starts without error but returns HTTP 404 for all static file requests. The API endpoints remain functional.
- **Path traversal attempts:** Requests containing `..` in the path (e.g., `GET /../../etc/passwd`) must not serve files outside the `web/` directory. The server returns HTTP 404 or HTTP 400 for such requests.
- **Empty `web/` directory:** The service starts without error. All static file requests return HTTP 404.

## Non-Goals

- **Server-side rendering.** The frontend is a static single-page application. The server does not render HTML dynamically.
- **File upload.** The static file server is read-only.
- **Caching headers or CDN integration.** Not required for a local development tool.
- **Compression (gzip/brotli).** Not required for local use.

## Open Questions

None.
