"""Evaluate retrieval quality for a corpus using ROUGE-L recall."""

import argparse
import json
import logging
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from minirag.clients.query import QueryClient
from minirag.config import Config

logger = logging.getLogger(__name__)

SEARCH_MODES = ["sparse", "dense", "hybrid"]
TOP_K = 5


def configure_logging() -> None:
    """Configure script logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Evaluate retrieval quality for a mini-rag corpus")
    parser.add_argument("--corpus", required=True, help="Name of the corpus to evaluate")
    parser.add_argument("--config", default=None, help="Path to config file (default: config.yaml in project root)")
    return parser.parse_args()


def load_qa_pairs(evals_path: Path) -> list[dict[str, str]]:
    """Load Q&A pairs from the evaluation JSON file.

    Raises:
        FileNotFoundError: If the evaluation file does not exist.
        ValueError: If the file format is invalid or contains no Q&A pairs.
    """
    if not evals_path.exists():
        raise FileNotFoundError(f"evaluation file not found: {evals_path}")

    with evals_path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)

    if not isinstance(raw, dict) or "qa_pairs" not in raw:
        raise ValueError(f'invalid evaluation file format: expected {{"qa_pairs": [...]}} in {evals_path}')

    qa_pairs = raw["qa_pairs"]
    if not isinstance(qa_pairs, list) or len(qa_pairs) == 0:
        raise ValueError(f"evaluation file contains no Q&A pairs: {evals_path}")

    for i, pair in enumerate(qa_pairs):
        if not isinstance(pair, dict) or "question" not in pair or "answer" not in pair:
            raise ValueError(f'invalid Q&A pair at index {i}: expected {{"question": ..., "answer": ...}}')

    return qa_pairs


def _tokenize(text: str, *, lowercase: bool) -> list[str]:
    normalized = text.lower() if lowercase else text
    return [token for token in re.split(r"\s+", normalized.strip()) if token]


def _lcs_length(tokens_a: list[str], tokens_b: list[str]) -> int:
    if not tokens_a or not tokens_b:
        return 0

    prev = [0] * (len(tokens_b) + 1)
    curr = [0] * (len(tokens_b) + 1)

    for token_a in tokens_a:
        for j, token_b in enumerate(tokens_b, start=1):
            if token_a == token_b:
                curr[j] = prev[j - 1] + 1
            else:
                curr[j] = curr[j - 1] if curr[j - 1] >= prev[j] else prev[j]
        prev, curr = curr, prev
        curr[:] = [0] * len(curr)

    return prev[-1]


def _rouge_l_recall(target: str, prediction: str, *, lowercase: bool) -> float:
    target_tokens = _tokenize(target, lowercase=lowercase)
    prediction_tokens = _tokenize(prediction, lowercase=lowercase)
    if not target_tokens:
        return 0.0
    lcs = _lcs_length(target_tokens, prediction_tokens)
    return lcs / float(len(target_tokens))


def evaluate_mode(
    client: QueryClient,
    corpus: str,
    mode: str,
    qa_pairs: list[dict[str, str]],
    top_k: int,
) -> dict[str, object]:
    """Evaluate retrieval quality for a single search mode."""
    search_fn = {
        "sparse": client.search_sparse,
        "dense": client.search_dense,
        "hybrid": client.search_hybrid,
    }[mode]

    per_query: list[dict[str, object]] = []
    total_recall = 0.0

    for i, pair in enumerate(qa_pairs, start=1):
        question = pair["question"]
        answer = pair["answer"]

        try:
            results = search_fn(corpus=corpus, query=question, top_k=top_k)
        except Exception as exc:
            logger.warning("[%s %d/%d] query failed: %s q=%s", mode, i, len(qa_pairs), exc, question[:60])
            per_query.append(
                {
                    "question": question,
                    "answer": answer,
                    "rouge_l_recall": 0.0,
                    "num_results": 0,
                    "error": str(exc),
                }
            )
            continue

        retrieved_text = " ".join(r.text for r in results)

        rouge_l_recall = 0.0 if retrieved_text.strip() == "" else _rouge_l_recall(answer, retrieved_text, lowercase=True)

        total_recall += rouge_l_recall
        per_query.append(
            {
                "question": question,
                "answer": answer,
                "rouge_l_recall": round(rouge_l_recall, 4),
                "num_results": len(results),
            }
        )

        logger.info("[%s %d/%d] ROUGE-L recall=%.4f results=%d q=%s", mode, i, len(qa_pairs), rouge_l_recall, len(results), question[:60])

    avg_recall = total_recall / len(qa_pairs) if len(qa_pairs) > 0 else 0.0

    return {
        "avg_rouge_l_recall": round(avg_recall, 4),
        "per_query": per_query,
    }


def build_report(corpus: str, top_k: int, num_qa_pairs: int, mode_results: dict[str, dict[str, object]]) -> dict[str, object]:
    """Assemble the full evaluation report."""
    return {
        "corpus": corpus,
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "top_k": top_k,
        "num_qa_pairs": num_qa_pairs,
        "modes": mode_results,
    }


def write_report(report: dict[str, object], report_path: Path) -> None:
    """Write the evaluation report atomically."""
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        dir=report_path.parent,
        mode="w",
        suffix=".json",
        encoding="utf-8",
        delete=False,
    ) as tmp:
        json.dump(report, tmp, indent=2, ensure_ascii=False)
        tmp_path = Path(tmp.name)

    tmp_path.replace(report_path)


def print_summary(mode_results: dict[str, dict[str, object]]) -> None:
    """Print a summary table to stdout."""
    print()
    print(f"{'Mode':<10} {'Avg ROUGE-L Recall':>20}")
    print("-" * 32)
    for mode in SEARCH_MODES:
        if mode in mode_results:
            avg = mode_results[mode]["avg_rouge_l_recall"]
            print(f"{mode:<10} {avg:>20.4f}")
    print()


def main() -> None:
    """Load config, run evaluation, and write report."""
    configure_logging()
    args = parse_args()
    corpus: str = args.corpus

    project_root = Path(__file__).resolve().parent.parent
    config_path = Path(args.config).resolve() if args.config else project_root / "config.yaml"
    config = Config.from_yaml(config_path)

    data_dir = config.resolve_data_dir(project_root)
    evals_path = data_dir / "input" / corpus / "evals" / "question_answer_pairs.json"
    qa_pairs = load_qa_pairs(evals_path)

    logger.info("Loaded %d Q&A pairs for corpus=%s", len(qa_pairs), corpus)

    service_config = config.get_service_config()
    client = QueryClient(host=service_config.host, port=service_config.port, http_client=None)

    mode_results: dict[str, dict[str, object]] = {}
    for mode in SEARCH_MODES:
        logger.info("Evaluating mode=%s for corpus=%s", mode, corpus)
        mode_results[mode] = evaluate_mode(
            client=client,
            corpus=corpus,
            mode=mode,
            qa_pairs=qa_pairs,
            top_k=TOP_K,
        )

    # Detect systemic failures: if every query in every mode failed, abort
    all_failed = all(
        all("error" in entry for entry in mode_data.get("per_query", []))  # type: ignore[union-attr]
        for mode_data in mode_results.values()
    )
    if all_failed:
        raise RuntimeError(f"all queries failed across all modes for corpus={corpus} — is the service running?")

    report = build_report(
        corpus=corpus,
        top_k=TOP_K,
        num_qa_pairs=len(qa_pairs),
        mode_results=mode_results,
    )

    report_path = project_root / "reports" / corpus / "evaluation.json"
    write_report(report, report_path)
    logger.info("Report written to %s", report_path)

    print_summary(mode_results)


if __name__ == "__main__":
    main()
