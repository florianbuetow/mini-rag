# Integration: Auto-Launch — Test Implementation Specification

## Test Framework & Conventions

- **Language:** Python 3.12
- **Test framework:** pytest with pytest-asyncio
- **HTTP testing:** httpx (direct HTTP requests to the running service, not FastAPI TestClient)
- **Process management:** `subprocess.Popen` to start/stop the service
- **Assertion style:** Plain `assert` statements
- **Test location:** `tests_integration/` directory (separate from unit tests — these require a running service)
- **Test runner:** `uv run pytest tests_integration/`

## Test Structure

- **File:** `tests_integration/test_auto_launch.py`
- **Grouping:** Standalone test functions
- **Naming:** `test_<scenario_description>`
- **Execution:** These tests start and stop the actual mini-rag service. They require port 9191 to be available.

## Test Scenario Mapping

| Test Scenario | Test Function | File |
|--------------|---------------|------|
| TS-1: Service starts on port 9191 | `test_service_starts_on_port_9191` | `tests_integration/test_auto_launch.py` |
| TS-2: Root URL serves Chat UI | `test_root_url_serves_chat_ui` | `tests_integration/test_auto_launch.py` |
| TS-3: API endpoints accessible on 9191 | `test_api_endpoints_on_same_port` | `tests_integration/test_auto_launch.py` |
| TS-4: Service stops cleanly | `test_service_stops_and_frees_port` | `tests_integration/test_auto_launch.py` |
| TS-5: Port conflict error | `test_port_conflict_error` | `tests_integration/test_auto_launch.py` |
| TS-6: Start without web/ directory | `test_start_without_web_directory` | `tests_integration/test_auto_launch.py` |

### TS-1: Service starts on port 9191

- **Setup (Given):** Ensure port 9191 is free.
- **Action (When):** Start the service via subprocess (e.g., `uv run src/main.py` with config for port 9191). Wait for the process to be ready (poll `GET http://localhost:9191/v1/health` with retries).
- **Assertion (Then):** Health endpoint returns 200. Service process is running.
- **Teardown:** Stop the service.

### TS-2: Root URL serves Chat UI

- **Setup (Given):** Service is running on port 9191.
- **Action (When):** `httpx.get("http://localhost:9191/")`
- **Assertion (Then):** Status 200. Content-type includes `text/html`. Body contains expected Chat UI content.

### TS-3: API endpoints accessible on 9191

- **Setup (Given):** Service is running on port 9191.
- **Action (When):** `httpx.get("http://localhost:9191/v1/corpora")`
- **Assertion (Then):** Status 200. Response is JSON with `corpora` key.

### TS-4: Service stops and frees port

- **Setup (Given):** Service is running on port 9191.
- **Action (When):** Send `POST http://localhost:9191/v1/shutdown`. Wait for process to exit.
- **Assertion (Then):** Process has exited. `httpx.get("http://localhost:9191/")` raises a connection error (port freed).

### TS-5: Port conflict error

- **Setup (Given):** Bind a socket to port 9191 to occupy it.
- **Action (When):** Attempt to start the service.
- **Assertion (Then):** The service process exits with a non-zero exit code. Stderr or logs contain a message about the port being in use.
- **Teardown:** Close the blocking socket.

### TS-6: Start without web/ directory

- **Setup (Given):** Start the service with a config where the `web/` directory does not exist.
- **Action (When):** `httpx.get("http://localhost:9191/v1/health")` and `httpx.get("http://localhost:9191/")`
- **Assertion (Then):** Health returns 200. Root returns 404.
- **Teardown:** Stop the service.

## Fixtures & Test Data

- **`service_process` fixture (module-scoped):** Starts the mini-rag service as a subprocess with a test configuration file. Polls the health endpoint until ready (max 10 retries, 1s apart). Yields the process. On teardown, sends shutdown and waits for exit.
- **`wait_for_service` helper:** Polls `GET /v1/health` with retries until 200 or timeout. Used in the service_process fixture and standalone tests.
- **`free_port_check` helper:** Attempts to connect to port 9191 and raises if it succeeds (port still in use).
- **Test configuration:** A minimal YAML config file in `tmp_path` with port 9191, test data_dir, and minimal settings.
- **Isolation:** Tests that start/stop the service are ordered carefully — module-scoped fixture for tests that share a running service, function-scoped for tests that need their own service lifecycle (TS-4, TS-5, TS-6).

## Alignment Check

Full alignment. All 6 test scenarios (TS-1 through TS-6) are mapped to test functions. No gaps.

**Design note:** These tests are inherently slower than unit tests (process start/stop, network I/O). They should be in a separate test directory and run separately from `pytest tests/` (which runs fast unit tests).
