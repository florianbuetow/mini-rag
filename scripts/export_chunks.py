"""Export and verify document chunks across all stores (SQLite, FAISS, Tantivy)."""

import argparse
import sys
from pathlib import Path

from minirag.config import Config
from minirag.retrieval.faiss_dense import FAISSDense
from minirag.retrieval.tantivy_sparse import TantivySparse
from minirag.search.embeddings import FastTextEmbeddings
from minirag.search.embeddings_interface import Embeddings
from minirag.storage.interface import ChunkRecord, StorageReader
from minirag.storage.sqlite import SQLiteStorage


def parse_args() -> argparse.Namespace:
    """Parse and validate command-line arguments."""
    parser = argparse.ArgumentParser(description="Export and verify document chunks")
    parser.add_argument("--corpus", required=True, help="Name of the corpus")
    parser.add_argument("--config", default=None, help="Path to config file (default: config.yaml in project root)")
    parser.add_argument("document_id", type=int, help="Document ID to export")
    args = parser.parse_args()

    if args.document_id <= 0:
        print(f"Error: document_id must be a positive integer, got: {args.document_id}", file=sys.stderr)
        raise SystemExit(1)

    return args


def fetch_chunks(storage_reader: StorageReader, document_id: int) -> list[ChunkRecord]:
    """Read all chunks belonging to a document from storage."""
    return storage_reader.list_chunks(document_id=document_id)


def check_faiss(dense: FAISSDense, embeddings: Embeddings, chunk_id: int, content: str) -> bool:
    """Check whether a chunk is retrievable from the FAISS index."""
    vectors = embeddings.embed([content])
    results = dense.search(query_embedding=vectors[0], top_k=1)
    return any(r.chunk_id == chunk_id for r in results)


def check_tantivy(sparse: TantivySparse, chunk_id: int) -> bool:
    """Check whether a chunk_id exists in the Tantivy index."""
    searcher = sparse._index.searcher()
    query = sparse._index.parse_query(f"chunk_id:{chunk_id}", ["content"])
    result = searcher.search(query, limit=1)
    for _score, doc_address in result.hits:
        doc = searcher.doc(doc_address)
        doc_data = doc.to_dict()
        if "chunk_id" not in doc_data:
            raise ValueError("tantivy document missing chunk_id field")
        chunk_values = doc_data["chunk_id"]
        if not isinstance(chunk_values, list):
            raise ValueError("tantivy chunk_id field is not a list")
        if not all(isinstance(value, int) for value in chunk_values):
            raise ValueError("tantivy chunk_id values must all be integers")
        if chunk_id in chunk_values:
            return True
    return False


def close_if_supported(resource: object, cleanup_errors: list[BaseException], resource_name: str) -> None:
    """Call resource.close() when available and collect cleanup errors."""
    if not hasattr(resource, "close"):
        return
    close_candidate = resource.close
    if not callable(close_candidate):
        cleanup_errors.append(TypeError(f"{resource_name} close attribute is not callable"))
        return
    close_fn = close_candidate
    try:
        close_fn()
    except BaseException as exc:
        cleanup_errors.append(exc)


def close_backends(dense: FAISSDense, sparse: TantivySparse) -> list[BaseException]:
    """Close retrieval backends and return any cleanup errors."""
    cleanup_errors: list[BaseException] = []
    close_if_supported(sparse, cleanup_errors, "TantivySparse")
    close_if_supported(dense, cleanup_errors, "FAISSDense")
    return cleanup_errors


def initialize_backends(data_dir: Path, corpus: str, config: Config) -> tuple[Embeddings, FAISSDense, TantivySparse]:
    """Create embeddings, dense, and sparse backends with fail-fast cleanup."""
    index_config = config.get_index_config()
    embeddings = FastTextEmbeddings(
        model_path=data_dir / "models" / index_config.embeddings.model_name,
        expected_dimension=index_config.embeddings.dimension,
    )
    dense = FAISSDense(
        dimension=index_config.embeddings.dimension,
        index_dir=data_dir / "index" / corpus / "faiss",
        nprobe=index_config.faiss.nprobe,
    )

    try:
        sparse = TantivySparse(
            index_dir=data_dir / "index" / corpus / "tantivy",
            language=index_config.tantivy.language,
            stemming=index_config.tantivy.stemming,
        )
    except BaseException as exc:
        cleanup_errors: list[BaseException] = []
        close_if_supported(dense, cleanup_errors, "FAISSDense")
        if len(cleanup_errors) > 0:
            raise ExceptionGroup(
                "failed to initialize TantivySparse and cleanup dense backend",
                [exc, *cleanup_errors],
            ) from exc
        raise
    return (embeddings, dense, sparse)


