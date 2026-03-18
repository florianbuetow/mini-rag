# Static File Serving — Test Implementation Specification

## Test Framework & Conventions

- **Language:** Python 3.12
- **Test framework:** pytest with pytest-asyncio (asyncio_mode = "auto")
- **HTTP testing:** FastAPI `TestClient`
- **Assertion style:** Plain `assert` statements
- **Mocking strategy:** Temporary directories with real files (using `tmp_path` fixture) — no file system mocks
- **Test location:** `tests/` directory

## Test Structure

- **File:** `tests/test_static_file_serving.py`
- **Grouping:** Standalone test functions
- **Naming:** `test_<scenario_description>`

## Test Scenario Mapping

| Test Scenario | Test Function | File |
|--------------|---------------|------|
| TS-1: Serve index.html at root | `test_serve_index_html_at_root` | `tests/test_static_file_serving.py` |
| TS-2: Serve CSS files | `test_serve_css_file` | `tests/test_static_file_serving.py` |
| TS-3: Serve image files | `test_serve_image_file` | `tests/test_static_file_serving.py` |
| TS-4: Return 404 for non-existent root file | `test_404_for_nonexistent_root_file` | `tests/test_static_file_serving.py` |
| TS-5: Return 404 for non-existent CSS file | `test_404_for_nonexistent_css_file` | `tests/test_static_file_serving.py` |
| TS-6: API routes take precedence | `test_api_routes_take_precedence_over_static` | `tests/test_static_file_serving.py` |
| TS-7: Service works without web/ directory | `test_service_works_without_web_directory` | `tests/test_static_file_serving.py` |
| TS-8: Reject path traversal attempts | `test_reject_path_traversal` | `tests/test_static_file_serving.py` |

### TS-1: Serve index.html at root

- **Setup (Given):** Create a `tmp_path/web/index.html` with content `<html>Chat UI</html>`. Build app configured to serve static files from `tmp_path/web/`.
- **Action (When):** `TestClient(app).get("/")`
- **Assertion (Then):** Status 200. Content-type includes `text/html`. Body contains `Chat UI`.

### TS-2: Serve CSS files

- **Setup (Given):** Create `tmp_path/web/css/style.css` with content `body { color: red; }`. Build app.
- **Action (When):** `TestClient(app).get("/css/style.css")`
- **Assertion (Then):** Status 200. Content-type includes `text/css`. Body contains `body { color: red; }`.

### TS-3: Serve image files

- **Setup (Given):** Create `tmp_path/web/gfx/logo.png` with minimal PNG bytes. Build app.
- **Action (When):** `TestClient(app).get("/gfx/logo.png")`
- **Assertion (Then):** Status 200. Content-type includes `image/png`.

### TS-4: Return 404 for non-existent root file

- **Setup (Given):** Build app with static file serving configured.
- **Action (When):** `TestClient(app).get("/nonexistent.html")`
- **Assertion (Then):** Status 404.

### TS-5: Return 404 for non-existent CSS file

- **Setup (Given):** Build app with static file serving configured.
- **Action (When):** `TestClient(app).get("/css/nonexistent.css")`
- **Assertion (Then):** Status 404.

### TS-6: API routes take precedence over static files

- **Setup (Given):** Build app with both API routes and static serving. Set healthy state with `FakeCorpusManager`.
- **Action (When):** `TestClient(app).get("/v1/corpora")`
- **Assertion (Then):** Status 200. Response body is JSON with `corpora` key (not a static file).

### TS-7: Service works without web/ directory

- **Setup (Given):** Build app with static serving pointing to a non-existent directory.
- **Action (When):** `TestClient(app).get("/")` and `TestClient(app).get("/v1/health")`
- **Assertion (Then):** Root returns 404. Health endpoint returns 200.

### TS-8: Reject path traversal attempts

- **Setup (Given):** Build app with static serving from `tmp_path/web/`. Create a sensitive file at `tmp_path/secret.txt`.
- **Action (When):** `TestClient(app).get("/../secret.txt")`
- **Assertion (Then):** Status 404 or 400. Response body does not contain the contents of `secret.txt`.

## Fixtures & Test Data

- **`web_dir` fixture (function-scoped):** Uses pytest `tmp_path` to create `web/`, `web/css/`, `web/gfx/` with sample files. Returns the path to `web/`.
- **`app_with_static` fixture:** Builds a FastAPI app with the static file serving middleware/mount configured to serve from the `web_dir` fixture path. Also includes API routers.
- **Minimal PNG file:** 8-byte PNG header (`\x89PNG\r\n\x1a\n`) sufficient for content-type detection.
- **Isolation:** Each test gets a fresh `tmp_path` — no shared filesystem state.

## Alignment Check

Full alignment. All 8 test scenarios (TS-1 through TS-8) are mapped to test functions. No gaps. No implementation coupling — tests verify HTTP responses and content types at the API boundary.
