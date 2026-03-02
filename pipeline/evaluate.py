"""Evaluation runner for SurvivalRAG pipeline quality metrics.

Measures four evaluation dimensions against golden datasets:
1. Retrieval Recall -- proportion of expected chunk IDs found in top-K results
2. Hallucination Refusal -- out-of-scope queries must be refused (100% required)
3. Citation Faithfulness -- verified citations in full-mode responses (90% threshold)
4. Safety Warning Surfacing -- safety-critical queries must surface warnings

Outputs a terminal summary table and writes detailed JSON results to
processed/eval/results.json. Exits non-zero when aggregate thresholds are not met.

Usage:
    python -m pipeline.evaluate                   # Run all dimensions
    python -m pipeline.evaluate --suite retrieval  # Retrieval + safety only (fast, no LLM)
    python -m pipeline.evaluate --suite refusal    # Refusal only
    python -m pipeline.evaluate --suite citation   # Citation faithfulness only
    python -m pipeline.evaluate --suite safety     # Safety warnings only
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pipeline.retrieve as retrieve
import pipeline.generate as gen
from pipeline.prompt import collect_safety_warnings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (hardcoded per CONTEXT.md -- not env vars)
# ---------------------------------------------------------------------------

RETRIEVAL_THRESHOLD = 0.85       # 85% recall required (medical terminology)
CITATION_THRESHOLD = 0.90        # 90% citation faithfulness required
REFUSAL_THRESHOLD = 1.00         # 100% refusal required

GOLDEN_PATH = Path("data/eval/golden_queries.jsonl")
REFUSAL_PATH = Path("data/eval/refusal_queries.jsonl")
RESULTS_PATH = Path("processed/eval/results.json")


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_dataset(path: Path) -> list[dict]:
    """Load JSONL dataset. Returns list of parsed entries.

    Args:
        path: Path to the JSONL file.

    Returns:
        List of parsed JSON objects, one per non-empty line.

    Raises:
        FileNotFoundError: If the dataset file does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    entries = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entries.append(json.loads(line))
    return entries


# ---------------------------------------------------------------------------
# Pre-flight validation
# ---------------------------------------------------------------------------

def validate_chunk_ids(entries: list[dict]) -> tuple[int, int]:
    """Check that expected_chunk_ids exist in ChromaDB.

    Queries the ChromaDB collection for all expected chunk IDs referenced
    in the golden dataset. Logs missing IDs but does NOT abort -- missing
    IDs reduce retrieval scores naturally, which is the correct behavior.

    Args:
        entries: List of golden query entries with expected_chunk_ids fields.

    Returns:
        Tuple of (found_count, total_count).
    """
    all_expected_ids: list[str] = []
    for entry in entries:
        all_expected_ids.extend(entry.get("expected_chunk_ids", []))

    unique_ids = list(set(all_expected_ids))
    if not unique_ids:
        return (0, 0)

    # Query ChromaDB for existence of expected IDs
    try:
        result = retrieve._collection.get(ids=unique_ids)
        found_ids = set(result["ids"]) if result and result.get("ids") else set()
    except Exception as e:
        logger.warning("Could not validate chunk IDs: %s", e)
        return (0, len(unique_ids))

    missing = set(unique_ids) - found_ids
    if missing:
        logger.warning(
            "Golden dataset references %d chunk IDs not found in ChromaDB: %s",
            len(missing),
            sorted(missing)[:10],  # Show first 10
        )
        print(
            f"  [WARN] {len(missing)} of {len(unique_ids)} expected chunk IDs "
            f"not found in knowledge base"
        )
        if len(missing) <= 10:
            for mid in sorted(missing):
                print(f"         - {mid}")
        else:
            for mid in sorted(missing)[:10]:
                print(f"         - {mid}")
            print(f"         ... and {len(missing) - 10} more")

    return (len(found_ids), len(unique_ids))


# ---------------------------------------------------------------------------
# Dimension 1: Retrieval Recall (EVAL-02)
# ---------------------------------------------------------------------------

