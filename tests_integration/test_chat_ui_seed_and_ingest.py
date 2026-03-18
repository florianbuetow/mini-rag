"""Layer C — Integration tests: Seed corpora and ingest.

Tests 1-4 from specifications2.md section 7:
1. Seed knowledgebase and llmevals into an isolated temp data dir.
2. Ingest knowledgebase successfully.
3. Ingest llmevals successfully.
4. GET /v1/corpora returns exactly ["knowledgebase", "llmevals"] in sorted order.
"""

import shutil
from pathlib import Path

import httpx
import pytest

from tests_integration.helpers_runtime import (
    create_temp_data_dir,
    find_free_port,
    ingest_corpus,
    seed_corpus,
    start_service,
    stop_service,
    wait_for_service,
)

PROJECT_ROOT: Path = Path(__file__).parent.parent
SEED_DATA_DIR: Path = PROJECT_ROOT / "tests_e2e" / "seed_data"


pytestmark = [
    pytest.mark.integration,
    pytest.mark.timeout(120),
]


@pytest.fixture(scope="module")
def seeded_service():
    """Start a service with seeded and ingested knowledgebase and llmevals.

    Yields (base_url, tmp_dir).
    """
    tmp_dir = create_temp_data_dir()
    data_dir = tmp_dir / "data"

    # Seed both corpora
    seed_corpus(tmp_dir, "knowledgebase", SEED_DATA_DIR / "knowledgebase" / "txt")
    seed_corpus(tmp_dir, "llmevals", SEED_DATA_DIR / "llmevals" / "txt")

    port = find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    proc = start_service(port, data_dir)

    ready = wait_for_service(f"{base_url}/v1/health", timeout=30.0)
    if not ready:
        stop_service(proc, base_url)
        shutil.rmtree(tmp_dir, ignore_errors=True)
        pytest.fail(f"Service did not start on port {port}")

    # Ingest both corpora
    ingest_corpus(base_url, "knowledgebase", data_dir)
    ingest_corpus(base_url, "llmevals", data_dir)

    yield base_url, tmp_dir

    stop_service(proc, base_url)
    shutil.rmtree(tmp_dir, ignore_errors=True)


class TestSeedCorpora:
    """Tests 1: Seed files are placed correctly."""

    def test_seed_files_exist(self, seeded_service) -> None:
        _, tmp_dir = seeded_service
        kb_dir = tmp_dir / "data" / "input" / "knowledgebase" / "txt"
        le_dir = tmp_dir / "data" / "input" / "llmevals" / "txt"

        kb_files = list(kb_dir.glob("*.txt"))
        le_files = list(le_dir.glob("*.txt"))

        assert len(kb_files) >= 12, f"Expected >= 12 knowledgebase files, got {len(kb_files)}"
        assert len(le_files) >= 12, f"Expected >= 12 llmevals files, got {len(le_files)}"


class TestIngestion:
    """Tests 2-3: Ingestion succeeds for both corpora."""

    def test_knowledgebase_ingested(self, seeded_service) -> None:
        """Verify knowledgebase corpus has storage on disk after ingestion."""
        _, tmp_dir = seeded_service
        storage_dir = tmp_dir / "data" / "storage" / "knowledgebase"
        assert storage_dir.is_dir(), f"knowledgebase storage dir not found: {storage_dir}"

    def test_llmevals_ingested(self, seeded_service) -> None:
        """Verify llmevals corpus has storage on disk after ingestion."""
        _, tmp_dir = seeded_service
        storage_dir = tmp_dir / "data" / "storage" / "llmevals"
        assert storage_dir.is_dir(), f"llmevals storage dir not found: {storage_dir}"


class TestCorporaEndpoint:
    """Test 4: GET /v1/corpora returns both corpora sorted."""

    def test_corpora_returns_sorted_list(self, seeded_service) -> None:
        base_url, _ = seeded_service
        resp = httpx.get(f"{base_url}/v1/corpora", timeout=5.0)
        assert resp.status_code == 200
        data = resp.json()
        corpora = data.get("data", {}).get("corpora", [])
        assert corpora == sorted(corpora), f"Corpora not sorted: {corpora}"
        assert "knowledgebase" in corpora, f"knowledgebase not in corpora: {corpora}"
        assert "llmevals" in corpora, f"llmevals not in corpora: {corpora}"
