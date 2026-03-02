"""Embedding benchmark with auto-generated query-document pairs and Recall@5 evaluation.

Auto-generates 50+ domain-specific query-document pairs from the actual Tier 1 corpus
by sampling chunks and using an Ollama LLM to create realistic queries (lay language,
medical terminology, and typo variants). Evaluates Recall@5 using cosine similarity
on nomic-embed-text embeddings. Results written to processed/benchmark/.

Requirement: CHNK-06 -- Embedding model benchmarked before full corpus processing.

Usage:
    python -m pipeline.benchmark
"""

import json
import logging
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import ollama

from pipeline.chunk import chunk_section, read_section_file
from pipeline.embed import embed_documents, embed_query, get_model_version

logger = logging.getLogger(__name__)

# Benchmark configuration
MIN_PAIRS = 50
TARGET_PAIRS = 60
RECALL_K = 5
PASS_THRESHOLD = 0.85

PAIRS_PATH = Path("processed/benchmark/pairs.jsonl")
RESULTS_PATH = Path("processed/benchmark/results.json")

# Query type distribution
QUERY_TYPES = ["lay_language", "medical_terminology", "typo_variant"]

# LLM models to try for query generation (in priority order)
LLM_CANDIDATES = ["llama3.1:8b", "llama3.1", "llama3.2", "qwen2.5:7b"]

# Prompts for each query type
QUERY_PROMPTS = {
    "lay_language": (
        "Generate a search query a non-expert would type to find this information. "
        "Use simple everyday language, no technical terms. Return ONLY the query, "
        "nothing else."
    ),
    "medical_terminology": (
        "Generate a search query using proper medical or military terminology for "
        "this information. Return ONLY the query, nothing else."
    ),
    "typo_variant": (
        "Generate a search query with a common typo or misspelling that someone "
        "might type quickly in an emergency. Return ONLY the query, nothing else."
    ),
}


def _find_available_llm() -> str:
    """Find an available LLM model from Ollama for query generation.

    Tries candidates in priority order. Falls back to any available model
    if no candidate is found.

    Returns:
        Model name string.

    Raises:
        RuntimeError: If no LLM model is available.
    """
    try:
        available = ollama.list()
    except Exception as e:
        raise ConnectionError(
            "Ollama is not running. Start it with: ollama serve"
        ) from e

    # Get list of available model names
    if isinstance(available, dict):
        model_list = available.get("models", [])
    else:
        model_list = getattr(available, "models", [])

    available_names = set()
    for m in model_list:
        if isinstance(m, dict):
            name = m.get("name", "")
        else:
            name = getattr(m, "model", "") or getattr(m, "name", "")
        if name:
            available_names.add(name)
            # Also add without tag for matching
            base_name = name.split(":")[0]
            available_names.add(base_name)

    logger.info("Available Ollama models: %s", sorted(available_names))

    # Try candidates in order
    for candidate in LLM_CANDIDATES:
        if candidate in available_names:
            logger.info("Selected LLM for query generation: %s", candidate)
            return candidate

    # Fall back to any non-embedding model
    for name in sorted(available_names):
        if "embed" not in name.lower() and "nomic" not in name.lower():
            logger.info("Falling back to LLM: %s", name)
            return name

    raise RuntimeError(
        "No LLM model available in Ollama for query generation. "
        f"Pull one with: ollama pull llama3.1:8b\n"
        f"Available models: {sorted(available_names)}"
    )


_WEAK_SECTION_PATTERNS = [
    "untitled",
    "glossary",
    "references",
    "index",
    "bibliography",
    "table of contents",
    "resources",
    "distribution",
    "preface",
]


def _is_weak_section(metadata: dict) -> bool:
    """Return True if a section header indicates low-quality benchmark content.

    Sections like "Untitled", "References-2", "Glossary" tend to produce
    chunks that are generic boilerplate, yielding bad benchmark pairs.
    """
    header = (metadata.get("section_heading") or "").strip().lower()

    # Empty header is weak
    if not header:
        return True

    for pattern in _WEAK_SECTION_PATTERNS:
        if header == pattern or header.startswith(pattern):
            return True

    return False