def evaluate_retrieval(entries: list[dict]) -> list[dict]:
    """Evaluate retrieval recall for each golden query.

    For each golden query, calls retrieve.retrieve() and measures the
    proportion of expected_chunk_ids found in the retrieved result IDs.

    Args:
        entries: List of golden query entries with expected_chunk_ids.

    Returns:
        List of per-query result dicts with dimension="retrieval".
    """
    results = []
    total = len(entries)

    for i, entry in enumerate(entries, start=1):
        print(f"  Evaluating retrieval: {i}/{total}...", end="\r")

        query = entry["query"]
        category = entry.get("category")
        expected_ids = set(entry.get("expected_chunk_ids", []))

        try:
            retrieved = retrieve.retrieve(
                query,
                categories=[category] if category else None,
            )
            retrieved_ids = {r["id"] for r in retrieved}
        except Exception as e:
            logger.warning("Retrieval failed for query '%s': %s", query, e)
            retrieved_ids = set()
            retrieved = []

        hits = retrieved_ids & expected_ids
        misses = expected_ids - retrieved_ids
        score = len(hits) / len(expected_ids) if expected_ids else 0.0

        results.append({
            "query": query,
            "query_type": entry.get("query_type", "unknown"),
            "category": category,
            "dimension": "retrieval",
            "score": score,
            "expected": sorted(expected_ids),
            "actual": [r["id"] for r in retrieved],
            "hits": sorted(hits),
            "misses": sorted(misses),
        })

    print()  # Clear progress line
    return results


# ---------------------------------------------------------------------------
# Dimension 2: Refusal / Hallucination (EVAL-03)
# ---------------------------------------------------------------------------

def evaluate_refusal(entries: list[dict]) -> list[dict]:
    """Evaluate that out-of-scope queries are refused.

    For each refusal query, calls gen.answer() and checks that the
    returned status is "refused". Uses status check (not exact message
    string matching) per CONTEXT.md discretion recommendation.

    Args:
        entries: List of refusal query entries with expected_action="refuse".

    Returns:
        List of per-query result dicts with dimension="refusal".
    """
    results = []
    total = len(entries)

    for i, entry in enumerate(entries, start=1):
        print(f"  Evaluating refusal: {i}/{total}...", end="\r")

        query = entry["query"]

        try:
            result = gen.answer(query)
            refused = result["status"] == "refused"
            status = result["status"]
            response_preview = result["response"][:100] if not refused else None
        except Exception as e:
            logger.warning("Refusal eval failed for query '%s': %s", query, e)
            refused = False
            status = "error"
            response_preview = str(e)[:100]

        results.append({
            "query": query,
            "query_type": entry.get("query_type", "unknown"),
            "dimension": "refusal",
            "score": 1.0 if refused else 0.0,
            "passed": refused,
            "status": status,
            "response_preview": response_preview,
        })

    print()  # Clear progress line
    return results


# ---------------------------------------------------------------------------
# Dimension 3: Citation Faithfulness (EVAL-04)
# ---------------------------------------------------------------------------

def evaluate_citation_faithfulness(entries: list[dict]) -> list[dict]:
    """Evaluate citation faithfulness on full pipeline responses.

    For each golden query, calls gen.answer(mode="full") and uses the
    verification dict from the response to score citation faithfulness.
    Only tests "full" mode (not ultra) per Pitfall 3 from RESEARCH.md.
    Skips entries where the response was refused.

    Args:
        entries: List of golden query entries.

    Returns:
        List of per-query result dicts with dimension="citation_faithfulness".
    """
    results = []
    total = len(entries)

    for i, entry in enumerate(entries, start=1):
        print(f"  Evaluating citation faithfulness: {i}/{total}...", end="\r")

        query = entry["query"]

        try:
            result = gen.answer(query, mode="full")
        except Exception as e:
            logger.warning("Citation eval failed for query '%s': %s", query, e)
            results.append({
                "query": query,
                "dimension": "citation_faithfulness",
                "score": 0.0,
                "citations_found": 0,
                "citations_verified": 0,
                "citations_failed": 0,
                "details": [],
                "error": str(e)[:200],
            })
            continue

        # Skip refused queries -- refusal is not a citation failure
        if result["status"] == "refused":
            continue

        verification = result.get("verification") or {}

        # Skip ultra mode (no citations) -- should not happen since we use full
        if verification.get("skipped"):
            continue

        found = verification.get("citations_found", 0)
        verified = verification.get("citations_verified", 0)
        failed = verification.get("citations_failed", 0)

        # No citations found is not a failure per research
        score = verified / found if found > 0 else 1.0

        results.append({
            "query": query,
            "dimension": "citation_faithfulness",
            "score": score,
            "citations_found": found,
            "citations_verified": verified,
            "citations_failed": failed,
            "details": verification.get("details", []),
        })

    print()  # Clear progress line
    return results


# ---------------------------------------------------------------------------
# Dimension 4: Safety Warning Surfacing (EVAL-05)
# ---------------------------------------------------------------------------

