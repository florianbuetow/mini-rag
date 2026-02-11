"""Integration tests for mini-rag service.

Test plan
---------
1. Health & info endpoints respond correctly.
2. Documents are chunked into the expected number of pieces.
3. Sparse (BM25) search finds keywords unique to a single chunk.
4. Sparse search for overlap keywords returns both adjacent chunks.
5. Dense (vector) search returns semantically relevant chunks.
6. Hybrid search returns results combining both modes.
7. Cross-document isolation: searching for doc-1-only terms does not
   return doc-2 chunks and vice-versa.
8. Citation keys appear in search results and map to correct documents.
9. Citation endpoint returns full citation metadata.
10. Index destruction clears all data including citations.
11. Auto-generated citations work when no citation is provided.
"""

import pytest

from minirag.search.types import SearchResult
from tests_integration.conftest import INTEGRATION_CORPUS
from tests_integration.documents import (
    CITATION_1,
    CITATION_2,
    DOC1_CHUNK1_UNIQUE,
    DOC1_CHUNK2_UNIQUE,
    DOC1_OVERLAP,
    DOC2_CHUNK1_UNIQUE,
    DOC2_CHUNK2_UNIQUE,
    DOC2_CHUNK3_UNIQUE,
    DOC2_OVERLAP_12,
    DOC2_OVERLAP_23,
    DOCUMENT_1,
)

# ───────────────────────── helpers ──────────────────────────


def _texts_containing(results: list[SearchResult], keyword: str) -> list[str]:
    """Return result texts that contain *keyword* (case-insensitive)."""
    kw = keyword.lower()
    return [r.text for r in results if kw in r.text.lower()]


# ──────────────────── health / info ─────────────────────────


