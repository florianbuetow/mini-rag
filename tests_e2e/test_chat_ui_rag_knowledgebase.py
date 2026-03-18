"""Layer B — Real-RAG browser tests: knowledgebase corpus.

12 scenarios (KB-01 through KB-12) from specifications2.md section 10.
Requires: mini-rag service on port 9191, LM Studio with allowed model,
knowledgebase corpus seeded and ingested.
"""

import pytest

from tests_e2e.helpers_chat_ui import (
    LLM_TIMEOUT,
    assert_has_citation_keys,
    assert_has_keywords,
    assert_lacks_citation_keys,
    corpus_available,
    create_new_chat,
    has_citation_evidence,
    lm_studio_available,
    select_corpus,
    send_message_and_wait,
    service_available,
    wait_for_selectors_loaded,
)

CORPUS: str = "knowledgebase"
LE_CITATION_KEYS: list[str] = [
    "le_rouge_l",
    "le_precision_recall_at_k",
    "le_groundedness",
    "le_hallucination",
    "le_judge_models",
    "le_pairwise",
    "le_dataset_design",
    "le_latency",
    "le_reproducibility",
    "le_error_analysis",
    "le_thresholds",
    "le_reporting",
]


def _skip_unless_ready() -> None:
    if not service_available():
        pytest.skip("mini-rag service not running on port 9191")
    if not lm_studio_available():
        pytest.skip("LM Studio not running on port 1234")
    if not corpus_available(CORPUS):
        pytest.skip(f"corpus '{CORPUS}' not available")


pytestmark = [
    pytest.mark.e2e,
    pytest.mark.rag,
    pytest.mark.timeout(240),
]


