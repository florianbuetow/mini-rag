"""End-to-end lifecycle test: convert, ingest, evaluate, assert quality, delete.

This test exercises the full pipeline as a user would:
1. Start the service (handled by conftest fixture).
2. Convert markdown to text via scripts/md2txt.py.
3. Verify search returns empty results before indexing.
4. Shell out to scripts/ingest.py to ingest the test corpus.
5. Verify search returns results after indexing.
6. Verify citation endpoint returns data.
7. Shell out to scripts/evaluate.py to run evaluation.
8. Read the JSON report and assert average ROUGE-L thresholds per mode.
9. Delete the test corpus index.
10. Verify search returns empty results after deletion.
11. Verify citation endpoint returns 404 after deletion.
"""

import json
import subprocess
import time

import httpx

from minirag.clients.query import QueryClient
from minirag.search.types import SearchResult
from tests_e2e.conftest import E2EEnv

SEARCH_MODES = ["sparse", "dense", "hybrid"]
_E2E_COMMAND_TIMEOUT_S = 30

# Conservative initial thresholds for average ROUGE-L recall per mode.
# Tune upward once baseline scores are established.
ROUGE_L_THRESHOLDS = {
    "sparse": 0.15,
    "dense": 0.15,
    "hybrid": 0.15,
}


def _search_all_modes_with_timing(
    client: QueryClient, corpus: str, query: str, top_k: int = 5
) -> tuple[dict[str, list[SearchResult]], dict[str, float]]:
    """Run all search modes and capture per-mode latency in milliseconds."""
    timings_ms: dict[str, float] = {}

    started = time.perf_counter()
    sparse_results = client.search_sparse(corpus=corpus, query=query, top_k=top_k)
    timings_ms["sparse"] = (time.perf_counter() - started) * 1000.0

    started = time.perf_counter()
    dense_results = client.search_dense(corpus=corpus, query=query, top_k=top_k)
    timings_ms["dense"] = (time.perf_counter() - started) * 1000.0

    started = time.perf_counter()
    hybrid_results = client.search_hybrid(corpus=corpus, query=query, top_k=top_k)
    timings_ms["hybrid"] = (time.perf_counter() - started) * 1000.0

    return (
        {
            "sparse": sparse_results,
            "dense": dense_results,
            "hybrid": hybrid_results,
        },
        timings_ms,
    )


def _record_query_timings(
    e2e_env: E2EEnv,
    *,
    phase: str,
    query: str,
    top_k: int,
    timings_ms: dict[str, float],
) -> None:
    """Append per-mode query timing metrics to the mode-specific E2E report."""
    with e2e_env.timings_report_path.open("a", encoding="utf-8") as file_handle:
        for mode in SEARCH_MODES:
            entry = {
                "phase": phase,
                "mode": mode,
                "query": query,
                "top_k": top_k,
                "duration_ms": round(timings_ms[mode], 3),
                "reranking_enabled": e2e_env.reranking_enabled,
            }
            file_handle.write(f"{json.dumps(entry)}\n")