def _sample_chunks_from_corpus(n: int = TARGET_PAIRS) -> list[dict]:
    """Sample chunks from the actual corpus for benchmark pair generation.

    Scans processed/sections/ directories, reads section files, filters to
    sections with content >= 100 characters, applies stratified sampling by
    document, and chunks the sampled sections.

    Args:
        n: Target number of samples.

    Returns:
        List of dicts with keys: chunk_text, source_document, section_header,
        content_type, categories.
    """
    sections_dir = Path("processed/sections")
    if not sections_dir.exists():
        raise FileNotFoundError(
            f"Sections directory not found: {sections_dir}\n"
            "Run Phase 2 document processing first."
        )

    # Collect all section files grouped by document
    docs: dict[str, list[Path]] = {}
    for doc_dir in sorted(sections_dir.iterdir()):
        if not doc_dir.is_dir():
            continue
        section_files = sorted(doc_dir.glob("*.md"))
        if section_files:
            docs[doc_dir.name] = section_files

    if not docs:
        raise FileNotFoundError(
            f"No section files found in {sections_dir}/*/*.md"
        )

    logger.info("Found %d documents with section files", len(docs))

    # Read all sections and filter to those with enough content
    all_sections: list[dict] = []
    for doc_name, files in docs.items():
        for filepath in files:
            try:
                metadata, content = read_section_file(filepath)
                if len(content.strip()) < 100:
                    continue
                if _is_weak_section(metadata):
                    continue
                all_sections.append({
                    "filepath": filepath,
                    "metadata": metadata,
                    "content": content,
                    "doc_name": doc_name,
                })
            except Exception as e:
                logger.debug("Skipping %s: %s", filepath, e)

    logger.info(
        "Found %d sections with >= 100 chars content across %d docs",
        len(all_sections),
        len(docs),
    )

    if len(all_sections) < n:
        logger.warning(
            "Only %d eligible sections (need %d). Using all.",
            len(all_sections),
            n,
        )
        sampled = all_sections
    else:
        # Stratified sampling: proportional by document
        by_doc: dict[str, list[dict]] = {}
        for sec in all_sections:
            by_doc.setdefault(sec["doc_name"], []).append(sec)

        sampled = []
        total_sections = len(all_sections)
        for doc_name, doc_sections in sorted(by_doc.items()):
            # Proportion of this document in the corpus
            proportion = len(doc_sections) / total_sections
            doc_sample_size = max(1, round(proportion * n))
            doc_sample = random.sample(
                doc_sections, min(doc_sample_size, len(doc_sections))
            )
            sampled.extend(doc_sample)

        # Trim to target or pad if under
        if len(sampled) > n:
            sampled = random.sample(sampled, n)
        elif len(sampled) < n:
            remaining = [s for s in all_sections if s not in sampled]
            extra = random.sample(
                remaining, min(n - len(sampled), len(remaining))
            )
            sampled.extend(extra)

    logger.info("Sampled %d sections for benchmark", len(sampled))

    # Chunk each sampled section and take one chunk per section
    results = []
    for sec in sampled:
        try:
            chunks = chunk_section(sec["content"], sec["metadata"])
            if not chunks:
                continue
            # Filter out oversized chunks that exceed embedding context window
            chunks = [c for c in chunks if len(c.text) <= 6000]
            if not chunks:
                continue
            # Pick a random chunk if multiple, otherwise take the first
            chunk = random.choice(chunks) if len(chunks) > 1 else chunks[0]

            content_type_raw = sec["metadata"].get("content_type", {})
            if isinstance(content_type_raw, dict):
                content_type = content_type_raw.get("primary", "general")
            else:
                content_type = str(content_type_raw) if content_type_raw else "general"

            results.append({
                "chunk_text": chunk.text,
                "source_document": sec["metadata"].get(
                    "source_document", sec["doc_name"]
                ),
                "section_header": sec["metadata"].get("section_heading", ""),
                "content_type": content_type or "general",
                "categories": sec["metadata"].get("categories", []),
            })
        except Exception as e:
            logger.debug("Error chunking section from %s: %s", sec["doc_name"], e)

    logger.info("Produced %d chunks for benchmark pairs", len(results))
    return results


