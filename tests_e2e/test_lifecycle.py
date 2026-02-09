"""End-to-end lifecycle test: convert, ingest, evaluate, assert quality, delete.

This test exercises the full pipeline as a user would:
1. Start the service (handled by conftest fixture).
2. Convert markdown to text via scripts/md2txt.py.
3. Verify search returns empty results before indexing.
4. Shell out to scripts/ingest.py to ingest the test corpus.
5. Verify search returns results after indexing.
6. Shell out to scripts/evaluate.py to run evaluation.
7. Read the JSON report and assert average ROUGE-L thresholds per mode.
8. Delete the test corpus index.
9. Verify search returns empty results after deletion.
"""

import json
import subprocess

import httpx

from minirag.clients.query import QueryClient
from minirag.search.types import SearchResult
from tests_e2e.conftest import E2EEnv

SEARCH_MODES = ["sparse", "dense", "hybrid"]

# Conservative initial thresholds for average ROUGE-L recall per mode.
# Tune upward once baseline scores are established.
ROUGE_L_THRESHOLDS = {
    "sparse": 0.15,
    "dense": 0.15,
    "hybrid": 0.15,
}


def _search_all_modes(client: QueryClient, corpus: str, query: str, top_k: int = 5) -> dict[str, list[SearchResult]]:
    """Run search in all modes and return results keyed by mode."""
    return {
        "sparse": client.search_sparse(corpus=corpus, query=query, top_k=top_k),
        "dense": client.search_dense(corpus=corpus, query=query, top_k=top_k),
        "hybrid": client.search_hybrid(corpus=corpus, query=query, top_k=top_k),
    }


class TestLifecycle:
    """Ordered lifecycle tests — run with -p no:randomly to preserve order."""

    def test_01_health_check(self, e2e_env: E2EEnv) -> None:
        """Service should be healthy."""
        resp = httpx.get(f"{e2e_env.base_url}/v1/health", timeout=5.0)
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["status"] == "healthy"

    def test_02_convert_md_to_txt(self, e2e_env: E2EEnv) -> None:
        """Convert markdown to text via scripts/md2txt.py."""
        result = subprocess.run(
            [
                "uv",
                "run",
                "scripts/md2txt.py",
                "--config",
                str(e2e_env.config_path),
            ],
            cwd=str(e2e_env.project_root),
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, f"md2txt failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"

        # Verify txt files were created
        txt_dir = e2e_env.data_dir / "input" / e2e_env.corpus / "txt"
        txt_files = list(txt_dir.glob("*.txt"))
        assert len(txt_files) > 0, f"No txt files created in {txt_dir}"

    def test_03_search_before_ingest_returns_empty(self, e2e_env: E2EEnv) -> None:
        """Querying before indexing should return no results in all modes."""
        client = QueryClient(host=e2e_env.host, port=e2e_env.port, http_client=None)
        results = _search_all_modes(client, e2e_env.corpus, "quantum computing")

        for mode in SEARCH_MODES:
            assert len(results[mode]) == 0, f"{mode} search returned results before indexing"

    def test_04_ingest_test_corpus(self, e2e_env: E2EEnv) -> None:
        """Ingest the test corpus via scripts/ingest.py."""
        result = subprocess.run(
            [
                "uv",
                "run",
                "scripts/ingest.py",
                "--corpus",
                e2e_env.corpus,
                "--config",
                str(e2e_env.config_path),
            ],
            cwd=str(e2e_env.project_root),
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, f"Ingest failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"

    def test_05_search_after_ingest_returns_results(self, e2e_env: E2EEnv) -> None:
        """Querying after indexing should return results in all modes."""
        client = QueryClient(host=e2e_env.host, port=e2e_env.port, http_client=None)
        results = _search_all_modes(client, e2e_env.corpus, "quantum computing")

        for mode in SEARCH_MODES:
            assert len(results[mode]) > 0, f"{mode} search returned no results after indexing"

    def test_06_evaluate_test_corpus(self, e2e_env: E2EEnv) -> None:
        """Run evaluation via scripts/evaluate.py."""
        result = subprocess.run(
            [
                "uv",
                "run",
                "scripts/evaluate.py",
                "--corpus",
                e2e_env.corpus,
                "--config",
                str(e2e_env.config_path),
            ],
            cwd=str(e2e_env.project_root),
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert result.returncode == 0, f"Evaluate failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"

        report_path = e2e_env.project_root / "reports" / e2e_env.corpus / "evaluation.json"
        assert report_path.exists(), f"Evaluation report not found at {report_path}"

    def test_07_quality_thresholds(self, e2e_env: E2EEnv) -> None:
        """Assert average ROUGE-L recall per mode meets thresholds."""
        report_path = e2e_env.project_root / "reports" / e2e_env.corpus / "evaluation.json"
        with report_path.open("r", encoding="utf-8") as fh:
            report = json.load(fh)

        assert "modes" in report, "Report missing 'modes' key"

        for mode, threshold in ROUGE_L_THRESHOLDS.items():
            assert mode in report["modes"], f"Report missing mode '{mode}'"
            avg_score = report["modes"][mode]["avg_rouge_l_recall"]
            assert avg_score >= threshold, f"{mode} avg ROUGE-L recall {avg_score:.4f} below threshold {threshold:.4f}"

        # Print summary for visibility in test output
        print()
        print(f"{'Mode':<10} {'Avg ROUGE-L':>12} {'Threshold':>12} {'Status':>8}")
        print("-" * 44)
        for mode in SEARCH_MODES:
            avg = report["modes"][mode]["avg_rouge_l_recall"]
            thr = ROUGE_L_THRESHOLDS[mode]
            status = "PASS" if avg >= thr else "FAIL"
            print(f"{mode:<10} {avg:>12.4f} {thr:>12.4f} {status:>8}")
        print()

    def test_08_delete_index(self, e2e_env: E2EEnv) -> None:
        """Delete the test corpus index."""
        resp = httpx.delete(
            f"{e2e_env.base_url}/v1/corpus/{e2e_env.corpus}/index",
            timeout=30.0,
        )
        assert resp.status_code == 200

    def test_09_search_after_delete_returns_empty(self, e2e_env: E2EEnv) -> None:
        """Querying after deletion should return no results in all modes."""
        client = QueryClient(host=e2e_env.host, port=e2e_env.port, http_client=None)
        results = _search_all_modes(client, e2e_env.corpus, "quantum computing")

        for mode in SEARCH_MODES:
            assert len(results[mode]) == 0, f"{mode} search returned results after index deletion"
