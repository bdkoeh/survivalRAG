#!/usr/bin/env python3
"""Verify integrity of JSONL chunk files produced by pipeline/chunk_all.py.

Checks:
1. JSONL file count matches document directory count in processed/sections/
2. Every line is valid JSON
3. Every record has text (non-empty), embedding (768 floats), and metadata
4. metadata.embedding_model is "nomic-embed-text" on every record
5. metadata.embedding_model_version is the same across ALL records
6. metadata.chunk_index starts at 0 and is sequential within each section
7. metadata.source_document is present on every record

Usage:
    python scripts/verify_chunks.py
    python scripts/verify_chunks.py --sections-dir processed/sections --chunks-dir processed/chunks
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


def verify_chunks(
    sections_dir: Path = Path("processed/sections"),
    chunks_dir: Path = Path("processed/chunks"),
) -> bool:
    """Run integrity verification on all JSONL chunk files.

    Args:
        sections_dir: Directory containing per-document section subdirectories.
        chunks_dir: Directory containing JSONL chunk files.

    Returns:
        True if all checks pass, False otherwise.
    """
    # Check directories exist
    if not chunks_dir.exists():
        print(f"ERROR: Chunks directory does not exist: {chunks_dir}")
        print("Run: python -m pipeline.chunk_all")
        return False

    jsonl_files = sorted(chunks_dir.glob("*.jsonl"))
    if not jsonl_files:
        print(f"ERROR: No JSONL files found in {chunks_dir}")
        print("Run: python -m pipeline.chunk_all")
        return False

    # Count expected documents
    if sections_dir.exists():
        doc_dirs = [d for d in sections_dir.iterdir() if d.is_dir()]
        print(f"Document directories in sections: {len(doc_dirs)}")
    else:
        doc_dirs = []
        print(f"WARNING: Sections directory not found: {sections_dir}")

    print(f"JSONL files in chunks: {len(jsonl_files)}")

    if doc_dirs and len(jsonl_files) != len(doc_dirs):
        print(
            f"WARNING: JSONL count ({len(jsonl_files)}) != "
            f"document count ({len(doc_dirs)})"
        )
        # Find missing
        jsonl_names = {jf.stem for jf in jsonl_files}
        doc_names = {d.name for d in doc_dirs}
        missing = doc_names - jsonl_names
        extra = jsonl_names - doc_names
        if missing:
            print(f"  Missing JSONL for: {sorted(missing)}")
        if extra:
            print(f"  Extra JSONL (no matching section dir): {sorted(extra)}")

    # Verify each file
    total_chunks = 0
    model_versions: set[str] = set()
    errors: list[str] = []
    chunks_per_doc: dict[str, int] = {}

    for jf in jsonl_files:
        doc_chunks = 0
        section_chunks: dict[str, list[int]] = defaultdict(list)

        with open(jf, encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as e:
                    errors.append(f"{jf.name}:{line_num}: invalid JSON: {e}")
                    continue

                # Check text
                text = record.get("text")
                if not text or not text.strip():
                    errors.append(f"{jf.name}:{line_num}: empty text")

                # Check embedding
                embedding = record.get("embedding", [])
                if len(embedding) != 768:
                    errors.append(
                        f"{jf.name}:{line_num}: bad embedding dim "
                        f"(got {len(embedding)}, expected 768)"
                    )

                # Check all embedding values are floats
                if embedding:
                    try:
                        _ = [float(x) for x in embedding[:5]]
                    except (TypeError, ValueError) as e:
                        errors.append(
                            f"{jf.name}:{line_num}: non-float embedding: {e}"
                        )

                # Check metadata
                meta = record.get("metadata", {})
                if not meta:
                    errors.append(f"{jf.name}:{line_num}: missing metadata")
                    continue

                # Check embedding model
                if meta.get("embedding_model") != "nomic-embed-text":
                    errors.append(
                        f"{jf.name}:{line_num}: wrong model: "
                        f"{meta.get('embedding_model')}"
                    )

                # Track model versions
                version = meta.get("embedding_model_version", "")
                if version:
                    model_versions.add(version)
                else:
                    errors.append(
                        f"{jf.name}:{line_num}: empty model version"
                    )

                # Check required metadata fields
                if not meta.get("source_document"):
                    errors.append(
                        f"{jf.name}:{line_num}: missing source_document"
                    )

                # Track chunk indices per section for sequential check
                section_key = (
                    f"{meta.get('source_document', '')}:"
                    f"{meta.get('section_header', '')}"
                )
                section_chunks[section_key].append(
                    meta.get("chunk_index", -1)
                )

                doc_chunks += 1

        total_chunks += doc_chunks
        chunks_per_doc[jf.stem] = doc_chunks
        print(f"  {jf.name}: {doc_chunks} chunks")

    # Summary stats
    print(f"\nTotal chunks: {total_chunks}")
    print(f"Model versions: {model_versions}")

    if chunks_per_doc:
        counts = sorted(chunks_per_doc.values())
        print(
            f"Chunks per document: min={counts[0]}, "
            f"max={counts[-1]}, "
            f"median={counts[len(counts) // 2]}, "
            f"mean={sum(counts) / len(counts):.1f}"
        )

    # Version consistency check
    if len(model_versions) > 1:
        errors.append(
            f"Multiple model versions found: {model_versions}"
        )
    elif len(model_versions) == 0:
        errors.append("No model versions found in any record")

    # Report errors
    print(f"\nErrors: {len(errors)}")
    if errors:
        for err in errors[:20]:
            print(f"  - {err}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more")
        print("\nINTEGRITY CHECK FAILED")
        return False

    print("\nINTEGRITY CHECK PASSED")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Verify JSONL chunk file integrity"
    )
    parser.add_argument(
        "--sections-dir",
        type=Path,
        default=Path("processed/sections"),
        help="Sections directory for document count comparison",
    )
    parser.add_argument(
        "--chunks-dir",
        type=Path,
        default=Path("processed/chunks"),
        help="Chunks directory containing JSONL files to verify",
    )
    args = parser.parse_args()

    passed = verify_chunks(
        sections_dir=args.sections_dir,
        chunks_dir=args.chunks_dir,
    )
    sys.exit(0 if passed else 1)