def _generate_query(
    chunk_text: str, query_type: str, llm_model: str
) -> str:
    """Generate a realistic search query for a chunk using an LLM.

    Args:
        chunk_text: The text content to generate a query for.
        query_type: One of "lay_language", "medical_terminology", "typo_variant".
        llm_model: The Ollama LLM model name to use.

    Returns:
        Generated query string.
    """
    prompt_instruction = QUERY_PROMPTS.get(query_type, QUERY_PROMPTS["lay_language"])

    # Truncate chunk text to first 500 chars to keep LLM context small
    truncated = chunk_text[:500]

    prompt = (
        f"{prompt_instruction}\n\n"
        f"Reference text:\n{truncated}\n\n"
        f"Search query:"
    )

    try:
        response = ollama.chat(
            model=llm_model,
            messages=[{"role": "user", "content": prompt}],
        )
        if isinstance(response, dict):
            result = response.get("message", {}).get("content", "").strip()
        else:
            result = response.message.content.strip()

        # Clean up: remove quotes, take first line only
        result = result.strip('"\'')
        result = result.split("\n")[0].strip()

        # Retry with simpler prompt if response is too short
        if len(result) < 5:
            logger.debug("Short response, retrying with simpler prompt")
            simple_prompt = (
                f"Write a short search query to find this information:\n"
                f"{truncated[:200]}\n\nQuery:"
            )
            response = ollama.chat(
                model=llm_model,
                messages=[{"role": "user", "content": simple_prompt}],
            )
            if isinstance(response, dict):
                result = response.get("message", {}).get("content", "").strip()
            else:
                result = response.message.content.strip()
            result = result.strip('"\'').split("\n")[0].strip()

        return result

    except Exception as e:
        logger.warning("Query generation failed: %s", e)
        return ""


def generate_benchmark_pairs(n: int = TARGET_PAIRS) -> list[dict]:
    """Generate benchmark query-document pairs from the actual corpus.

    Samples chunks from the corpus and uses an LLM to generate realistic
    queries for each. Distributes query types evenly (lay language, medical
    terminology, typo variants).

    Args:
        n: Target number of pairs.

    Returns:
        List of dicts with: query, expected_chunk, query_type, source_document,
        section_header.
    """
    # Find available LLM
    llm_model = _find_available_llm()
    logger.info("Using LLM '%s' for query generation", llm_model)

    # Sample chunks
    chunks = _sample_chunks_from_corpus(n)
    if len(chunks) < MIN_PAIRS:
        raise RuntimeError(
            f"Only {len(chunks)} chunks sampled, need at least {MIN_PAIRS}. "
            "Ensure processed/sections/ has enough content."
        )

    pairs = []
    for i, chunk_data in enumerate(chunks):
        # Rotate query types evenly
        query_type = QUERY_TYPES[i % len(QUERY_TYPES)]

        logger.info(
            "Generating query %d/%d (%s) for %s...",
            i + 1,
            len(chunks),
            query_type,
            chunk_data["source_document"],
        )

        query = _generate_query(chunk_data["chunk_text"], query_type, llm_model)
        if not query or len(query) < 5:
            logger.warning("Skipping pair %d: empty or too short query", i + 1)
            continue

        pairs.append({
            "query": query,
            "expected_chunk": chunk_data["chunk_text"],
            "query_type": query_type,
            "source_document": chunk_data["source_document"],
            "section_header": chunk_data["section_header"],
        })

    logger.info("Generated %d benchmark pairs", len(pairs))

    # Write to JSONL
    PAIRS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PAIRS_PATH, "w", encoding="utf-8") as f:
        for pair in pairs:
            f.write(json.dumps(pair, ensure_ascii=False) + "\n")

    logger.info("Wrote pairs to %s", PAIRS_PATH)
    return pairs


