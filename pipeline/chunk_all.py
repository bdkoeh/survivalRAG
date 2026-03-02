"""Full corpus chunking and embedding orchestrator.

Reads all section files in processed/sections/, chunks them using content-type-
aware strategies (pipeline.chunk), embeds them with nomic-embed-text
(pipeline.embed), and writes per-document JSONL output to processed/chunks/.

This is the final step of Phase 3: the output is the complete set of JSONL files
that Phase 4 will load into ChromaDB.

Pre-flight checks:
- Verifies Ollama is running and nomic-embed-text is available
- Verifies the embedding benchmark has passed (unless --skip-benchmark-check)
- Records model version for metadata consistency (CHNK-07)

Error handling:
- Individual document failures are logged and skipped (pipeline continues)
- If ALL documents fail, exits with error
- Failed documents are reported in the final summary
"""

import json
import logging
from pathlib import Path

from pipeline.chunk import chunk_document
from pipeline.embed import embed_chunk_records, get_model_version

logger = logging.getLogger(__name__)

# Path constants
SECTIONS_DIR = Path("processed/sections")
CHUNKS_DIR = Path("processed/chunks")
BENCHMARK_RESULTS = Path("processed/benchmark/results.json")


def process_corpus(
    sections_dir: Path = SECTIONS_DIR,
    chunks_dir: Path = CHUNKS_DIR,
    skip_benchmark_check: bool = False,
) -> dict:
    """Process the full corpus: chunk all sections and embed with nomic-embed-text.

    Step 0: Pre-flight checks (Ollama running, benchmark passed, model version)
    Step 1: Discover document directories in sections_dir
    Step 2: For each document: chunk -> embed -> write JSONL
    Step 3: Print summary report

    Args:
        sections_dir: Directory containing per-document section subdirectories.
        chunks_dir: Output directory for JSONL files.
        skip_benchmark_check: If True, skip benchmark pass verification
            (for development only).

    Returns:
        Summary dict with documents_processed, total_chunks, total_sections,
        errors, model_version, and jsonl_files_written.
    """
    # ---- Step 0: Pre-flight checks ----
    logger.info("Starting corpus processing pre-flight checks...")

    # Verify Ollama is running and nomic-embed-text is available
    try:
        model_version = get_model_version()
        logger.info("Model version: %s", model_version)
    except (ConnectionError, RuntimeError) as e:
        print(f"ERROR: {e}")
        raise

    # Verify benchmark has passed
    if not skip_benchmark_check:
        if not BENCHMARK_RESULTS.exists():
            msg = (
                "Benchmark has not been run. "
                "Run `python -m pipeline.benchmark` first."
            )
            print(f"ERROR: {msg}")
            raise RuntimeError(msg)

        with open(BENCHMARK_RESULTS) as f:
            benchmark = json.load(f)

        if not benchmark.get("passed"):
            msg = (
                "Benchmark has not passed. "
                "Run `python -m pipeline.benchmark` first."
            )
            print(f"ERROR: {msg}")
            raise RuntimeError(msg)

        logger.info(
            "Benchmark passed: Recall@5 = %.2f%%",
            benchmark.get("recall_at_5", 0) * 100,
        )

    # Create output directory
    chunks_dir.mkdir(parents=True, exist_ok=True)
    gitkeep = chunks_dir / ".gitkeep"
    if not gitkeep.exists():
        gitkeep.touch()

    # ---- Step 1: Discover documents ----
    doc_dirs = sorted(
        [d for d in sections_dir.iterdir() if d.is_dir()],
        key=lambda d: d.name,
    )

    if not doc_dirs:
        msg = f"No document directories found in {sections_dir}"
        print(f"ERROR: {msg}")
        raise RuntimeError(msg)

    logger.info("Found %d documents to process", len(doc_dirs))

    # ---- Step 2: Process each document ----
    total_sections = 0
    total_chunks = 0
    documents_processed = 0
    jsonl_files_written = 0
    errors: list[dict] = []

    for doc_dir in doc_dirs:
        doc_id = doc_dir.name

        try:
            # Count section files for stats
            section_files = list(doc_dir.glob("*.md"))
            n_sections = len(section_files)
            total_sections += n_sections

            # Chunk the document
            chunks = chunk_document(doc_dir)

            if not chunks:
                logger.warning("No chunks produced for %s -- skipping", doc_id)
                continue

            # Embed the chunks
            chunks = embed_chunk_records(chunks, model="nomic-embed-text")

            # Write JSONL output
            output_path = chunks_dir / f"{doc_id}.jsonl"
            n_chunks = len(chunks)

            with open(output_path, "w", encoding="utf-8") as f:
                for record in chunks:
                    record_dict = record.model_dump()

                    # Convert numpy arrays to Python lists if needed
                    embedding = record_dict.get("embedding", [])
                    if hasattr(embedding, "tolist"):
                        record_dict["embedding"] = embedding.tolist()
                    else:
                        # Ensure all floats are Python native (not numpy float32)
                        record_dict["embedding"] = [
                            float(x) for x in embedding
                        ]

                    f.write(json.dumps(record_dict, default=str) + "\n")

            total_chunks += n_chunks
            documents_processed += 1
            jsonl_files_written += 1

            logger.info(
                "Processed %s: %d sections -> %d chunks",
                doc_id,
                n_sections,
                n_chunks,
            )

        except Exception as e:
            error_info = {"document": doc_id, "error": str(e)}
            errors.append(error_info)
            logger.error("Error processing %s: %s", doc_id, e)

    # ---- Step 3: Summary report ----
    summary = {
        "documents_processed": documents_processed,
        "total_sections": total_sections,
        "total_chunks": total_chunks,
        "jsonl_files_written": jsonl_files_written,
        "embedding_model": "nomic-embed-text",
        "embedding_model_version": model_version,
        "output_directory": str(chunks_dir),
        "errors": errors,
    }

    print("\n=== Corpus Processing Complete ===")
    print(f"Documents processed: {documents_processed}")
    print(f"Total sections read: {total_sections}")
    print(f"Total chunks produced: {total_chunks}")
    print(f"Total JSONL files written: {jsonl_files_written}")
    print(f"Embedding model: nomic-embed-text")
    print(f"Embedding model version: {model_version}")
    print(f"Output directory: {chunks_dir}/")

    if errors:
        print(f"Errors: {len(errors)}")
        for err in errors:
            print(f"  - {err['document']}: {err['error']}")
    else:
        print("Errors: 0")

    # If ALL documents failed, that's a fatal error
    if documents_processed == 0 and doc_dirs:
        msg = "All documents failed to process"
        print(f"\nFATAL: {msg}")
        raise RuntimeError(msg)

    return summary


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Chunk and embed the full corpus"
    )
    parser.add_argument(
        "--skip-benchmark-check",
        action="store_true",
        help="Skip benchmark pass verification (for development only)",
    )
    parser.add_argument(
        "--sections-dir",
        type=Path,
        default=SECTIONS_DIR,
        help="Input sections directory",
    )
    parser.add_argument(
        "--chunks-dir",
        type=Path,
        default=CHUNKS_DIR,
        help="Output chunks directory",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    results = process_corpus(
        sections_dir=args.sections_dir,
        chunks_dir=args.chunks_dir,
        skip_benchmark_check=args.skip_benchmark_check,
    )

    if results.get("errors"):
        print(f"\nWARNING: {len(results['errors'])} document(s) had errors")
        sys.exit(1 if results.get("documents_processed", 0) == 0 else 0)
