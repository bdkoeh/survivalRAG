"""Hybrid retrieval engine with vector search, BM25, RRF fusion, and threshold filtering.

Implements always-on hybrid search: every query runs both BM25 keyword search
and vector similarity search via ChromaDB, then fuses results using Reciprocal
Rank Fusion (RRF). Category pre-filtering is applied to both search paths.
A cosine similarity threshold filters out irrelevant chunks -- when no chunks
pass, the caller receives an empty list to trigger refusal.

The BM25 index is built in-memory at application startup and must be rebuilt
after knowledge base updates (application restart).
"""

import logging
import os
from typing import Optional

import pipeline._chromadb_compat  # noqa: F401 -- must patch before chromadb import
import bm25s
import chromadb

from pipeline.embed import embed_query
from pipeline.ingest import get_collection, get_all_chunks_for_bm25

logger = logging.getLogger(__name__)

# Default cosine similarity threshold (configurable via SURVIVALRAG_RELEVANCE_THRESHOLD)
DEFAULT_THRESHOLD = 0.25

# Default maximum chunks to return (configurable via SURVIVALRAG_MAX_CHUNKS)
DEFAULT_MAX_RESULTS = 5

# RRF fusion constant (standard value from Cormack et al. 2009)
RRF_K = 60

# Module-level state (initialized by init())
_bm25_index: Optional[bm25s.BM25] = None
_bm25_ids: list[str] = []
_bm25_categories: dict[str, list[str]] = {}
_collection: Optional[chromadb.Collection] = None


def init(chroma_path: str = None) -> None:
    """Initialize the retrieval engine: connect to ChromaDB and build BM25 index.

    Must be called once at application startup before any retrieve() calls.

    Args:
        chroma_path: Optional path to ChromaDB persistent storage directory.
            If None, uses the default CHROMA_PATH from ingest module.
    """
    global _collection

    if chroma_path is not None:
        _collection = get_collection(path=chroma_path)
    else:
        _collection = get_collection()

    ids, docs, metas = get_all_chunks_for_bm25(collection=_collection)
    build_bm25_index(ids, docs, metas)

    logger.info("Retrieval engine initialized: %d chunks in index", len(ids))


def build_bm25_index(
    ids: list[str], documents: list[str], metadatas: list[dict]
) -> None:
    """Build the in-memory BM25 keyword search index.

    Stores chunk IDs and category mappings for post-hoc category filtering
    of BM25 results before RRF fusion.

    Args:
        ids: List of chunk IDs corresponding to documents.
        documents: List of chunk text strings.
        metadatas: List of metadata dicts (must contain 'categories' key).
    """
    global _bm25_index, _bm25_ids, _bm25_categories

    _bm25_ids = ids
    _bm25_categories = {
        chunk_id: meta.get("categories", [])
        for chunk_id, meta in zip(ids, metadatas)
    }

    if not documents:
        _bm25_index = None
        logger.warning("BM25 index not built: no documents provided")
        return

    corpus_tokens = bm25s.tokenize(documents)
    _bm25_index = bm25s.BM25()
    _bm25_index.index(corpus_tokens)

    logger.info("BM25 index built: %d documents", len(ids))


def _build_category_filter(categories: Optional[list[str]]) -> Optional[dict]:
    """Build a ChromaDB where filter for category pre-filtering.

    Uses $contains operator for array metadata filtering. Single category
    uses direct $contains; multiple categories use $or logic (match ANY).

    Args:
        categories: List of category strings to filter by, or None/empty for all.

    Returns:
        ChromaDB where filter dict, or None if no filtering needed.
    """
    if not categories:
        return None

    if len(categories) == 1:
        return {"categories": {"$contains": categories[0]}}

    return {"$or": [{"categories": {"$contains": c}} for c in categories]}


def _vector_search(
    query_embedding: list[float],
    n_results: int,
    where_filter: Optional[dict],
) -> list[dict]:
    """Run vector similarity search via ChromaDB.

    Queries the collection with the pre-computed query embedding and optional
    category filter. Converts ChromaDB cosine distances to similarity scores.

    Args:
        query_embedding: 768-dim query embedding vector.
        n_results: Maximum number of results to return.
        where_filter: ChromaDB where filter for category pre-filtering, or None.

    Returns:
        List of result dicts with keys: id, similarity, text, metadata.
    """
    query_kwargs: dict = {
        "query_embeddings": [query_embedding],
        "n_results": n_results,
        "include": ["documents", "metadatas", "distances"],
    }
    if where_filter is not None:
        query_kwargs["where"] = where_filter

    raw = _collection.query(**query_kwargs)

    # Handle empty results
    if not raw["ids"] or not raw["ids"][0]:
        return []

    results = []
    for doc_id, distance, doc, meta in zip(
        raw["ids"][0],
        raw["distances"][0],
        raw["documents"][0],
        raw["metadatas"][0],
    ):
        results.append({
            "id": doc_id,
            "similarity": 1 - distance,  # CRITICAL: convert distance to similarity
            "text": doc,
            "metadata": meta,
        })

    return results