def evaluate_recall(pairs: list[dict]) -> dict:
    """Evaluate Recall@K for benchmark query-document pairs.

    Embeds all expected chunks as the "corpus", then for each query, embeds
    the query and computes cosine similarity against all chunk embeddings
    to check if the expected chunk appears in the top-K results.

    Ollama returns L2-normalized vectors, so dot product = cosine similarity.

    Args:
        pairs: List of benchmark pair dicts with query and expected_chunk fields.

    Returns:
        Dict with recall_at_k, per_query_scores, mean_reciprocal_rank,
        worst_performers, and per_query_type_recall.
    """
    logger.info("Evaluating Recall@%d on %d pairs...", RECALL_K, len(pairs))

    # Embed all expected chunks as the corpus
    chunk_texts = [p["expected_chunk"] for p in pairs]
    logger.info("Embedding %d corpus chunks...", len(chunk_texts))
    chunk_embeddings = embed_documents(chunk_texts)
    corpus_matrix = np.array(chunk_embeddings, dtype=np.float32)

    # Evaluate each query
    per_query_scores = []
    hits = 0
    reciprocal_ranks = []
    type_hits: dict[str, list[bool]] = {qt: [] for qt in QUERY_TYPES}

    for i, pair in enumerate(pairs):
        logger.info(
            "Evaluating query %d/%d: %s",
            i + 1,
            len(pairs),
            pair["query"][:60],
        )

        # Embed query
        query_embedding = embed_query(pair["query"])
        query_vec = np.array(query_embedding, dtype=np.float32)

        # Cosine similarity via dot product (vectors are L2-normalized)
        similarities = np.dot(corpus_matrix, query_vec)

        # Rank by similarity descending
        ranked_indices = np.argsort(similarities)[::-1]

        # Find rank of expected chunk (same index as in pairs list)
        expected_rank = int(np.where(ranked_indices == i)[0][0]) + 1  # 1-based

        # Check if in top-K
        hit = expected_rank <= RECALL_K
        if hit:
            hits += 1

        reciprocal_ranks.append(1.0 / expected_rank)
        query_type = pair.get("query_type", "unknown")
        if query_type in type_hits:
            type_hits[query_type].append(hit)

        per_query_scores.append({
            "query": pair["query"],
            "query_type": query_type,
            "source_document": pair["source_document"],
            "section_header": pair["section_header"],
            "expected_rank": expected_rank,
            "similarity_score": float(similarities[i]),
            "top_similarity": float(similarities[ranked_indices[0]]),
            "hit": hit,
        })

    # Compute aggregate metrics
    recall_at_k = hits / len(pairs) if pairs else 0.0
    mean_reciprocal_rank = float(np.mean(reciprocal_ranks)) if reciprocal_ranks else 0.0

    # Per query type recall
    per_query_type_recall = {}
    for qt, qt_hits in type_hits.items():
        if qt_hits:
            per_query_type_recall[qt] = sum(qt_hits) / len(qt_hits)

    # Worst performers (bottom 10 by expected rank)
    worst_performers = sorted(
        per_query_scores, key=lambda x: x["expected_rank"], reverse=True
    )[:10]

    return {
        "recall_at_k": recall_at_k,
        "k": RECALL_K,
        "per_query_scores": per_query_scores,
        "mean_reciprocal_rank": mean_reciprocal_rank,
        "worst_performers": worst_performers,
        "per_query_type_recall": per_query_type_recall,
    }


