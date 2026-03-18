# Integration: Auto-Launch — Behavioral Specification

## Objective

Ensure the Chat UI is automatically available when the mini-rag service starts, so that users do not need to manually launch a separate server for the web interface.

## User Stories & Acceptance Criteria

US-1: As a user, I want the Chat UI to be available as soon as I start the mini-rag service, so that I can immediately open my browser and start chatting.

Acceptance Criteria:
  AC-1.1: When the mini-rag service starts via `just start`, the Chat UI is served on port 9191.
  AC-1.2: Navigating to `http://localhost:9191/` in a browser loads the Chat UI (`web/index.html`).
  AC-1.3: The API endpoints (`/v1/corpora`, `/v1/chats`, `/v1/chat/completions`, etc.) are accessible on the same port 9191.
  AC-1.4: No additional manual steps are required after `just start` to access the Chat UI.

US-2: As a user, I want the mini-rag API and the Chat UI to stop together, so that there are no orphaned processes.

Acceptance Criteria:
  AC-2.1: When the mini-rag service is stopped via `just stop` or `POST /v1/shutdown`, both the API and the static file serving stop.
  AC-2.2: After stopping, port 9191 is no longer in use.

## Constraints

- **Technical:** The Chat UI and API are served by the same FastAPI application on port 9191.
- **Technical:** The `just start` recipe must be updated to serve on port 9191.
- **Technical:** The existing mini-rag API functionality (indexing, querying, health, info, shutdown) must remain fully functional at the same port.
- **Operational:** The service is intended for local use on a single machine.

## Edge Cases

- **Port 9191 already in use:** The service fails to start with a clear error message indicating the port is occupied. It does not silently fall back to a different port.
- **`web/` directory missing:** The service starts successfully. API endpoints work normally. Static file requests return HTTP 404. A warning is logged at startup indicating the web directory was not found.

## Non-Goals

- **Running the Chat UI on a separate port from the API.** Everything is served from a single port.
- **HTTPS/TLS support.** Local use only; plain HTTP is sufficient.
- **Reverse proxy configuration.** Not needed for local development.
- **Auto-opening the browser.** The user manually navigates to the URL.

## Open Questions

None.