def evaluate_safety_warnings(entries: list[dict]) -> list[dict]:
    """Evaluate that safety-critical queries surface associated warnings.

    Filters to entries where safety_critical is True, then for each:
    retrieves chunks and checks that collect_safety_warnings() returns
    a non-empty list.

    Args:
        entries: List of golden query entries (only safety_critical=True are tested).

    Returns:
        List of per-query result dicts with dimension="safety_warnings".
    """
    safety_entries = [e for e in entries if e.get("safety_critical")]
    results = []
    total = len(safety_entries)

    if total == 0:
        print("  No safety-critical entries found in dataset")
        return results

    for i, entry in enumerate(safety_entries, start=1):
        print(f"  Evaluating safety warnings: {i}/{total}...", end="\r")

        query = entry["query"]

        try:
            retrieved = retrieve.retrieve(query)
            warnings = collect_safety_warnings(retrieved)
        except Exception as e:
            logger.warning("Safety eval failed for query '%s': %s", query, e)
            warnings = []

        has_warnings = len(warnings) > 0

        results.append({
            "query": query,
            "dimension": "safety_warnings",
            "score": 1.0 if has_warnings else 0.0,
            "passed": has_warnings,
            "warnings_found": len(warnings),
            "warning_texts": [w["warning_text"][:80] for w in warnings],
        })

    print()  # Clear progress line
    return results


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

