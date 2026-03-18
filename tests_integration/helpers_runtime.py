"""Runtime helpers for integration tests.

Provides temp config creation, subprocess start/stop, free-port allocation,
ingestion wrappers, and LM Studio CLI wrappers.
"""

import contextlib
import os
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path

import httpx
import yaml

PROJECT_ROOT = Path(__file__).parent.parent

# Large model patterns to reject
REJECT_MODEL_PATTERNS = ["32b", "70b", "72b", "110b", "405b"]

# Preferred model patterns in priority order
PREFERRED_MODEL_PATTERNS = [
    ("qwen", 14),
    ("gemma", 12),
]


def find_free_port() -> int:
    """Find and return a free TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def port_in_use(port: int) -> bool:
    """Check if a port is currently in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


def create_temp_data_dir() -> Path:
    """Create an isolated temporary data directory for tests.

    Returns the path to the temp dir. Caller should clean up with shutil.rmtree.
    Structure:
        tmp/data/input/knowledgebase/txt/
        tmp/data/input/llmevals/txt/
        tmp/data/storage/
        tmp/data/index/
        tmp/data/models/cc.en.300.bin (symlinked from production)
        tmp/chats/
    """
    tmp = Path(tempfile.mkdtemp(prefix="minirag_test_"))
    (tmp / "data" / "input" / "knowledgebase" / "txt").mkdir(parents=True)
    (tmp / "data" / "input" / "llmevals" / "txt").mkdir(parents=True)
    (tmp / "data" / "storage").mkdir(parents=True)
    (tmp / "data" / "index").mkdir(parents=True)
    (tmp / "data" / "models").mkdir(parents=True)
    (tmp / "chats").mkdir(parents=True)

    # Symlink the embedding model from the production data dir.
    # The service requires this file to pass startup validation.
    prod_model = _find_production_model()
    if prod_model is not None:
        (tmp / "data" / "models" / prod_model.name).symlink_to(prod_model)

    return tmp


def _find_production_model() -> Path | None:
    """Locate the production cc.en.300.bin embedding model file.

    Checks both the config.yaml data_dir and a well-known fallback path.
    """
    config_yaml = PROJECT_ROOT / "config.yaml"
    if config_yaml.exists():
        with config_yaml.open("r", encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh)
        if isinstance(cfg, dict):
            data_section = cfg.get("data", {})
            if isinstance(data_section, dict):
                data_dir_str = data_section.get("data_dir", "")
                if data_dir_str:
                    candidate = Path(data_dir_str) / "models" / "cc.en.300.bin"
                    if candidate.is_file():
                        return candidate
    return None


def seed_corpus(tmp_dir: Path, corpus_name: str, seed_data_dir: Path) -> None:
    """Copy seed txt files into the temp data directory for a corpus.

    Args:
        tmp_dir: The temp directory from create_temp_data_dir().
        corpus_name: e.g. "knowledgebase" or "llmevals".
        seed_data_dir: Path to seed_data/<corpus_name>/txt/ containing .txt files.
    """
    target = tmp_dir / "data" / "input" / corpus_name / "txt"
    for txt_file in seed_data_dir.glob("*.txt"):
        shutil.copy2(txt_file, target / txt_file.name)