def run_benchmark() -> dict:
    """Main entry point: generate pairs, evaluate, report results.

    Orchestrates the full benchmark pipeline:
    1. Generate pairs (or load existing from PAIRS_PATH if already generated)
    2. Evaluate Recall@5
    3. Write results to RESULTS_PATH
    4. Print human-readable summary
    5. If failed: print detailed failure report, exit non-zero

    Returns:
        Results dict with all metrics.
    """
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    print("=" * 70)
    print("EMBEDDING BENCHMARK: nomic-embed-text Recall@5 Evaluation")
    print("=" * 70)
    print()

    # Prerequisites check
    print("Checking prerequisites...")

    # 1. Verify Ollama is running and nomic-embed-text available
    try:
        model_version = get_model_version()
        print(f"  [OK] nomic-embed-text model: {model_version}")
    except ConnectionError as e:
        print(f"  [FAIL] Ollama not running: {e}")
        print("\nStart Ollama: ollama serve")
        sys.exit(1)
    except RuntimeError as e:
        print(f"  [FAIL] Model not available: {e}")
        print("\nPull model: ollama pull nomic-embed-text")
        sys.exit(1)

    # 2. Verify sections directory exists
    sections_dir = Path("processed/sections")
    if not sections_dir.exists() or not any(sections_dir.iterdir()):
        print(f"  [FAIL] No sections found in {sections_dir}")
        print("\nRun Phase 2 document processing first.")
        sys.exit(1)
    doc_count = sum(1 for d in sections_dir.iterdir() if d.is_dir())
    print(f"  [OK] Sections directory: {doc_count} documents")

    print()

    # Step 1: Generate pairs (or load existing)
    if PAIRS_PATH.exists():
        existing = []
        with open(PAIRS_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    existing.append(json.loads(line))

        if len(existing) >= MIN_PAIRS:
            print(
                f"Reusing {len(existing)} existing pairs from {PAIRS_PATH} "
                f"(>= {MIN_PAIRS} minimum)"
            )
            pairs = existing
        else:
            print(
                f"Existing pairs ({len(existing)}) below minimum ({MIN_PAIRS}). "
                f"Regenerating..."
            )
            pairs = generate_benchmark_pairs()
    else:
        print(f"Generating {TARGET_PAIRS} benchmark pairs...")
        pairs = generate_benchmark_pairs()

    if len(pairs) < MIN_PAIRS:
        print(
            f"\n[FAIL] Only {len(pairs)} pairs generated, need at least {MIN_PAIRS}."
        )
        sys.exit(1)

    print(f"\nBenchmark pairs: {len(pairs)}")
    type_counts = {}
    for p in pairs:
        qt = p.get("query_type", "unknown")
        type_counts[qt] = type_counts.get(qt, 0) + 1
    for qt, count in sorted(type_counts.items()):
        print(f"  {qt}: {count}")

    print()

    # Step 2: Evaluate Recall@5
    print(f"Evaluating Recall@{RECALL_K}...")
    eval_results = evaluate_recall(pairs)

    # Step 3: Build results
    results = {
        "model": "nomic-embed-text",
        "model_version": model_version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "num_pairs": len(pairs),
        "recall_at_5": eval_results["recall_at_k"],
        "pass_threshold": PASS_THRESHOLD,
        "passed": eval_results["recall_at_k"] >= PASS_THRESHOLD,
        "mean_reciprocal_rank": eval_results["mean_reciprocal_rank"],
        "per_query_type_recall": eval_results["per_query_type_recall"],
        "worst_performers": eval_results["worst_performers"],
    }

    # Write results
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    logger.info("Results written to %s", RESULTS_PATH)

    # Step 4: Print summary
    print()
    print("=" * 70)
    print("BENCHMARK RESULTS")
    print("=" * 70)
    print()
    print(f"  Model:                nomic-embed-text ({model_version})")
    print(f"  Pairs evaluated:      {results['num_pairs']}")
    print(f"  Recall@{RECALL_K}:            {results['recall_at_5']:.2%}")
    print(f"  Pass threshold:       {results['pass_threshold']:.0%}")
    print(f"  Mean reciprocal rank: {results['mean_reciprocal_rank']:.4f}")
    print()

    print("  Per query type:")
    for qt, recall in sorted(results["per_query_type_recall"].items()):
        print(f"    {qt}: {recall:.2%}")

    print()

    # Step 5/6: Pass/fail determination
    if results["passed"]:
        print(f"  RESULT: PASSED (Recall@{RECALL_K} = {results['recall_at_5']:.2%} >= {PASS_THRESHOLD:.0%})")
        print()
        print("  nomic-embed-text is suitable for full corpus embedding.")
        print(f"  Results saved to: {RESULTS_PATH}")
        print("=" * 70)
        return results
    else:
        print(f"  RESULT: FAILED (Recall@{RECALL_K} = {results['recall_at_5']:.2%} < {PASS_THRESHOLD:.0%})")
        print()
        print("  DETAILED FAILURE REPORT")
        print("  " + "-" * 40)
        print()
        print("  Worst performing queries:")
        for i, wp in enumerate(results["worst_performers"][:10], 1):
            print(f"    {i}. Rank {wp['expected_rank']}: \"{wp['query']}\"")
            print(f"       Type: {wp['query_type']}, Source: {wp['source_document']}")
            print(f"       Similarity: {wp['similarity_score']:.4f} (top: {wp['top_similarity']:.4f})")
            print()

        print("  Investigation steps:")
        print("    1. Check if worst-performing queries match chunk content semantically")
        print("    2. Inspect chunk quality for those sections")
        print("    3. Consider adjusting chunk sizes or content preprocessing")
        print("    4. Try different embedding model if issues persist")
        print()
        print(f"  Results saved to: {RESULTS_PATH}")
        print("=" * 70)
        return results


if __name__ == "__main__":
    results = run_benchmark()
    if not results.get("passed", False):
        sys.exit(1)