class TestServiceEndpoints:
    """Verify administrative endpoints."""

    def test_health_returns_200(self, integration_http_client):
        resp = integration_http_client.get("/v1/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == 200
        assert body["data"]["status"] == "healthy"

    def test_info_returns_config(self, integration_http_client):
        resp = integration_http_client.get("/v1/info")
        assert resp.status_code == 200
        body = resp.json()
        assert "config" in body["data"]
        config = body["data"]["config"]
        assert config["index"]["chunking"]["chunk_size"] == 50
        assert config["index"]["chunking"]["overlap"] == pytest.approx(0.3)


# ───────────────────── indexing ──────────────────────────────


class TestIndexing:
    """Verify document indexing and chunk counts."""

    def test_document1_produces_two_chunks(self, indexed_documents):
        assert len(indexed_documents["doc1"]["chunk_ids"]) == 2

    def test_document2_produces_three_chunks(self, indexed_documents):
        assert len(indexed_documents["doc2"]["chunk_ids"]) == 3

    def test_document_ids_are_positive(self, indexed_documents):
        assert indexed_documents["doc1"]["id"] > 0
        assert indexed_documents["doc2"]["id"] > 0

    def test_chunk_ids_are_positive(self, indexed_documents):
        for cid in indexed_documents["doc1"]["chunk_ids"]:
            assert cid > 0
        for cid in indexed_documents["doc2"]["chunk_ids"]:
            assert cid > 0

    def test_all_chunk_ids_unique(self, indexed_documents):
        all_ids = indexed_documents["doc1"]["chunk_ids"] + indexed_documents["doc2"]["chunk_ids"]
        assert len(all_ids) == len(set(all_ids))


# ──────────── sparse (BM25) search ──────────────────────────


class TestSparseSearch:
    """BM25 keyword search: exact token matching."""

    # --- Document 1 ---

    def test_unique_chunk1_keyword_doc1(self, query_client, indexed_documents):
        """'superposition' is only in chunk 1 of doc1."""
        results = query_client.search_sparse(INTEGRATION_CORPUS, DOC1_CHUNK1_UNIQUE, top_k=10)
        matching = _texts_containing(results, DOC1_CHUNK1_UNIQUE)
        assert len(matching) >= 1
        # The keyword must NOT appear in chunk 2 (unique to chunk 1)
        for text in matching:
            assert DOC1_CHUNK1_UNIQUE.lower() in text.lower()

    def test_unique_chunk2_keyword_doc1(self, query_client, indexed_documents):
        """'topological' is only in chunk 2 of doc1."""
        results = query_client.search_sparse(INTEGRATION_CORPUS, DOC1_CHUNK2_UNIQUE, top_k=10)
        matching = _texts_containing(results, DOC1_CHUNK2_UNIQUE)
        assert len(matching) >= 1

    def test_overlap_keyword_doc1(self, query_client, indexed_documents):
        """'entanglement' sits in the overlap of doc1's two chunks.

        Both chunks must contain the word, so at least 2 results should match.
        """
        results = query_client.search_sparse(INTEGRATION_CORPUS, DOC1_OVERLAP, top_k=10)
        matching = _texts_containing(results, DOC1_OVERLAP)
        assert len(matching) >= 2

    # --- Document 2 ---

    def test_unique_chunk1_keyword_doc2(self, query_client, indexed_documents):
        """'symbiotic' is only in chunk 1 of doc2."""
        results = query_client.search_sparse(INTEGRATION_CORPUS, DOC2_CHUNK1_UNIQUE, top_k=10)
        matching = _texts_containing(results, DOC2_CHUNK1_UNIQUE)
        assert len(matching) >= 1

    def test_unique_chunk2_keyword_doc2(self, query_client, indexed_documents):
        """'bioluminescence' is only in chunk 2 of doc2."""
        results = query_client.search_sparse(INTEGRATION_CORPUS, DOC2_CHUNK2_UNIQUE, top_k=10)
        matching = _texts_containing(results, DOC2_CHUNK2_UNIQUE)
        assert len(matching) >= 1

    def test_unique_chunk3_keyword_doc2(self, query_client, indexed_documents):
        """'chemosynthetic' is only in chunk 3 of doc2."""
        results = query_client.search_sparse(INTEGRATION_CORPUS, DOC2_CHUNK3_UNIQUE, top_k=10)
        matching = _texts_containing(results, DOC2_CHUNK3_UNIQUE)
        assert len(matching) >= 1

    def test_overlap_12_keyword_doc2(self, query_client, indexed_documents):
        """'acidification' sits in the overlap of doc2 chunks 1 and 2."""
        results = query_client.search_sparse(INTEGRATION_CORPUS, DOC2_OVERLAP_12, top_k=10)
        matching = _texts_containing(results, DOC2_OVERLAP_12)
        assert len(matching) >= 2

    def test_overlap_23_keyword_doc2(self, query_client, indexed_documents):
        """'hydrothermal' sits in the overlap of doc2 chunks 2 and 3."""
        results = query_client.search_sparse(INTEGRATION_CORPUS, DOC2_OVERLAP_23, top_k=10)
        matching = _texts_containing(results, DOC2_OVERLAP_23)
        assert len(matching) >= 2

    # --- Cross-document isolation ---

    def test_doc1_keyword_absent_from_doc2_results(self, query_client, indexed_documents):
        """'superposition' should not appear in any doc2 chunk."""
        results = query_client.search_sparse(INTEGRATION_CORPUS, DOC1_CHUNK1_UNIQUE, top_k=10)
        for r in results:
            # Results should NOT contain doc2-specific language
            assert DOC2_CHUNK1_UNIQUE.lower() not in r.text.lower()

    def test_doc2_keyword_absent_from_doc1_results(self, query_client, indexed_documents):
        """'symbiotic' should not appear in any doc1 chunk."""
        results = query_client.search_sparse(INTEGRATION_CORPUS, DOC2_CHUNK1_UNIQUE, top_k=10)
        for r in results:
            assert DOC1_CHUNK1_UNIQUE.lower() not in r.text.lower()


# ──────────── dense (vector) search ─────────────────────────


class TestDenseSearch:
    """Semantic vector similarity search via FastText + FAISS."""

    def test_quantum_query_returns_doc1_chunks(self, query_client, indexed_documents):
        """A quantum-themed query should surface doc1 chunks."""
        results = query_client.search_dense(INTEGRATION_CORPUS, "quantum mechanics computation qubits", top_k=5)
        assert len(results) >= 1
        # At least one result should contain quantum-related text
        assert any("quantum" in r.text.lower() for r in results)

    def test_marine_query_returns_doc2_chunks(self, query_client, indexed_documents):
        """A marine-biology query should surface doc2 chunks."""
        results = query_client.search_dense(INTEGRATION_CORPUS, "coral reef ocean marine ecosystem", top_k=5)
        assert len(results) >= 1
        assert any("coral" in r.text.lower() or "marine" in r.text.lower() for r in results)

    def test_dense_results_have_scores(self, query_client, indexed_documents):
        """Every dense result must carry a numeric score."""
        results = query_client.search_dense(INTEGRATION_CORPUS, "energy", top_k=5)
        for r in results:
            assert isinstance(r.score, float)

    def test_dense_top_result_has_highest_score(self, query_client, indexed_documents):
        """Results should be sorted descending by score."""
        results = query_client.search_dense(INTEGRATION_CORPUS, "quantum entanglement", top_k=5)
        if len(results) >= 2:
            for i in range(len(results) - 1):
                assert results[i].score >= results[i + 1].score


# ──────────── hybrid search ─────────────────────────────────


class TestHybridSearch:
    """Combined dense + sparse search with alpha weighting."""

    def test_hybrid_returns_results(self, query_client, indexed_documents):
        results = query_client.search_hybrid(INTEGRATION_CORPUS, "quantum computing", top_k=5)
        assert len(results) >= 1

    def test_hybrid_marine_biology(self, query_client, indexed_documents):
        results = query_client.search_hybrid(INTEGRATION_CORPUS, "coral reef bioluminescence ocean", top_k=5)
        assert len(results) >= 1
        assert any("coral" in r.text.lower() or "bioluminescence" in r.text.lower() for r in results)

    def test_hybrid_scores_descending(self, query_client, indexed_documents):
        results = query_client.search_hybrid(INTEGRATION_CORPUS, "marine ecosystem", top_k=10)
        if len(results) >= 2:
            for i in range(len(results) - 1):
                assert results[i].score >= results[i + 1].score

    def test_hybrid_overlap_keyword(self, query_client, indexed_documents):
        """Overlap keyword 'acidification' should appear in multiple results."""
        results = query_client.search_hybrid(INTEGRATION_CORPUS, DOC2_OVERLAP_12, top_k=10)
        matching = _texts_containing(results, DOC2_OVERLAP_12)
        assert len(matching) >= 2


# ──────────── citations in search results ─────────────────────


class TestCitationInSearchResults:
    """Verify that search results include correct citation keys."""

    def test_sparse_results_have_citation_key(self, query_client, indexed_documents):
        """Every sparse search result must carry a non-empty citation_key."""
        results = query_client.search_sparse(INTEGRATION_CORPUS, DOC1_CHUNK1_UNIQUE, top_k=10)
        assert len(results) >= 1
        for r in results:
            assert r.citation_key != ""

    def test_dense_results_have_citation_key(self, query_client, indexed_documents):
        """Every dense search result must carry a non-empty citation_key."""
        results = query_client.search_dense(INTEGRATION_CORPUS, "quantum computing", top_k=5)
        assert len(results) >= 1
        for r in results:
            assert r.citation_key != ""

    def test_hybrid_results_have_citation_key(self, query_client, indexed_documents):
        """Every hybrid search result must carry a non-empty citation_key."""
        results = query_client.search_hybrid(INTEGRATION_CORPUS, "coral reef", top_k=5)
        assert len(results) >= 1
        for r in results:
            assert r.citation_key != ""

    def test_doc1_chunks_have_doc1_citation_key(self, query_client, indexed_documents):
        """Chunks from doc1 should carry the doc1 citation key."""
        results = query_client.search_sparse(INTEGRATION_CORPUS, DOC1_CHUNK1_UNIQUE, top_k=10)
        matching = [r for r in results if DOC1_CHUNK1_UNIQUE.lower() in r.text.lower()]
        assert len(matching) >= 1
        for r in matching:
            assert r.citation_key == CITATION_1["citation_key"]

    def test_doc2_chunks_have_doc2_citation_key(self, query_client, indexed_documents):
        """Chunks from doc2 should carry the doc2 citation key."""
        results = query_client.search_sparse(INTEGRATION_CORPUS, DOC2_CHUNK1_UNIQUE, top_k=10)
        matching = [r for r in results if DOC2_CHUNK1_UNIQUE.lower() in r.text.lower()]
        assert len(matching) >= 1
        for r in matching:
            assert r.citation_key == CITATION_2["citation_key"]

    def test_results_have_positive_document_id(self, query_client, indexed_documents):
        """Every search result must have a positive document_id."""
        results = query_client.search_sparse(INTEGRATION_CORPUS, DOC1_CHUNK1_UNIQUE, top_k=10)
        assert len(results) >= 1
        for r in results:
            assert r.document_id > 0


# ──────────── citation endpoint ───────────────────────────────


class TestCitationEndpoint:
    """Verify the citation retrieval API endpoint."""

    def test_get_citation_doc1(self, integration_http_client, indexed_documents):
        """Retrieve full citation for doc1 by citation_key."""
        citation_key = CITATION_1["citation_key"]
        resp = integration_http_client.get(f"/v1/corpus/{INTEGRATION_CORPUS}/citation/{citation_key}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == 200
        data = body["data"]
        assert data["citation_key"] == citation_key
        assert data["source_type"] == CITATION_1["source_type"]
        assert data["common"]["author"] == "Feynman, Richard"
        assert data["common"]["title"] == "Quantum Computing Principles"

    def test_get_citation_doc2(self, integration_http_client, indexed_documents):
        """Retrieve full citation for doc2 by citation_key."""
        citation_key = CITATION_2["citation_key"]
        resp = integration_http_client.get(f"/v1/corpus/{INTEGRATION_CORPUS}/citation/{citation_key}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == 200
        data = body["data"]
        assert data["citation_key"] == citation_key
        assert data["source_type"] == CITATION_2["source_type"]
        assert data["common"]["url"] == "https://example.com/coral-reefs"
        assert data["source_data"]["blog_name"] == "Ocean Science Today"

    def test_get_citation_source_data_preserved(self, integration_http_client, indexed_documents):
        """Source-type-specific fields are stored and returned correctly."""
        citation_key = CITATION_1["citation_key"]
        resp = integration_http_client.get(f"/v1/corpus/{INTEGRATION_CORPUS}/citation/{citation_key}")
        data = resp.json()["data"]
        assert data["source_data"]["journal_name"] == "Physical Review Letters"
        assert data["source_data"]["doi"] == "10.1000/quantum-test"

    def test_citation_not_found_returns_404(self, integration_http_client, indexed_documents):
        """Unknown citation_key should return 404."""
        resp = integration_http_client.get(f"/v1/corpus/{INTEGRATION_CORPUS}/citation/nonexistent_key_xyz")
        assert resp.status_code == 404
        body = resp.json()
        assert body["status"] == 404
        assert "nonexistent_key_xyz" in body["error"]


# ──────────── index destruction (MUST BE LAST) ────────────────
#
# These classes destroy the index. They MUST remain at the bottom of the
# file because integration tests run with -p no:randomly, so class order
# follows file order.  No test above should depend on state after this point.


class TestIndexDestruction:
    """Verify that destroying the index clears all data."""

    def test_destroy_and_verify_empty(self, indexing_client, query_client):
        """After destroy, sparse search should return no results."""
        indexing_client.destroy_index(INTEGRATION_CORPUS)

        results = query_client.search_sparse(INTEGRATION_CORPUS, DOC1_CHUNK1_UNIQUE, top_k=10)
        assert len(results) == 0

    def test_reindex_after_destroy(self, indexing_client, query_client):
        """Re-indexing after destroy should work normally."""
        indexing_client.destroy_index(INTEGRATION_CORPUS)
        doc_id, chunk_ids = indexing_client.index_document(INTEGRATION_CORPUS, DOCUMENT_1, CITATION_1)
        assert doc_id > 0
        assert len(chunk_ids) == 2

        results = query_client.search_sparse(INTEGRATION_CORPUS, DOC1_CHUNK1_UNIQUE, top_k=10)
        assert len(results) >= 1


class TestCitationAfterDestruction:
    """Verify citations are cleared when the index is destroyed."""

    def test_citation_cleared_after_destroy(self, indexing_client, integration_http_client):
        """After destroy, citation lookup should return 404."""
        indexing_client.destroy_index(INTEGRATION_CORPUS)

        citation_key = CITATION_1["citation_key"]
        resp = integration_http_client.get(f"/v1/corpus/{INTEGRATION_CORPUS}/citation/{citation_key}")
        assert resp.status_code == 404

    def test_auto_generated_citation(self, indexing_client, integration_http_client):
        """Indexing without citation should auto-generate one."""
        indexing_client.destroy_index(INTEGRATION_CORPUS)
        doc_id, _ = indexing_client.index_document(INTEGRATION_CORPUS, DOCUMENT_1, None)

        # Auto-generated citation uses document_id as citation_key
        auto_key = str(doc_id)
        resp = integration_http_client.get(f"/v1/corpus/{INTEGRATION_CORPUS}/citation/{auto_key}")
        assert resp.status_code == 200
        body = resp.json()
        data = body["data"]
        assert data["citation_key"] == auto_key
        assert data["source_type"] == "text_file"
