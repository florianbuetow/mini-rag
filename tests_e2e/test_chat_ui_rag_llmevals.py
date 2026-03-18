"""Layer B — Real-RAG browser tests: llmevals corpus.

12 scenarios (LE-01 through LE-12) from specifications2.md section 11.
Requires: mini-rag service on port 9191, LM Studio with allowed model,
llmevals corpus seeded and ingested.
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

CORPUS: str = "llmevals"
KB_CITATION_KEYS: list[str] = [
    "kb_intent_engineering",
    "kb_prompt_engineering",
    "kb_rag_basics",
    "kb_hybrid_search",
    "kb_chunking",
    "kb_citations",
    "kb_chat_persistence",
    "kb_export",
    "kb_corpora",
    "kb_models",
    "kb_streaming",
    "kb_no_results",
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


class TestLlmevalsRAG:
    """LE-01 through LE-12: llmevals corpus real-RAG scenarios."""

    def _setup(self, page) -> None:
        _skip_unless_ready()
        wait_for_selectors_loaded(page)
        select_corpus(page, CORPUS)
        create_new_chat(page)

    def test_le01_rouge_l(self, page) -> None:
        """LE-01: What does ROUGE-L recall measure?"""
        self._setup(page)
        text = send_message_and_wait(
            page,
            "What does ROUGE-L recall measure?",
            LLM_TIMEOUT,
        )
        assert text
        assert_has_keywords(text, ["longest", "common", "subsequence", "overlap", "reference", "rouge"])
        assert has_citation_evidence(text)
        assert_has_citation_keys(text, ["le_rouge_l"])
        assert_lacks_citation_keys(text, KB_CITATION_KEYS)

    def test_le02_precision_recall_at_k(self, page) -> None:
        """LE-02: precision@k vs recall@k."""
        self._setup(page)
        text = send_message_and_wait(
            page,
            "What is the difference between precision@k and recall@k?",
            LLM_TIMEOUT,
        )
        assert text
        assert_has_keywords(text, ["precision", "recall", "top", "relevance", "coverage"])
        assert has_citation_evidence(text)
        assert_has_citation_keys(text, ["le_precision_recall_at_k"])

    def test_le03_groundedness(self, page) -> None:
        """LE-03: What is groundedness in an LLM evaluation?"""
        self._setup(page)
        text = send_message_and_wait(
            page,
            "What is groundedness in an LLM evaluation?",
            LLM_TIMEOUT,
        )
        assert text
        assert_has_keywords(text, ["groundedness", "support", "evidence", "retrieved", "claims"])
        assert has_citation_evidence(text)
        assert_has_citation_keys(text, ["le_groundedness"])

    def test_le04_hallucination(self, page) -> None:
        """LE-04: How should we detect hallucinations in evals?"""
        self._setup(page)
        text = send_message_and_wait(
            page,
            "How should we detect hallucinations in evals?",
            LLM_TIMEOUT,
        )
        assert text
        assert_has_keywords(text, ["unsupported", "claims", "fabricated", "facts", "citations", "hallucination"])
        assert has_citation_evidence(text)
        assert_has_citation_keys(text, ["le_hallucination"])

    def test_le05_judge_models(self, page) -> None:
        """LE-05: What are the risks of using judge models?"""
        self._setup(page)
        text = send_message_and_wait(
            page,
            "What are the risks of using judge models?",
            LLM_TIMEOUT,
        )
        assert text
        assert_has_keywords(text, ["bias", "calibration", "judge", "model"])
        assert has_citation_evidence(text)
        assert_has_citation_keys(text, ["le_judge_models"])

    def test_le06_pairwise(self, page) -> None:
        """LE-06: When should we use pairwise evaluation?"""
        self._setup(page)
        text = send_message_and_wait(
            page,
            "When should we use pairwise evaluation?",
            LLM_TIMEOUT,
        )
        assert text
        assert_has_keywords(text, ["ranking", "comparing", "pairwise", "outputs"])
        assert has_citation_evidence(text)
        assert_has_citation_keys(text, ["le_pairwise"])

    def test_le07_dataset_design(self, page) -> None:
        """LE-07: How should we design an evaluation dataset?"""
        self._setup(page)
        text = send_message_and_wait(
            page,
            "How should we design an evaluation dataset?",
            LLM_TIMEOUT,
        )
        assert text
        assert_has_keywords(text, ["easy", "medium", "hard", "adversarial", "coverage", "dataset"])
        assert has_citation_evidence(text)
        assert_has_citation_keys(text, ["le_dataset_design"])

    def test_le08_latency(self, page) -> None:
        """LE-08: What latency numbers should an eval report include?"""
        self._setup(page)
        text = send_message_and_wait(
            page,
            "What latency numbers should an eval report include?",
            LLM_TIMEOUT,
        )
        assert text
        assert_has_keywords(text, ["retrieval", "generation", "latency", "time"])
        assert has_citation_evidence(text)
        assert_has_citation_keys(text, ["le_latency"])

    def test_le09_reproducibility(self, page) -> None:
        """LE-09: What makes an eval reproducible?"""
        self._setup(page)
        text = send_message_and_wait(
            page,
            "What makes an eval reproducible?",
            LLM_TIMEOUT,
        )
        assert text
        assert_has_keywords(text, ["seed", "version", "model", "corpus", "prompt", "reproducib"])
        assert has_citation_evidence(text)
        assert_has_citation_keys(text, ["le_reproducibility"])

    def test_le10_error_analysis(self, page) -> None:
        """LE-10: How should we categorize failures during error analysis?"""
        self._setup(page)
        text = send_message_and_wait(
            page,
            "How should we categorize failures during error analysis?",
            LLM_TIMEOUT,
        )
        assert text
        assert_has_keywords(text, ["retrieval", "grounding", "citation", "reasoning", "miss", "failure"])
        assert has_citation_evidence(text)
        assert_has_citation_keys(text, ["le_error_analysis"])

    def test_le11_thresholds(self, page) -> None:
        """LE-11: How should pass-fail thresholds be defined?"""
        self._setup(page)
        text = send_message_and_wait(
            page,
            "How should pass-fail thresholds be defined?",
            LLM_TIMEOUT,
        )
        assert text
        assert_has_keywords(text, ["explicit", "metric", "threshold", "specific"])
        assert has_citation_evidence(text)
        assert_has_citation_keys(text, ["le_thresholds"])

    def test_le12_reporting(self, page) -> None:
        """LE-12: What should be in an eval report for each scenario?"""
        self._setup(page)
        text = send_message_and_wait(
            page,
            "What should be in an eval report for each scenario?",
            LLM_TIMEOUT,
        )
        assert text
        assert_has_keywords(text, ["scenario", "prompt", "citations", "latency", "pass", "fail", "report"])
        assert has_citation_evidence(text)
        assert_has_citation_keys(text, ["le_reporting"])