def run_export(
    *,
    storage: SQLiteStorage,
    corpus: str,
    document_id: int,
    data_dir: Path,
    dense: FAISSDense,
    sparse: TantivySparse,
    embeddings: Embeddings,
) -> None:
    """Export chunks and verify they exist in dense and sparse indices."""
    chunks = fetch_chunks(storage_reader=storage, document_id=document_id)
    if len(chunks) == 0:
        print(f"Error: no chunks found for document_id {document_id} in corpus {corpus}", file=sys.stderr)
        raise SystemExit(1)

    print(f"Corpus {corpus}, Document {document_id}: {len(chunks)} chunks found in SQLite")
    print()

    export_dir = data_dir / "export" / corpus / str(document_id)
    export_dir.mkdir(parents=True, exist_ok=True)

    header = f"{'chunk_id':<10}| {'SQLite':^6} | {'FAISS':^5} | {'Tantivy':^7} | Exported"
    separator = f"{'-' * 10}|{'-' * 8}|{'-' * 7}|{'-' * 9}|{'-' * 8}"
    print(header)
    print(separator)

    faiss_count = 0
    tantivy_count = 0
    any_missing = False

    for chunk_id, content in chunks:
        in_sqlite = True

        in_faiss = check_faiss(dense, embeddings, chunk_id, content)
        if in_faiss:
            faiss_count += 1

        in_tantivy = check_tantivy(sparse, chunk_id)
        if in_tantivy:
            tantivy_count += 1

        export_path = export_dir / f"{chunk_id}.txt"
        export_path.write_text(content, encoding="utf-8")
        relative_export = str(export_path)

        sqlite_mark = "\u2713" if in_sqlite else "\u2717"
        faiss_mark = "\u2713" if in_faiss else "\u2717"
        tantivy_mark = "\u2713" if in_tantivy else "\u2717"

        print(f"{chunk_id:<10}|   {sqlite_mark}    |   {faiss_mark}   |    {tantivy_mark}    | {relative_export}")

        if not in_faiss or not in_tantivy:
            any_missing = True

    total = len(chunks)
    print()
    print(f"{faiss_count} out of {total} chunk IDs were found in the FAISS dense index")
    print(f"{tantivy_count} out of {total} chunk IDs were found in the Tantivy sparse index")

    if faiss_count < total:
        print(f"Error: {total - faiss_count} chunk(s) missing from FAISS dense index", file=sys.stderr)
    if tantivy_count < total:
        print(f"Error: {total - tantivy_count} chunk(s) missing from Tantivy sparse index", file=sys.stderr)
    if any_missing:
        raise SystemExit(1)


def main() -> None:
    """Export chunks and verify presence across all stores."""
    args = parse_args()
    corpus: str = args.corpus
    document_id: int = args.document_id

    project_root = Path(__file__).resolve().parent.parent
    config_path = Path(args.config).resolve() if args.config else project_root / "config.yaml"
    config = Config.from_yaml(config_path)
    data_dir = config.resolve_data_dir(project_root)
    index_config = config.get_index_config()
    database_path = data_dir / "storage" / corpus / index_config.storage.db_filename

    embeddings, dense, sparse = initialize_backends(data_dir=data_dir, corpus=corpus, config=config)

    try:
        storage = SQLiteStorage(database_path=database_path)
        try:
            run_export(
                storage=storage,
                corpus=corpus,
                document_id=document_id,
                data_dir=data_dir,
                dense=dense,
                sparse=sparse,
                embeddings=embeddings,
            )
        finally:
            storage.close()
    except BaseException as primary_exc:
        cleanup_errors = close_backends(dense, sparse)
        if len(cleanup_errors) > 0:
            raise ExceptionGroup(
                "export failed and backend cleanup encountered additional errors",
                [primary_exc, *cleanup_errors],
            ) from primary_exc
        raise
    else:
        cleanup_errors = close_backends(dense, sparse)
        if len(cleanup_errors) > 0:
            raise ExceptionGroup("cleanup failed after export", cleanup_errors)


if __name__ == "__main__":
    main()
