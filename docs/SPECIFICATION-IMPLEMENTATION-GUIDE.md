**Planning Basis**
Plan is based on:
- `/Users/flo/Developer/github/minirag/docs/SPECIFICATION.md`
- `/Users/flo/Developer/github/minirag/README.md`
- `/Users/flo/Developer/github/minirag/AGENTS.md`
- `/Users/flo/Developer/github/minirag/config/semgrep/no-default-values.yml`
- `/Users/flo/Developer/github/minirag/config/semgrep/no-sneaky-fallbacks.yml`
- `/Users/flo/Developer/github/minirag/config/semgrep/python-constants.yml`
- `/Users/flo/Developer/github/minirag/config/semgrep/no-noqa.yml`
- `/Users/flo/Developer/github/minirag/config/semgrep/no_type_suppression.yml`

No files were modified.

**Non-Negotiable Constraints**
- No default parameter values in `src/`.
- No fallback patterns in `src/` (`or`, `dict.get(..., default)`, `getattr(..., default)`, ternary fallback for missing values).
- No module-level primitive constants in `src/`.
- No typing suppression (`# type: ignore`, `# noqa`, `# pyright: ignore`, `# mypy: ...` suppressions) in `src/`.
- Fail fast on invalid config, invalid runtime prerequisites, and unexpected runtime states.
- Propagate failures from business logic to API boundary; API returns explicit error envelope.
- Access configuration only through `Config` object and typed sub-config getters.
- Use logging, not `print()`, in service/components.

---

**Detailed Implementation Plan (Checklist)**

1. **Phase 0: Align conflicts before coding**
- [ ] Confirm ingestion error behavior conflict: `/Users/flo/Developer/github/minirag/docs/SPECIFICATION.md` says fail-hard on first file error; `/Users/flo/Developer/github/minirag/AGENTS.md` has generic “continue and count failures” rule for scripts.
- [ ] Resolve by project policy for this system: use fail-hard for `ingest` (recommended, matches spec + fail-fast objective), and document this as an explicit exception.

2. **Phase 1: Project scaffolding and runtime dependencies**
- [ ] Update `/Users/flo/Developer/github/minirag/pyproject.toml` runtime dependencies: `fastapi`, `uvicorn`, `pydantic`, `pyyaml`, `chromadb`, `fasttext-wheel` (or selected fasttext package), `httpx`.
- [ ] Add missing file `/Users/flo/Developer/github/minirag/config.yaml.template` with complete required config structure from spec.
- [ ] Update `/Users/flo/Developer/github/minirag/.gitignore` to include `config.yaml`.
- [ ] Create package/module structure under `/Users/flo/Developer/github/minirag/src/minirag/` exactly as specified (`config.py`, `server/*`, `search/*`, `ingestion/*`, `clients/*`).
- [ ] Add `/Users/flo/Developer/github/minirag/scripts/ingest.py`.

3. **Phase 2: Configuration system (`Config`)**
- [ ] Implement strict nested Pydantic models in `/Users/flo/Developer/github/minirag/src/minirag/config.py` with required fields only.
- [ ] Implement config loading from explicit path (`config.yaml`) with explicit file existence/type checks.
- [ ] Implement startup validation checks:
- [ ] Verify `data_dir` exists, is a directory, and writable.
- [ ] Verify model exists at `{data_dir}/models/{model_name}`.
- [ ] Validate overlap/chunk/alpha ranges and Chroma dimensions as explicit runtime assertions.
- [ ] Implement typed getters only (`get_service_config`, `get_data_config`, `get_index_config`, `get_search_config`).
- [ ] Implement explicit `to_dict()` for `/v1/info` response payload.

4. **Phase 3: Ingestion primitives**
- [ ] Implement word chunker in `/Users/flo/Developer/github/minirag/src/minirag/ingestion/chunker.py`.
- [ ] Validate chunk parameters strictly; reject invalid overlap resulting in non-positive step.
- [ ] Reject empty/whitespace-only document text with explicit error.

5. **Phase 4: Embeddings and hybrid logic**
- [ ] Implement FastText embedding wrapper in `/Users/flo/Developer/github/minirag/src/minirag/search/embeddings.py` implementing Chroma embedding function interface.
- [ ] Validate embedding dimensionality equals configured `dimension`; raise error if mismatch.
- [ ] Implement score normalization/merge in `/Users/flo/Developer/github/minirag/src/minirag/search/hybrid.py`.
- [ ] Define deterministic behavior for edge cases:
- [ ] Empty result sets return empty list.
- [ ] Single-element normalization yields `1.0`.
- [ ] `alpha` outside `[0.0, 1.0]` raises error.