def wait_for_service(url: str, timeout: float = 30.0, interval: float = 1.0) -> bool:
    """Poll a URL until it returns 200 or timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            resp = httpx.get(url, timeout=2.0)
            if resp.status_code == 200:
                return True
        except (httpx.ConnectError, httpx.ReadTimeout):
            pass
        time.sleep(interval)
    return False


def _write_temp_config(port: int, data_dir: Path) -> Path:
    """Write a temporary config.yaml for the test service.

    Returns the path to the temp config file. Caller should clean up
    the parent temp directory.
    """
    config_data = {
        "service": {
            "host": "127.0.0.1",
            "port": port,
            "reload": False,
            "log_level": "WARNING",
        },
        "data": {
            "data_dir": str(data_dir),
        },
        "index": {
            "chunking": {"chunk_size": 500, "overlap": 0.3},
            "embeddings": {"model_name": "cc.en.300.bin", "dimension": 300},
            "storage": {"db_filename": "minirag.db"},
            "faiss": {"index_type": "IndexFlatIP", "nprobe": 1},
            "tantivy": {"language": "en", "stemming": True},
        },
        "search": {
            "hybrid": {"alpha": 0.5},
            "dense": {},
            "sparse": {},
            "reranking": {
                "enabled": False,
                "model_name": "cross-encoder/ms-marco-MiniLM-L12-v2",
                "candidate_multiplier": 3,
            },
        },
    }

    fd, tmp_path = tempfile.mkstemp(prefix="minirag_config_", suffix=".yaml")
    os.close(fd)
    config_path = Path(tmp_path)
    with config_path.open("w", encoding="utf-8") as fh:
        yaml.dump(config_data, fh, default_flow_style=False)
    return config_path


def start_service(port: int, data_dir: Path, config_env: dict[str, str] | None = None) -> subprocess.Popen:
    """Start the mini-rag service as a subprocess on a given port.

    Creates a temporary config.yaml with the given port and data_dir,
    then passes it via MINIRAG_CONFIG env var.

    Args:
        port: Port to run the service on.
        data_dir: Path to the data directory.
        config_env: Additional environment variables.

    Returns:
        The subprocess.Popen object.
    """
    config_path = _write_temp_config(port, data_dir)

    env = {**os.environ}
    if config_env:
        env.update(config_env)
    env["MINIRAG_CONFIG"] = str(config_path)

    proc = subprocess.Popen(
        ["uv", "run", "src/main.py"],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    return proc


def stop_service(proc: subprocess.Popen, base_url: str) -> None:
    """Stop the service by sending shutdown request, then terminate if needed."""
    with contextlib.suppress(httpx.ConnectError, httpx.ReadTimeout):
        httpx.post(f"{base_url}/v1/shutdown", timeout=5.0)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.terminate()
        proc.wait(timeout=5)


def ingest_corpus(base_url: str, corpus: str, data_dir: Path) -> None:
    """Ingest a corpus into the running test service via its API.

    Reads text files from data_dir/input/<corpus>/txt/ and sends them
    to POST /v1/corpus/<corpus>/index.
    """
    input_dir = data_dir / "input" / corpus / "txt"
    txt_files = sorted(input_dir.glob("*.txt"))
    if not txt_files:
        raise FileNotFoundError(f"No .txt files found in {input_dir}")

    with httpx.Client(base_url=base_url, timeout=30.0) as client:
        for txt_file in txt_files:
            text = txt_file.read_text(encoding="utf-8")
            if not text.strip():
                continue
            citation_key = txt_file.stem
            payload = {
                "document": text,
                "citation": {
                    "citation_key": citation_key,
                    "source_type": "text_file",
                    "common": {"title": txt_file.name},
                    "source_data": {},
                },
            }
            resp = client.post(f"/v1/corpus/{corpus}/index", json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"Failed to index {txt_file.name} into {corpus}: {resp.status_code} {resp.text}")


def is_model_allowed(model_id: str) -> bool:
    """Check if a model ID passes the allowed-model policy.

    Rejects very large models (32b, 70b, etc).
    Prefers gemma and qwen instruct/chat variants.
    """
    model_lower = model_id.lower()
    return all(pattern not in model_lower for pattern in REJECT_MODEL_PATTERNS)


def get_loaded_models() -> list[str]:
    """Get the list of currently loaded model IDs from LM Studio."""
    try:
        resp = httpx.get("http://127.0.0.1:1234/v1/models", timeout=5.0)
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            return [m["id"] for m in data if "id" in m]
    except (httpx.ConnectError, httpx.ReadTimeout):
        pass
    return []


def find_allowed_loaded_model() -> str | None:
    """Find an already-loaded model that passes the allowed-model policy."""
    for model_id in get_loaded_models():
        if is_model_allowed(model_id):
            return model_id
    return None


def lm_studio_available() -> bool:
    """Check if LM Studio API is reachable."""
    try:
        resp = httpx.get("http://127.0.0.1:1234/v1/models", timeout=2.0)
        return resp.status_code == 200
    except (httpx.ConnectError, httpx.ReadTimeout):
        return False


# ---------------------------------------------------------------------------
# LM Studio CLI wrappers (spec section 4.3)
# ---------------------------------------------------------------------------


def lms_cli_available() -> bool:
    """Check if the ``lms`` CLI binary is on PATH."""
    return shutil.which("lms") is not None


def lms_server_status() -> bool:
    """Return True if ``lms server status`` reports the server is running."""
    if not lms_cli_available():
        return False
    try:
        result = subprocess.run(
            ["lms", "server", "status"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def lms_server_start() -> bool:
    """Start the LM Studio server via ``lms server start``.

    Returns True if the command succeeds.
    """
    try:
        result = subprocess.run(
            ["lms", "server", "start"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def lms_list_loaded() -> list[str]:
    """Return model identifiers from ``lms ps``."""
    try:
        result = subprocess.run(
            ["lms", "ps"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return []
        # Parse lines that look like model identifiers (non-header, non-empty)
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        return [line for line in lines if not line.startswith(("─", "│", "Model", "="))]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def lms_unload_all() -> bool:
    """Unload all models via ``lms unload --all``."""
    try:
        result = subprocess.run(
            ["lms", "unload", "--all"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def lms_list_local_models() -> list[str]:
    """Return locally available model keys from ``lms ls``."""
    try:
        result = subprocess.run(
            ["lms", "ls"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return []
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        return [line for line in lines if not line.startswith(("─", "│", "Model", "="))]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def lms_load_model(model_key: str, identifier: str = "e2e-model") -> bool:
    """Load a model via ``lms load <key> --identifier <id> -y``.

    Does NOT auto-download. Returns True on success.
    """
    try:
        result = subprocess.run(
            ["lms", "load", model_key, "--identifier", identifier, "-y"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _pick_best_local_model(local_models: list[str]) -> str | None:
    """Pick the best local model per the allowed-model policy.

    Priority: qwen instruct/chat <=14B, gemma instruct/chat <=12B,
    then any other allowed model.
    """
    for pattern, _max_size in PREFERRED_MODEL_PATTERNS:
        for model in local_models:
            model_lower = model.lower()
            if pattern in model_lower and is_model_allowed(model):
                return model
    # Fallback: any allowed model
    for model in local_models:
        if is_model_allowed(model):
            return model
    return None


def ensure_allowed_model_loaded() -> str | None:
    """Ensure an allowed model is loaded in LM Studio.

    Follows the spec section 4.3 flow:
    1. Check if an allowed model is already loaded via API.
    2. If not, try CLI: unload all, pick best local model, load it.
    3. Poll API until the model appears.

    Returns the model ID on success, None on failure.
    """
    # Step 1: check API
    existing = find_allowed_loaded_model()
    if existing is not None:
        return existing

    # Step 2: try CLI
    if not lms_cli_available():
        return None

    if not lms_server_status():
        if not lms_server_start():
            return None
        time.sleep(3)

    lms_unload_all()

    local_models = lms_list_local_models()
    best = _pick_best_local_model(local_models)
    if best is None:
        return None

    if not lms_load_model(best):
        return None

    # Step 3: poll API
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        loaded = find_allowed_loaded_model()
        if loaded is not None:
            return loaded
        time.sleep(2)
    return None
