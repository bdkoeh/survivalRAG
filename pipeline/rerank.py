"""Cross-encoder reranker for improving retrieval precision.

Re-scores retrieved chunks by processing query + document pairs together through
a cross-encoder model, rather than comparing independent embeddings. This provides
15-40% precision improvement over embedding-only similarity scoring.

The reranker is optional and controlled by the SURVIVALRAG_RERANKER_MODEL env var.
When unset or empty, the reranker is disabled and retrieve() falls through to the
existing RRF + threshold pipeline unchanged.

Default model: BAAI/bge-reranker-v2-m3 (568M params, MIT license, self-hosted)
Requires: sentence-transformers (pip install sentence-transformers)

Usage:
    import pipeline.rerank as rerank
    rerank.init()                       # loads model if env var is set
    reranked = rerank.rerank(query, chunks, top_n=5)
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Default reranker model (empty string = disabled)
DEFAULT_MODEL = "BAAI/bge-reranker-v2-m3"

# Module-level state
_cross_encoder = None
_enabled = False


def init(model: str = None) -> None:
    """Initialize the cross-encoder reranker model.

    Loads the model specified by SURVIVALRAG_RERANKER_MODEL env var, or the
    model argument, or DEFAULT_MODEL. Set env var to empty string or "none"
    to explicitly disable reranking.

    The model is downloaded from HuggingFace on first use and cached locally.

    Args:
        model: Model name/path override. If None, reads from env var.
    """
    global _cross_encoder, _enabled

    if model is None:
        model = os.environ.get("SURVIVALRAG_RERANKER_MODEL", DEFAULT_MODEL)

    if not model or model.lower() == "none":
        _enabled = False
        logger.info("Reranker disabled (SURVIVALRAG_RERANKER_MODEL not set)")
        return

    try:
        from sentence_transformers import CrossEncoder

        _cross_encoder = CrossEncoder(model, trust_remote_code=True)
        _enabled = True
        logger.info("Reranker initialized: %s", model)
    except ImportError:
        _enabled = False
        logger.warning(
            "sentence-transformers not installed -- reranker disabled. "
            "Install with: pip install sentence-transformers"
        )
    except Exception as e:
        _enabled = False
        logger.warning("Failed to load reranker model '%s': %s", model, e)


def is_enabled() -> bool:
    """Check whether the reranker is initialized and ready."""
    return _enabled and _cross_encoder is not None


def rerank(
    query: str,
    chunks: list[dict],
    top_n: Optional[int] = None,
) -> list[dict]:
    """Re-score and re-order chunks using the cross-encoder model.

    Each (query, chunk_text) pair is scored by the cross-encoder which reads
    both together, providing more accurate relevance judgments than independent
    embeddings. Results are sorted by reranker score descending.

    If the reranker is not enabled, returns chunks unchanged (passthrough).

    Args:
        query: The user's search query.
        chunks: List of chunk dicts from RRF fusion (must have 'text' key).
        top_n: Maximum number of results to return. None returns all.

    Returns:
        List of chunk dicts re-ordered by reranker score, with 'rerank_score'
        field added to each. Original fields (id, rrf_score, similarity, text,
        metadata) are preserved.
    """
    if not is_enabled() or not chunks:
        return chunks[:top_n] if top_n else chunks

    # Build (query, document) pairs for cross-encoder scoring
    pairs = [(query, chunk["text"]) for chunk in chunks]

    scores = _cross_encoder.predict(pairs)

    # Attach scores and sort by reranker score descending
    scored = []
    for chunk, score in zip(chunks, scores):
        chunk_copy = dict(chunk)
        chunk_copy["rerank_score"] = float(score)
        scored.append(chunk_copy)

    scored.sort(key=lambda x: x["rerank_score"], reverse=True)

    if top_n is not None:
        scored = scored[:top_n]

    return scored