6. **Phase 5: Chroma facade**
- [ ] Implement `/Users/flo/Developer/github/minirag/src/minirag/search/facade.py`.
- [ ] Initialize `PersistentClient` and collection using config values only.
- [ ] Expose operations: index, destroy, vector query, lexical query, hybrid query.
- [ ] Ensure all methods are synchronous.
- [ ] Ensure all failures bubble up without fallback or silent recovery.
- [ ] Normalize endpoint scores to `[0,1]` and keep consistent result shape `{text, score}`.

7. **Phase 6: FastAPI app and routes**
- [ ] Implement app factory in `/Users/flo/Developer/github/minirag/src/minirag/server/app.py`.
- [ ] Store `Config` and `ChromaFacade` in `app.state`.
- [ ] Implement admin routes in `/Users/flo/Developer/github/minirag/src/minirag/server/routes_admin.py`: health/info/shutdown.
- [ ] Implement index routes in `/Users/flo/Developer/github/minirag/src/minirag/server/routes_index.py`: `POST /v1/index`, `DELETE /v1/index`.
- [ ] Implement query routes in `/Users/flo/Developer/github/minirag/src/minirag/server/routes_query.py`: vector/lexical/hybrid.
- [ ] Implement response helpers in `/Users/flo/Developer/github/minirag/src/minirag/server/utils.py`.
- [ ] Add request validation + exception mapping:
- [ ] Malformed JSON -> 400 envelope.
- [ ] Field validation errors -> 422 envelope.
- [ ] Runtime exceptions -> 500 envelope with raw message.
- [ ] Implement shutdown gate behavior (`503`) for requests after shutdown initiation.

8. **Phase 7: Entry point**
- [ ] Replace placeholder `/Users/flo/Developer/github/minirag/src/main.py`.
- [ ] Load config from explicit path.
- [ ] Configure logging level from config.
- [ ] Create app via app factory and start uvicorn with configured host/port/reload/log level.
- [ ] Fail immediately if config/startup validation fails.

9. **Phase 8: Clients**
- [ ] Implement `/Users/flo/Developer/github/minirag/src/minirag/clients/base.py` with health-check-before-operation.
- [ ] Implement `/Users/flo/Developer/github/minirag/src/minirag/clients/indexing.py`.
- [ ] Implement `/Users/flo/Developer/github/minirag/src/minirag/clients/query.py`.
- [ ] Ensure all client methods raise on non-200/non-expected status with server-provided message.

10. **Phase 9: Ingestion script and just targets**
- [ ] Implement `/Users/flo/Developer/github/minirag/scripts/ingest.py` to ingest all `.txt` files in `{data_dir}/input/txt/`.
- [ ] Enforce fail-hard behavior on first indexing failure (or project-approved alternative from Phase 0 decision).
- [ ] Update `/Users/flo/Developer/github/minirag/justfile`:
- [ ] `init`: create required dirs, `uv sync --all-extras`, download model, copy template if missing.
- [ ] `start`: run service.
- [ ] `stop`: call shutdown endpoint.
- [ ] `status`: check health/info.
- [ ] `ingest`: destroy then ingest.
- [ ] Keep existing CI/test/style targets.

11. **Phase 10: Tests (required from start)**
- [ ] Add config tests (`load success`, `missing key`, `wrong type`, `model missing`, `data dir unwritable`) in `/Users/flo/Developer/github/minirag/tests/`.
- [ ] Add chunker tests (`normal chunking`, `overlap validation`, `empty text`).
- [ ] Add hybrid tests (`alpha bounds`, `merge correctness`, `normalization edge cases`).
- [ ] Add response util tests (`success envelope`, `error envelope`).
- [ ] Add route tests with FastAPI test client and mocked facade.
- [ ] Add client tests with mocked HTTP responses.
- [ ] Add ingest script tests (file discovery, fail-fast behavior).
- [ ] Keep coverage >= 80%.

12. **Phase 11: Quality gates during implementation**
- [ ] After each code batch: run `just test`.
- [ ] After each code batch: run `just run` (with valid local config/model setup).
- [ ] Before completion: run `just ci-quiet`.

---