class TestKnowledgebaseRAG:
    """KB-01 through KB-12: knowledgebase corpus real-RAG scenarios."""

    def _setup(self, page) -> None:
        _skip_unless_ready()
        wait_for_selectors_loaded(page)
        select_corpus(page, CORPUS)
        create_new_chat(page)

    def test_kb01_intent_engineering(self, page) -> None:
        """KB-01: What is intent engineering?"""
        self._setup(page)
        text = send_message_and_wait(page, "What is intent engineering?", LLM_TIMEOUT)
        assert text, "Response should not be empty"
        assert_has_keywords(text, ["intent", "engineering", "goals", "constraints", "tools", "evaluation"])
        assert has_citation_evidence(text), f"Expected citation evidence in: {text[:300]}"
        assert_has_citation_keys(text, ["kb_intent_engineering"])
        assert_lacks_citation_keys(text, LE_CITATION_KEYS)

    def test_kb02_intent_vs_prompt_engineering(self, page) -> None:
        """KB-02: How is intent engineering different from prompt engineering?"""
        self._setup(page)
        text = send_message_and_wait(
            page,
            "How is intent engineering different from prompt engineering?",
            LLM_TIMEOUT,
        )
        assert text, "Response should not be empty"
        assert_has_keywords(text, ["intent", "prompt", "broader", "constraints", "tooling", "framing"])
        assert has_citation_evidence(text), f"Expected citation evidence in: {text[:300]}"
        assert_has_citation_keys(text, ["kb_intent_engineering", "kb_prompt_engineering"])

    def test_kb03_rag_basics(self, page) -> None:
        """KB-03: What is retrieval augmented generation?"""
        self._setup(page)
        text = send_message_and_wait(
            page,
            "What is retrieval augmented generation?",
            LLM_TIMEOUT,
        )
        assert text
        assert_has_keywords(text, ["retrieval", "generation", "retrieve", "ground", "source"])
        assert has_citation_evidence(text)
        assert_has_citation_keys(text, ["kb_rag_basics"])

    def test_kb04_hybrid_search(self, page) -> None:
        """KB-04: Why use hybrid search instead of only dense search?"""
        self._setup(page)
        text = send_message_and_wait(
            page,
            "Why use hybrid search instead of only dense search?",
            LLM_TIMEOUT,
        )
        assert text
        assert_has_keywords(text, ["dense", "sparse", "hybrid", "relevance", "rerank"])
        assert has_citation_evidence(text)
        assert_has_citation_keys(text, ["kb_hybrid_search"])

    def test_kb05_chunking(self, page) -> None:
        """KB-05: How do chunk size and overlap affect retrieval?"""
        self._setup(page)
        text = send_message_and_wait(
            page,
            "How do chunk size and overlap affect retrieval?",
            LLM_TIMEOUT,
        )
        assert text
        assert_has_keywords(text, ["chunk", "overlap", "recall", "precision", "duplication"])
        assert has_citation_evidence(text)
        assert_has_citation_keys(text, ["kb_chunking"])

    def test_kb06_citations(self, page) -> None:
        """KB-06: How should grounded answers show citations?"""
        self._setup(page)
        text = send_message_and_wait(
            page,
            "How should grounded answers show citations?",
            LLM_TIMEOUT,
        )
        assert text
        assert_has_keywords(text, ["citation", "bracket", "source", "reference", "grounded"])
        assert has_citation_evidence(text)
        assert_has_citation_keys(text, ["kb_citations"])

    def test_kb07_chat_persistence(self, page) -> None:
        """KB-07: What fields are stored when a chat is persisted?"""
        self._setup(page)
        text = send_message_and_wait(
            page,
            "What fields are stored when a chat is persisted?",
            LLM_TIMEOUT,
        )
        assert text
        assert_has_keywords(text, ["id", "name", "model", "corpus", "messages", "created_at", "updated_at"])
        assert has_citation_evidence(text)
        assert_has_citation_keys(text, ["kb_chat_persistence"])

    def test_kb08_export_difference(self, page) -> None:
        """KB-08: What is the difference between Markdown export and JSON export?"""
        self._setup(page)
        text = send_message_and_wait(
            page,
            "What is the difference between Markdown export and JSON export?",
            LLM_TIMEOUT,
        )
        assert text
        assert_has_keywords(text, ["markdown", "json", "readable", "full", "object", "export"])
        assert has_citation_evidence(text)
        assert_has_citation_keys(text, ["kb_export"])

    def test_kb09_corpora_switching(self, page) -> None:
        """KB-09: How are corpora listed and switched in the chat UI?"""
        self._setup(page)
        text = send_message_and_wait(
            page,
            "How are corpora listed and switched in the chat UI?",
            LLM_TIMEOUT,
        )
        assert text
        assert_has_keywords(text, ["alphabetical", "corpora", "switch", "turn"])
        assert has_citation_evidence(text)
        assert_has_citation_keys(text, ["kb_corpora"])

    def test_kb10_preferred_models(self, page) -> None:
        """KB-10: Which local models should we prefer for e2e testing?"""
        self._setup(page)
        text = send_message_and_wait(
            page,
            "Which local models should we prefer for e2e testing?",
            LLM_TIMEOUT,
        )
        assert text
        assert_has_keywords(text, ["gemma", "qwen", "local", "model", "instruct"])
        assert has_citation_evidence(text)
        assert_has_citation_keys(text, ["kb_models"])

    def test_kb11_multi_turn_sse(self, page) -> None:
        """KB-11: Multi-turn — ask about SSE, then follow up."""
        self._setup(page)
        text1 = send_message_and_wait(
            page,
            "What is SSE in this app?",
            LLM_TIMEOUT,
        )
        assert text1
        assert_has_keywords(text1, ["stream", "event", "sse", "incremental"])

        text2 = send_message_and_wait(
            page,
            "Why should duplicate sends be blocked?",
            LLM_TIMEOUT,
        )
        assert text2
        assert_has_keywords(text2, ["streaming", "disabled", "duplicate", "send"])
        assert has_citation_evidence(text2)
        assert_has_citation_keys(text2, ["kb_streaming"])

    def test_kb12_out_of_scope(self, page) -> None:
        """KB-12: Out-of-scope question — should not hallucinate citations."""
        self._setup(page)
        text = send_message_and_wait(
            page,
            "Who won the 1998 World Cup?",
            LLM_TIMEOUT,
        )
        assert text
        # Should not cite any kb_ documents for an out-of-scope question
        assert_lacks_citation_keys(
            text,
            [
                "kb_intent_engineering",
                "kb_prompt_engineering",
                "kb_rag_basics",
                "kb_hybrid_search",
                "kb_chunking",
                "kb_citations",
            ],
        )