def _bm25_search(
    query: str, n_results: int, categories: Optional[list[str]]
) -> list[dict]:
    """Run BM25 keyword search with post-hoc category filtering.

    Searches the in-memory BM25 index and filters results by category
    BEFORE returning, to prevent wrong-category results from leaking
    through RRF fusion.

    Args:
        query: Raw query string for keyword search.
        n_results: Maximum number of results to return.
        categories: List of categories to filter by, or None for all.

    Returns:
        List of result dicts with keys: id, bm25_score.
        Results with score <= 0 are excluded.
    """
    if _bm25_index is None:
        return []

    query_tokens = bm25s.tokenize(query)
    k = min(n_results, len(_bm25_ids))
    if k == 0:
        return []

    results, scores = _bm25_index.retrieve(query_tokens, k=k)

    # results shape: (1, k) indices; scores shape: (1, k) BM25 scores
    bm25_results = []
    for idx, score in zip(results[0], scores[0]):
        idx = int(idx)
        score = float(score)

        if score <= 0:
            continue

        if idx < 0 or idx >= len(_bm25_ids):
            continue

        chunk_id = _bm25_ids[idx]

        # CRITICAL: Apply category filtering post-hoc BEFORE returning
        # This prevents BM25 results from wrong categories leaking through RRF
        if categories:
            chunk_cats = _bm25_categories.get(chunk_id, [])
            if not any(cat in chunk_cats for cat in categories):
                continue

        bm25_results.append({"id": chunk_id, "bm25_score": score})

    return bm25_results


def reciprocal_rank_fusion(
    vector_results: list[dict],
    bm25_results: list[dict],
    k: int = RRF_K,
) -> list[dict]:
    """Combine vector and BM25 ranked lists using Reciprocal Rank Fusion.

    RRF score = sum(1 / (k + rank)) across all lists where a document appears.
    Documents that appear only in BM25 results (no vector metadata) are excluded
    from the final output since they lack the text and metadata needed for response.

    Args:
        vector_results: Ranked vector search results (must have id, similarity, text, metadata).
        bm25_results: Ranked BM25 search results (must have id, bm25_score).
        k: RRF constant, default 60 (empirically optimal, insensitive to exact value).

    Returns:
        List of fused result dicts sorted by RRF score descending, with keys:
        id, rrf_score, similarity, text, metadata.
    """
    rrf_scores: dict[str, float] = {}
    metadata_map: dict[str, dict] = {}
    text_map: dict[str, str] = {}
    similarity_map: dict[str, float] = {}

    # Vector results (already ranked by similarity)
    for rank, result in enumerate(vector_results):
        doc_id = result["id"]
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (k + rank + 1)
        metadata_map[doc_id] = result["metadata"]
        text_map[doc_id] = result["text"]
        similarity_map[doc_id] = result["similarity"]

    # BM25 results (already ranked by BM25 score)
    for rank, result in enumerate(bm25_results):
        doc_id = result["id"]
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (k + rank + 1)
        # BM25-only results lack text/metadata -- they will be excluded below

    # Sort by RRF score descending
    sorted_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)

    # Only return results that have full metadata (present in vector results)
    return [
        {
            "id": doc_id,
            "rrf_score": rrf_scores[doc_id],
            "similarity": similarity_map.get(doc_id, 0),
            "text": text_map.get(doc_id, ""),
            "metadata": metadata_map.get(doc_id, {}),
        }
        for doc_id in sorted_ids
        if doc_id in metadata_map
    ]


def retrieve(
    query: str,
    categories: Optional[list[str]] = None,
    n_results: int = None,
    threshold: float = None,
) -> list[dict]:
    """Run hybrid search, fuse with RRF, filter by threshold.

    Main entry point for retrieval. Embeds the query, runs both vector and
    BM25 searches with category filtering, fuses via RRF, applies cosine
    similarity threshold, and returns the top results.

    When no chunks pass the threshold, returns an empty list. The caller
    should use this to trigger a refusal response.

    Args:
        query: User's search query string.
        categories: Optional list of categories to filter by (OR logic).
            None or empty means search all categories.
        n_results: Maximum number of results to return.
            Defaults to SURVIVALRAG_MAX_CHUNKS env var or DEFAULT_MAX_RESULTS.
        threshold: Cosine similarity threshold for relevance filtering.
            Defaults to SURVIVALRAG_RELEVANCE_THRESHOLD env var or DEFAULT_THRESHOLD.

    Returns:
        List of result dicts with keys: id, rrf_score, similarity, text, metadata.
        Empty list when no chunks pass the threshold (triggers refusal).

    Raises:
        RuntimeError: If init() has not been called.
    """
    if _collection is None or _bm25_index is None:
        raise RuntimeError(
            "Retrieval engine not initialized. Call init() first."
        )

    # Read defaults from env vars if not provided
    if n_results is None:
        n_results = int(
            os.environ.get("SURVIVALRAG_MAX_CHUNKS", DEFAULT_MAX_RESULTS)
        )
    if threshold is None:
        threshold = float(
            os.environ.get("SURVIVALRAG_RELEVANCE_THRESHOLD", DEFAULT_THRESHOLD)
        )

    # Step 1: Embed query via Ollama nomic-embed-text (with search_query: prefix)
    query_embedding = embed_query(query)

    # Step 2: Build category filter for ChromaDB pre-filtering
    where_filter = _build_category_filter(categories)

    # Step 3: Vector search (over-fetch for fusion)
    vector_results = _vector_search(query_embedding, n_results * 2, where_filter)

    # Step 4: BM25 search (category-filtered post-hoc)
    bm25_results = _bm25_search(query, n_results * 2, categories)

    # Step 5: Fuse via Reciprocal Rank Fusion
    fused = reciprocal_rank_fusion(vector_results, bm25_results)

    # Step 6: Threshold filter (cosine similarity)
    passed = [r for r in fused if r["similarity"] >= threshold]

    # Log search metrics
    logger.info(
        "Query: '%s' | Categories: %s | Vector: %d | BM25: %d | Fused: %d | Passed threshold: %d",
        query,
        categories,
        len(vector_results),
        len(bm25_results),
        len(fused),
        len(passed),
    )

    # Step 7: Return top n_results or empty list (triggers refusal)
    return passed[:n_results]