**Function/Method Behavior Contracts**

| Location | Function/Method | Input | Output | Errors |
|---|---|---|---|---|
| `/Users/flo/Developer/github/minirag/src/minirag/config.py` | `load_config(config_path: Path) -> Config` | absolute/relative path to YAML file | validated `Config` instance | `FileNotFoundError`, `ValueError`, `TypeError`, `ValidationError`, `PermissionError` |
| `/Users/flo/Developer/github/minirag/src/minirag/config.py` | `validate_startup(config: Config) -> None` | `Config` | `None` | `FileNotFoundError`, `NotADirectoryError`, `PermissionError`, `ValueError` |
| `/Users/flo/Developer/github/minirag/src/minirag/config.py` | `Config.get_service_config(self) -> ServiceConfig` | none | typed service config | none (must always exist post-validation) |
| `/Users/flo/Developer/github/minirag/src/minirag/ingestion/chunker.py` | `chunk_text(document_text: str, chunk_size: int, overlap: float) -> list[str]` | raw document + chunk params | ordered chunk list | `ValueError` for empty text/invalid chunk params |
| `/Users/flo/Developer/github/minirag/src/minirag/search/embeddings.py` | `FastTextEmbeddingFunction.__call__(self, input: list[str]) -> list[list[float]]` | list of texts | vectors matching configured dimension | `ValueError`, model loading/runtime errors |
| `/Users/flo/Developer/github/minirag/src/minirag/search/hybrid.py` | `merge_hybrid(vector_results, lexical_results, alpha, top_k) -> list[SearchResult]` | two result sets, weight, limit | ranked merged results | `ValueError` on bad alpha/top_k/invalid score states |
| `/Users/flo/Developer/github/minirag/src/minirag/search/facade.py` | `index_document(document_text: str) -> int` | document text | number of chunks indexed | `ValueError`, Chroma/embedding errors |
| `/Users/flo/Developer/github/minirag/src/minirag/search/facade.py` | `destroy_index() -> None` | none | none | Chroma errors |
| `/Users/flo/Developer/github/minirag/src/minirag/search/facade.py` | `search_vector(query: str, top_k: int) -> list[SearchResult]` | query + limit | normalized results | `ValueError`, Chroma errors |
| `/Users/flo/Developer/github/minirag/src/minirag/search/facade.py` | `search_lexical(query: str, top_k: int) -> list[SearchResult]` | query + limit | normalized results | `ValueError`, Chroma errors |
| `/Users/flo/Developer/github/minirag/src/minirag/search/facade.py` | `search_hybrid(query: str, top_k: int) -> list[SearchResult]` | query + limit | normalized merged results | `ValueError`, Chroma/hybrid errors |
| `/Users/flo/Developer/github/minirag/src/minirag/server/utils.py` | `success_response(status: int, data: dict[str, Any]) -> JSONResponse` | HTTP status + payload | envelope `{"status":..., "data":...}` | `ValueError` for malformed envelope input |
| `/Users/flo/Developer/github/minirag/src/minirag/server/utils.py` | `error_response(status: int, message: str) -> JSONResponse` | HTTP status + message | envelope `{"status":..., "error":...}` | `ValueError` for malformed envelope input |
| `/Users/flo/Developer/github/minirag/src/minirag/clients/base.py` | `ensure_healthy() -> None` | none | none | raises on unhealthy/unreachable service |
| `/Users/flo/Developer/github/minirag/src/minirag/clients/indexing.py` | `index_document(text: str) -> int` | document text | chunks indexed | HTTP/network/runtime errors |
| `/Users/flo/Developer/github/minirag/src/minirag/clients/indexing.py` | `destroy_index() -> None` | none | none | HTTP/network/runtime errors |
| `/Users/flo/Developer/github/minirag/src/minirag/clients/query.py` | `search_vector(query: str, top_k: int) -> list[SearchResult]` | query + limit | results | HTTP/network/runtime errors |
| `/Users/flo/Developer/github/minirag/src/minirag/clients/query.py` | `search_lexical(query: str, top_k: int) -> list[SearchResult]` | query + limit | results | HTTP/network/runtime errors |
| `/Users/flo/Developer/github/minirag/src/minirag/clients/query.py` | `search_hybrid(query: str, top_k: int) -> list[SearchResult]` | query + limit | results | HTTP/network/runtime errors |
| `/Users/flo/Developer/github/minirag/scripts/ingest.py` | `main() -> int` | CLI invocation | process exit code | returns non-zero on first failure (fail-hard) |