def init():
    """Initialize retrieval and generation engines for evaluation.

    Calls retrieve.init() and gen.init() with fail-fast error handling
    matching the ask.py / generate.py pattern from CONTEXT.md.
    """
    try:
        retrieve.init(chroma_path="./data/chroma")
    except ConnectionError:
        print("[FAIL] Ollama is not running. Start it with: ollama serve")
        sys.exit(1)
    except RuntimeError as e:
        print(f"[FAIL] {e}")
        sys.exit(1)

    try:
        gen.init()
    except ConnectionError:
        print("[FAIL] Ollama is not running. Start it with: ollama serve")
        sys.exit(1)
    except RuntimeError as e:
        print(f"[FAIL] {e}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def aggregate_results(results: list[dict], dimension: str) -> dict:
    """Compute aggregate score for a dimension.

    Calculates mean score across all results, compares against the
    appropriate threshold, and returns aggregate metrics.

    For retrieval specifically, also computes a filtered aggregate for
    medical_terminology queries only (the roadmap threshold applies to
    medical terminology, not overall).

    Args:
        results: List of per-query result dicts for one dimension.
        dimension: The dimension name.

    Returns:
        Dict with dimension, score, count, passed_count, threshold, status.
    """
    if not results:
        return {
            "dimension": dimension,
            "score": 0.0,
            "count": 0,
            "passed_count": 0,
            "threshold": None,
            "status": "NO_DATA",
        }

    scores = [r["score"] for r in results]
    mean_score = sum(scores) / len(scores)
    passed_count = sum(1 for s in scores if s >= 1.0)

    # Determine threshold and status based on dimension
    if dimension == "retrieval":
        # Overall retrieval is informational (no threshold)
        return {
            "dimension": dimension,
            "label": "Retrieval Recall (all)",
            "score": mean_score,
            "count": len(results),
            "passed_count": passed_count,
            "threshold": None,
            "status": "INFO",
        }
    elif dimension == "retrieval_medical":
        return {
            "dimension": dimension,
            "label": "Retrieval Recall (medical)",
            "score": mean_score,
            "count": len(results),
            "passed_count": passed_count,
            "threshold": RETRIEVAL_THRESHOLD,
            "status": "PASS" if mean_score >= RETRIEVAL_THRESHOLD else "FAIL",
        }
    elif dimension == "citation_faithfulness":
        return {
            "dimension": dimension,
            "label": "Citation Faithfulness",
            "score": mean_score,
            "count": len(results),
            "passed_count": passed_count,
            "threshold": CITATION_THRESHOLD,
            "status": "PASS" if mean_score >= CITATION_THRESHOLD else "FAIL",
        }
    elif dimension == "refusal":
        return {
            "dimension": dimension,
            "label": "Refusal (out-of-scope)",
            "score": mean_score,
            "count": len(results),
            "passed_count": passed_count,
            "threshold": REFUSAL_THRESHOLD,
            "status": "PASS" if mean_score >= REFUSAL_THRESHOLD else "FAIL",
        }
    elif dimension == "safety_warnings":
        return {
            "dimension": dimension,
            "label": "Safety Warnings",
            "score": mean_score,
            "count": len(results),
            "passed_count": passed_count,
            "threshold": None,
            "status": "INFO",
        }
    else:
        return {
            "dimension": dimension,
            "label": dimension,
            "score": mean_score,
            "count": len(results),
            "passed_count": passed_count,
            "threshold": None,
            "status": "INFO",
        }


# ---------------------------------------------------------------------------
# Terminal reporting
# ---------------------------------------------------------------------------

def print_summary(aggregates: list[dict], overall_passed: bool) -> None:
    """Print a human-readable evaluation summary table.

    Matches the benchmark.py reporting pattern with = separators,
    aligned columns, and PASS/FAIL verdict.

    Args:
        aggregates: List of aggregate result dicts (one per dimension).
        overall_passed: Whether all thresholds were met.
    """
    print()
    print("=" * 70)
    print("EVALUATION RESULTS")
    print("=" * 70)
    print()
    print(f"  {'Dimension':<28s}  {'Score':>8s}  {'Threshold':>9s}  {'Status':>6s}")
    print(f"  {'-' * 28}  {'-' * 8}  {'-' * 9}  {'-' * 6}")

    for agg in aggregates:
        label = agg.get("label", agg["dimension"])
        score_str = f"{agg['score']:.1%}"
        threshold = agg.get("threshold")
        threshold_str = f"{threshold:.1%}" if threshold is not None else "--"
        status = agg["status"]
        print(f"  {label:<28s}  {score_str:>8s}  {threshold_str:>9s}  {status:>6s}")

    print()
    verdict = "PASSED" if overall_passed else "FAILED"
    print(f"  OVERALL: {verdict}")
    print("=" * 70)


def print_failures(all_results: list[dict]) -> None:
    """Print detailed information about failing queries.

    Highlights specific queries that did not meet expectations, with
    expected vs actual details for debugging.

    Args:
        all_results: List of all per-query result dicts across dimensions.
    """
    failures = [r for r in all_results if r.get("score", 1.0) < 1.0]
    if not failures:
        return

    print()
    print("=" * 70)
    print("FAILURES (queries scoring below 1.0)")
    print("=" * 70)

    # Group by dimension
    by_dimension: dict[str, list[dict]] = {}
    for f in failures:
        dim = f.get("dimension", "unknown")
        by_dimension.setdefault(dim, []).append(f)

    for dim, dim_failures in sorted(by_dimension.items()):
        print(f"\n  --- {dim} ({len(dim_failures)} failures) ---")
        for f in dim_failures[:10]:  # Show max 10 per dimension
            print(f"\n    Query: \"{f['query']}\"")
            print(f"    Score: {f['score']:.2f}")

            if dim == "retrieval":
                print(f"    Expected: {f.get('expected', [])}")
                print(f"    Actual:   {f.get('actual', [])}")
                print(f"    Misses:   {f.get('misses', [])}")
            elif dim == "refusal":
                print(f"    Status:   {f.get('status', 'unknown')}")
                if f.get("response_preview"):
                    print(f"    Preview:  {f['response_preview']}")
            elif dim == "citation_faithfulness":
                print(f"    Found: {f.get('citations_found', 0)}, "
                      f"Verified: {f.get('citations_verified', 0)}, "
                      f"Failed: {f.get('citations_failed', 0)}")
            elif dim == "safety_warnings":
                print(f"    Warnings found: {f.get('warnings_found', 0)}")

        if len(dim_failures) > 10:
            print(f"\n    ... and {len(dim_failures) - 10} more")

    print()


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------

def write_results(
    aggregates: list[dict],
    all_results: list[dict],
    overall_passed: bool,
) -> None:
    """Write detailed evaluation results to JSON file.

    Creates processed/eval/ directory if needed and writes a comprehensive
    results file with aggregates, per-query results, and thresholds.

    Args:
        aggregates: List of aggregate result dicts.
        all_results: List of all per-query result dicts.
        overall_passed: Whether all thresholds were met.
    """
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)

    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall_passed": overall_passed,
        "aggregates": aggregates,
        "per_query_results": all_results,
        "thresholds": {
            "retrieval": RETRIEVAL_THRESHOLD,
            "citation": CITATION_THRESHOLD,
            "refusal": REFUSAL_THRESHOLD,
        },
    }

    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nDetailed results written to: {RESULTS_PATH}")


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def main():
    """Run evaluation suite.

    Parses --suite argument, initializes pipeline, loads datasets, runs
    selected evaluation dimensions, aggregates results, prints terminal
    summary, writes JSON results, and exits with appropriate status code.
    """
    parser = argparse.ArgumentParser(
        description="SurvivalRAG evaluation runner",
        prog="python -m pipeline.evaluate",
    )
    parser.add_argument(
        "--suite",
        choices=["all", "retrieval", "refusal", "citation", "safety"],
        default="all",
        help="Evaluation suite to run (default: all)",
    )
    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    print("=" * 70)
    print("SURVIVALRAG EVALUATION SUITE")
    print("=" * 70)
    print()
    print(f"  Suite: {args.suite}")
    print()

    # Initialize pipeline
    print("Initializing pipeline...")
    init()
    print("  [OK] Pipeline initialized")

    # Check ChromaDB has documents
    try:
        count = retrieve._collection.count()
        if count == 0:
            print(
                "\n[FAIL] ChromaDB collection empty -- "
                "run corpus ingestion first"
            )
            sys.exit(1)
        print(f"  [OK] ChromaDB: {count} chunks indexed")
    except Exception as e:
        print(f"\n[FAIL] ChromaDB error: {e}")
        sys.exit(1)

    print()

    # Load datasets
    needs_golden = args.suite in ("all", "retrieval", "citation", "safety")
    needs_refusal = args.suite in ("all", "refusal")

    golden_entries = []
    refusal_entries = []

    if needs_golden:
        try:
            golden_entries = load_dataset(GOLDEN_PATH)
            print(f"  Golden dataset: {len(golden_entries)} queries loaded")
        except FileNotFoundError as e:
            print(f"\n[FAIL] {e}")
            sys.exit(1)

    if needs_refusal:
        try:
            refusal_entries = load_dataset(REFUSAL_PATH)
            print(f"  Refusal dataset: {len(refusal_entries)} queries loaded")
        except FileNotFoundError as e:
            print(f"\n[FAIL] {e}")
            sys.exit(1)

    print()

    # Pre-flight chunk ID validation
    if golden_entries:
        print("Validating chunk IDs...")
        found, total = validate_chunk_ids(golden_entries)
        if total > 0:
            print(f"  [OK] {found}/{total} expected chunk IDs found in ChromaDB")
        print()

    # Run evaluation dimensions
    all_results: list[dict] = []
    aggregates: list[dict] = []
    start_time = time.time()

    # Dimension 1: Retrieval Recall
    if args.suite in ("all", "retrieval"):
        print("Running retrieval recall evaluation...")
        retrieval_results = evaluate_retrieval(golden_entries)
        all_results.extend(retrieval_results)

        # Overall retrieval aggregate (informational)
        agg_all = aggregate_results(retrieval_results, "retrieval")
        aggregates.append(agg_all)

        # Medical terminology filtered aggregate (threshold applies here)
        medical_results = [
            r for r in retrieval_results
            if r.get("query_type") == "medical_terminology"
        ]
        agg_medical = aggregate_results(medical_results, "retrieval_medical")
        aggregates.append(agg_medical)

    # Dimension 2: Refusal
    if args.suite in ("all", "refusal"):
        print("Running refusal evaluation...")
        refusal_results = evaluate_refusal(refusal_entries)
        all_results.extend(refusal_results)
        aggregates.append(aggregate_results(refusal_results, "refusal"))

    # Dimension 3: Citation Faithfulness
    if args.suite in ("all", "citation"):
        print("Running citation faithfulness evaluation...")
        citation_results = evaluate_citation_faithfulness(golden_entries)
        all_results.extend(citation_results)
        aggregates.append(
            aggregate_results(citation_results, "citation_faithfulness")
        )

    # Dimension 4: Safety Warning Surfacing
    if args.suite in ("all", "retrieval", "safety"):
        print("Running safety warning evaluation...")
        safety_results = evaluate_safety_warnings(golden_entries)
        all_results.extend(safety_results)
        aggregates.append(
            aggregate_results(safety_results, "safety_warnings")
        )

    elapsed = time.time() - start_time

    # Compute overall pass/fail: ALL threshold-checked dimensions must pass
    threshold_results = [
        a for a in aggregates
        if a.get("threshold") is not None
    ]
    overall_passed = all(a["status"] == "PASS" for a in threshold_results)

    # If no threshold dimensions were run, consider it passed
    if not threshold_results:
        overall_passed = True

    # Print terminal summary
    print_summary(aggregates, overall_passed)

    # Print failure details if any threshold failed
    if not overall_passed:
        print_failures(all_results)

    # Write JSON results
    write_results(aggregates, all_results, overall_passed)

    print(f"\nEvaluation completed in {elapsed:.1f}s")

    # Exit with appropriate code
    sys.exit(0 if overall_passed else 1)


if __name__ == "__main__":
    main()