def _load_recorded_timings(e2e_env: E2EEnv) -> dict[str, dict[str, float]]:
    """Load recorded timing entries as phase -> mode -> duration_ms."""
    phase_to_mode: dict[str, dict[str, float]] = {}
    with e2e_env.timings_report_path.open("r", encoding="utf-8") as file_handle:
        for line in file_handle:
            loaded: object = json.loads(line)
            if not isinstance(loaded, dict):
                continue

            phase_obj = loaded.get("phase")
            mode_obj = loaded.get("mode")
            duration_obj = loaded.get("duration_ms")
            if not isinstance(phase_obj, str):
                continue
            if not isinstance(mode_obj, str):
                continue
            if not isinstance(duration_obj, int | float):
                continue
            if mode_obj not in SEARCH_MODES:
                continue

            if phase_obj not in phase_to_mode:
                phase_to_mode[phase_obj] = {}
            phase_to_mode[phase_obj][mode_obj] = float(duration_obj)

    return phase_to_mode


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
            timeout=_E2E_COMMAND_TIMEOUT_S,
        )
        assert result.returncode == 0, f"md2txt failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"

        # Verify txt files were created
        txt_dir = e2e_env.data_dir / "input" / e2e_env.corpus / "txt"
        txt_files = list(txt_dir.glob("*.txt"))
        assert len(txt_files) > 0, f"No txt files created in {txt_dir}"

    def test_03_search_before_ingest_returns_empty(self, e2e_env: E2EEnv) -> None:
        """Querying before indexing should return no results in all modes."""
        client = QueryClient(host=e2e_env.host, port=e2e_env.port, http_client=None)
        query = "quantum computing"
        top_k = 5
        results, timings_ms = _search_all_modes_with_timing(client, e2e_env.corpus, query, top_k=top_k)
        _record_query_timings(
            e2e_env,
            phase="before_ingest",
            query=query,
            top_k=top_k,
            timings_ms=timings_ms,
        )

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
            timeout=_E2E_COMMAND_TIMEOUT_S,
        )
        assert result.returncode == 0, f"Ingest failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"

    def test_05_search_after_ingest_returns_results(self, e2e_env: E2EEnv) -> None:
        """Querying after indexing should return results with citation fields in all modes."""
        client = QueryClient(host=e2e_env.host, port=e2e_env.port, http_client=None)
        query = "quantum computing"
        top_k = 5
        results, timings_ms = _search_all_modes_with_timing(client, e2e_env.corpus, query, top_k=top_k)
        _record_query_timings(
            e2e_env,
            phase="after_ingest",
            query=query,
            top_k=top_k,
            timings_ms=timings_ms,
        )

        for mode in SEARCH_MODES:
            assert len(results[mode]) > 0, f"{mode} search returned no results after indexing"
            for result in results[mode]:
                assert result.document_id > 0, f"{mode} result missing document_id"
                assert result.citation_key.strip() != "", f"{mode} result missing citation_key"

    def test_06_citation_endpoint_returns_data(self, e2e_env: E2EEnv) -> None:
        """Citation endpoint should return data for a known citation_key after indexing."""
        client = QueryClient(host=e2e_env.host, port=e2e_env.port, http_client=None)
        results = client.search_hybrid(corpus=e2e_env.corpus, query="quantum computing", top_k=1)
        assert len(results) > 0, "Need at least one result to test citation endpoint"

        citation_key = results[0].citation_key
        resp = httpx.get(
            f"{e2e_env.base_url}/v1/corpus/{e2e_env.corpus}/citation/{citation_key}",
            timeout=5.0,
        )
        assert resp.status_code == 200, f"Citation endpoint failed: {resp.text}"
        data = resp.json()["data"]
        assert data["citation_key"] == citation_key
        assert "source_type" in data

    def test_07_evaluate_test_corpus(self, e2e_env: E2EEnv) -> None:
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
            timeout=_E2E_COMMAND_TIMEOUT_S,
        )
        assert result.returncode == 0, f"Evaluate failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"

        report_path = e2e_env.project_root / "reports" / e2e_env.corpus / "evaluation.json"
        assert report_path.exists(), f"Evaluation report not found at {report_path}"

    def test_08_quality_thresholds(self, e2e_env: E2EEnv) -> None:
        """Assert average ROUGE-L recall per mode meets thresholds."""
        report_path = e2e_env.project_root / "reports" / e2e_env.corpus / "evaluation.json"
        with report_path.open("r", encoding="utf-8") as fh:
            report = json.load(fh)

        assert "modes" in report, "Report missing 'modes' key"

        for mode, threshold in ROUGE_L_THRESHOLDS.items():
            assert mode in report["modes"], f"Report missing mode '{mode}'"
            avg_score = report["modes"][mode]["avg_rouge_l_recall"]
            assert avg_score >= threshold, f"{mode} avg ROUGE-L recall {avg_score:.4f} below threshold {threshold:.4f}"

        timings_by_phase = _load_recorded_timings(e2e_env)
        after_ingest_timings = timings_by_phase.get("after_ingest", {})

        # Print combined quality + timing summary for visibility in test output
        print()
        print(f"{'Mode':<10} {'Avg ROUGE-L':>12} {'Threshold':>12} {'Status':>8} {'Time (ms)':>10}")
        print("-" * 60)
        for mode in SEARCH_MODES:
            avg = report["modes"][mode]["avg_rouge_l_recall"]
            thr = ROUGE_L_THRESHOLDS[mode]
            status = "PASS" if avg >= thr else "FAIL"
            timing_ms = after_ingest_timings.get(mode, float("nan"))
            print(f"{mode:<10} {avg:>12.4f} {thr:>12.4f} {status:>8} {timing_ms:>10.3f}")
        print()

    def test_09_delete_index(self, e2e_env: E2EEnv) -> None:
        """Delete the test corpus index."""
        resp = httpx.delete(
            f"{e2e_env.base_url}/v1/corpus/{e2e_env.corpus}/index",
            timeout=30.0,
        )
        assert resp.status_code == 200

    def test_10_search_after_delete_returns_empty(self, e2e_env: E2EEnv) -> None:
        """Querying after deletion should return no results in all modes."""
        client = QueryClient(host=e2e_env.host, port=e2e_env.port, http_client=None)
        query = "quantum computing"
        top_k = 5
        results, timings_ms = _search_all_modes_with_timing(client, e2e_env.corpus, query, top_k=top_k)
        _record_query_timings(
            e2e_env,
            phase="after_delete",
            query=query,
            top_k=top_k,
            timings_ms=timings_ms,
        )

        for mode in SEARCH_MODES:
            assert len(results[mode]) == 0, f"{mode} search returned results after index deletion"

    def test_11_citation_returns_404_after_delete(self, e2e_env: E2EEnv) -> None:
        """Citation endpoint should return 404 after index deletion."""
        resp = httpx.get(
            f"{e2e_env.base_url}/v1/corpus/{e2e_env.corpus}/citation/nonexistent",
            timeout=5.0,
        )
        assert resp.status_code == 404