---

**Semgrep-Safe Code Examples (Fail-Fast, No Defaults/Fallbacks)**

```python
# /Users/flo/Developer/github/minirag/src/minirag/config.py
from pathlib import Path
from pydantic import BaseModel, ValidationError
import yaml

class ServiceConfig(BaseModel):
    host: str
    port: int
    reload: bool
    log_level: str

class Config(BaseModel):
    service: ServiceConfig
    # ... other required sections

def load_config(config_path: Path) -> Config:
    if not config_path.exists():
        raise FileNotFoundError(f"config file does not exist: {config_path}")
    raw_text = config_path.read_text(encoding="utf-8")
    loaded = yaml.safe_load(raw_text)
    if loaded is None:
        raise ValueError("config file is empty")
    if not isinstance(loaded, dict):
        raise TypeError("config root must be a mapping")
    try:
        return Config.model_validate(loaded)
    except ValidationError as exc:
        raise ValueError(f"config validation failed: {exc}") from exc
```

```python
# /Users/flo/Developer/github/minirag/src/minirag/ingestion/chunker.py
def chunk_text(document_text: str, chunk_size: int, overlap: float) -> list[str]:
    if not document_text.strip():
        raise ValueError("document_text must not be empty")
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if overlap < 0.0 or overlap >= 1.0:
        raise ValueError("overlap must be in [0.0, 1.0)")
    words = document_text.split()
    overlap_words = int(chunk_size * overlap)
    step = chunk_size - overlap_words
    if step <= 0:
        raise ValueError("overlap yields non-positive step")
    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk_words = words[start:end]
        chunks.append(" ".join(chunk_words))
        start += step
    return chunks
```

```python
# /Users/flo/Developer/github/minirag/src/minirag/search/hybrid.py
def merge_hybrid(
    vector_results: list[dict[str, float | str]],
    lexical_results: list[dict[str, float | str]],
    alpha: float,
    top_k: int,
) -> list[dict[str, float | str]]:
    if alpha < 0.0 or alpha > 1.0:
        raise ValueError("alpha must be in [0.0, 1.0]")
    if top_k <= 0:
        raise ValueError("top_k must be > 0")
    # ... explicit normalization + weighted merge
    return []
```

```python
# /Users/flo/Developer/github/minirag/src/minirag/server/routes_query.py
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/v1/query")

@router.post("/vector")
def query_vector(request: Request, payload: QueryRequest) -> JSONResponse:
    facade = request.app.state.facade
    results = facade.search_vector(payload.query, payload.top_k)
    return success_response(200, {"results": results})
```

```python
# /Users/flo/Developer/github/minirag/src/minirag/clients/base.py
import httpx

class BaseClient:
    def __init__(self, service_host: str, service_port: int) -> None:
        self._client = httpx.Client(base_url=f"http://{service_host}:{service_port}/v1", timeout=None)

    def ensure_healthy(self) -> None:
        response = self._client.get("/health")
        if response.status_code != 200:
            raise RuntimeError(f"service unhealthy: {response.text}")
```

```python
# /Users/flo/Developer/github/minirag/scripts/ingest.py
def main() -> int:
    # load config, create client, destroy index, ingest files
    # fail hard on first failure
    return 0
```

---

**Implementation Validation Matrix**
- Config parse/startup: missing file, empty file, missing keys, wrong types, non-writable data dir, missing model file.
- API envelope: every endpoint returns exactly one of `data` or `error`.
- HTTP semantics: 400 malformed JSON, 422 invalid fields, 500 runtime failure, 503 shutdown state.
- Search behavior: vector/lexical/hybrid shape consistency, score range `[0,1]`, top_k truncation, deterministic ordering.
- Client behavior: pre-flight health check on every operation.
- No defaults/fallbacks/type suppressions/module constants in `src`.

---

**Execution Order (Recommended)**
1. Dependencies + config template + `.gitignore`.
2. `config.py`.
3. `chunker.py`, `embeddings.py`, `hybrid.py`.
4. `facade.py`.
5. `server/utils.py` + route schemas + route handlers + app factory.
6. `src/main.py`.
7. clients.
8. `scripts/ingest.py`.
9. `justfile` updates.
10. full test suite + CI gates.

If you want, next turn I can convert this into an implementation sprint board with task IDs and exact test cases per task.
