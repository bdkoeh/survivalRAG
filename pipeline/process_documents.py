#!/usr/bin/env python3
"""Full document processing pipeline orchestrator.

Runs the complete pipeline: extraction (from Plan 01) + LLM-assisted
classification + dosage validation + verification reporting.

If sections already exist in processed/sections/, skips extraction and
goes straight to classification. If Ollama is not available, can run
with --skip-classification to produce extraction-only output.

Usage:
    python pipeline/process_documents.py                           # Full pipeline
    python pipeline/process_documents.py --skip-extraction         # Classify existing sections
    python pipeline/process_documents.py --skip-classification     # Extract only (no Ollama)
    python pipeline/process_documents.py --single FM-21-76         # Process single doc by ID
"""

import argparse
import logging
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is on Python path when running as script
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import yaml

from pipeline.classify import (
    check_ollama_ready,
    classify_section_with_retry,
)
from pipeline.clean import clean_text
from pipeline.extract import extract_with_fallback
from pipeline.models import SectionClassification, SectionMetadata
from pipeline.report import generate_processing_manifest, generate_report
from pipeline.split import section_to_markdown, split_into_sections
from pipeline.validate import DosageFlag, validate_dosages, validate_section_file
from pipeline.writer import apply_corrections, write_section_file

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def find_manifest(pdf_stem: str, manifest_dir: Path) -> dict | None:
    """Find and load the provenance manifest for a given PDF.

    Args:
        pdf_stem: PDF filename stem (e.g., "FM-21-76").
        manifest_dir: Directory containing YAML manifests.

    Returns:
        Parsed manifest dict, or None if no manifest found.
    """
    manifest_path = manifest_dir / f"{pdf_stem}.yaml"
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return None


def get_doc_id(pdf_stem: str, manifest: dict | None) -> str:
    """Derive a document ID from the manifest or PDF filename.

    Uses the manifest designation for military documents (e.g., "FM 21-76"
    -> "FM-21-76"). For civilian documents, uses the PDF filename stem.

    Args:
        pdf_stem: PDF filename stem.
        manifest: Parsed manifest dict, or None.

    Returns:
        Document ID string (filesystem-safe).
    """
    import re as _re

    if manifest and "document" in manifest:
        designation = manifest["document"].get("designation", "")
        if designation:
            clean_designation = designation.replace(" ", "-").replace("/", "-")
            clean_designation = _re.sub(r"-{2,}", "-", clean_designation)
            clean_designation = clean_designation.strip("-")
            if any(
                clean_designation.startswith(prefix)
                for prefix in ("FM-", "TC-", "ATP-", "ATTP-", "CALL-", "AFH-")
            ):
                return clean_designation
    return pdf_stem


def strip_yaml_front_matter(content: str) -> str:
    """Strip YAML front matter from a Markdown file's content.

    Args:
        content: Full file content including front matter.

    Returns:
        Content after the closing --- delimiter.
    """
    parts = content.split("---", 2)
    if len(parts) >= 3:
        return parts[2]
    return content


def parse_yaml_front_matter(content: str) -> dict:
    """Parse YAML front matter from a Markdown file's content.

    Args:
        content: Full file content including front matter.

    Returns:
        Parsed YAML dict, or empty dict if no front matter found.
    """
    parts = content.split("---", 2)
    if len(parts) >= 3:
        try:
            return yaml.safe_load(parts[1]) or {}
        except yaml.YAMLError:
            return {}
    return {}


def update_section_file_metadata(
    file_path: Path,
    classification: SectionClassification,
) -> None:
    """Update a section file's YAML front matter with classification results.

    Reads the file, updates the content_type, categories, warning_level,
    and warning_text fields in the YAML front matter, and writes it back.

    Args:
        file_path: Path to the section Markdown file.
        classification: Classification results from Ollama.
    """
    content = file_path.read_text(encoding="utf-8")
    parts = content.split("---", 2)

    if len(parts) < 3:
        logger.warning(f"Cannot update metadata for {file_path}: no front matter found")
        return

    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as e:
        logger.warning(f"Cannot parse front matter for {file_path}: {e}")
        return

    # Update classification fields
    meta["content_type"] = {
        "primary": classification.primary_type.value,
        "secondary": [t.value for t in classification.secondary_types],
    }
    meta["categories"] = list(classification.categories)
    meta["warning_level"] = (
        classification.warning_level.value if classification.warning_level else None
    )
    meta["warning_text"] = classification.warning_text

    # Write back
    front_matter = yaml.dump(
        meta,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
        width=120,
    )
    new_content = f"---\n{front_matter}---{parts[2]}"
    file_path.write_text(new_content, encoding="utf-8")


def default_classification() -> SectionClassification:
    """Create a default 'general' classification for short sections.

    Used for sections with < 20 characters of content, which are too
    short for meaningful LLM classification.

    Returns:
        SectionClassification with primary_type=general.
    """
    return SectionClassification(
        primary_type="general",
        secondary_types=[],
        categories=["tools"],  # safe default, min 1 required
        warning_level=None,
        warning_text=None,
        reasoning="Section too short for classification (< 20 chars)",
    )


def process_document_sections(
    doc_id: str,
    sections_dir: Path,
    corrections_dir: Path,
    reports_dir: Path,
    model: str,
    skip_classification: bool = False,
) -> dict:
    """Process all sections for a single document: classify, validate, report.

    Args:
        doc_id: Document identifier.
        sections_dir: Base directory containing document section subdirectories.
        corrections_dir: Directory containing corrections YAML files.
        reports_dir: Directory to write verification reports.
        model: Ollama model for classification.
        skip_classification: If True, skip LLM classification.

    Returns:
        Processing result dict with stats.
    """
    doc_dir = sections_dir / doc_id
    section_files = sorted(doc_dir.glob("*.md"))

    result = {
        "doc_id": doc_id,
        "sections_count": len(section_files),
        "classified_count": 0,
        "dosage_flags": [],
        "type_counts": Counter(),
        "category_counts": Counter(),
        "warnings_found": 0,
        "success": False,
        "error": None,
    }

    if not section_files:
        result["error"] = f"No section files found in {doc_dir}"
        logger.warning(result["error"])
        return result

    all_dosage_flags: list[DosageFlag] = []
    classified_count = 0
    section_file_names = [f.name for f in section_files]

    for section_file in section_files:
        try:
            content = section_file.read_text(encoding="utf-8")
            body = strip_yaml_front_matter(content)

            # Validate dosages in section content
            flags = validate_dosages(body)
            all_dosage_flags.extend(flags)

            if skip_classification:
                continue

            # Skip classification for very short sections
            if len(body.strip()) < 20:
                classification = default_classification()
                logger.debug(
                    f"Skipping classification for short section: {section_file.name}"
                )
            else:
                # Classify section with Ollama
                try:
                    classification = classify_section_with_retry(body, model=model)
                except RuntimeError as e:
                    logger.error(
                        f"Classification failed for {section_file.name}: {e}. "
                        f"Skipping section."
                    )
                    continue

            # Update section file metadata
            update_section_file_metadata(section_file, classification)
            classified_count += 1

            # Track distribution stats
            result["type_counts"][classification.primary_type.value] += 1
            for cat in classification.categories:
                result["category_counts"][cat] += 1
            if classification.warning_level:
                result["warnings_found"] += 1

        except Exception as e:
            logger.error(f"Error processing {section_file.name}: {e}")
            continue

    # Apply corrections if they exist
    corrections_file = corrections_dir / f"{doc_id}-corrections.yaml"
    corrections_applied = False
    if corrections_file.exists():
        try:
            applied = apply_corrections(corrections_file, sections_dir)
            corrections_applied = applied > 0
            logger.info(f"Applied {applied} corrections for {doc_id}")
        except Exception as e:
            logger.warning(f"Failed to apply corrections for {doc_id}: {e}")

    # Determine extraction method and page count from first section's metadata
    extraction_method = "born-digital"
    ocr_engine = None
    total_pages = 0
    if section_files:
        first_content = section_files[0].read_text(encoding="utf-8")
        first_meta = parse_yaml_front_matter(first_content)
        extraction_method = first_meta.get("extraction_method", "born-digital")
        ocr_engine = first_meta.get("ocr_engine", None)
        # Estimate page count from last section's page_start
        if len(section_files) > 0:
            last_content = section_files[-1].read_text(encoding="utf-8")
            last_meta = parse_yaml_front_matter(last_content)
            total_pages = last_meta.get("page_start", 1)

    # Generate verification report
    try:
        generate_report(
            doc_id=doc_id,
            extraction_method=extraction_method,
            ocr_engine=ocr_engine,
            total_sections=len(section_files),
            total_pages=total_pages,
            dosage_flags=all_dosage_flags,
            corrections_applied=corrections_applied,
            section_files=section_file_names,
            reports_dir=reports_dir,
        )
    except Exception as e:
        logger.error(f"Failed to generate report for {doc_id}: {e}")

    result["classified_count"] = classified_count
    result["dosage_flags"] = all_dosage_flags
    result["success"] = True

    logger.info(
        f"  -> {doc_id}: {len(section_files)} sections, "
        f"{classified_count} classified, "
        f"{len(all_dosage_flags)} dosage flags"
    )
    return result


def discover_document_dirs(sections_dir: Path) -> list[str]:
    """Discover all document directories in the sections output directory.

    Args:
        sections_dir: Base directory containing document subdirectories.

    Returns:
        Sorted list of document IDs (directory names).
    """
    doc_dirs = sorted(
        d.name
        for d in sections_dir.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    )
    logger.info(f"Discovered {len(doc_dirs)} document directories in {sections_dir}")
    return doc_dirs


def discover_pdfs(source_dir: Path) -> list[Path]:
    """Discover all PDF files in the source directory tree.

    Args:
        source_dir: Root directory containing agency subdirectories with PDFs.

    Returns:
        Sorted list of PDF file paths.
    """
    pdfs = sorted(source_dir.rglob("*.pdf"))
    logger.info(f"Discovered {len(pdfs)} PDFs in {source_dir}")
    return pdfs


def print_summary(results: list[dict], elapsed: float, skip_classification: bool) -> None:
    """Print a summary of the processing run.

    Args:
        results: List of per-document result dicts.
        elapsed: Total elapsed time in seconds.
        skip_classification: Whether classification was skipped.
    """
    total = len(results)
    successful = sum(1 for r in results if r["success"])
    failed = total - successful
    total_sections = sum(r["sections_count"] for r in results)
    total_classified = sum(r["classified_count"] for r in results)
    total_dosage_flags = sum(len(r["dosage_flags"]) for r in results)
    total_critical = sum(
        1 for r in results for f in r["dosage_flags"] if f.severity == "critical"
    )
    docs_needing_review = sum(
        1
        for r in results
        if any(f.severity == "critical" for f in r["dosage_flags"])
    )
    total_warnings = sum(r["warnings_found"] for r in results)

    # Aggregate type and category distributions
    type_totals: Counter = Counter()
    category_totals: Counter = Counter()
    for r in results:
        type_totals.update(r["type_counts"])
        category_totals.update(r["category_counts"])

    print("\n" + "=" * 60)
    print("PROCESSING SUMMARY")
    print("=" * 60)
    print(f"Total documents:         {total}")
    print(f"Successful:              {successful}")
    print(f"Failed:                  {failed}")
    print(f"Total sections:          {total_sections}")
    print(f"Sections classified:     {total_classified}")
    print(f"Elapsed time:            {elapsed:.1f}s ({elapsed/60:.1f}m)")
    print()
    print(f"Dosage flags:            {total_dosage_flags} ({total_critical} critical)")
    print(f"Documents needing review:{docs_needing_review}")
    print(f"Sections with warnings:  {total_warnings}")

    if not skip_classification and type_totals:
        print()
        print("Classification distribution:")
        for ctype, count in type_totals.most_common():
            pct = count / total_classified * 100 if total_classified else 0
            print(f"  {ctype:20s}: {count:5d} ({pct:.1f}%)")

        print()
        print("Category distribution:")
        for cat, count in category_totals.most_common():
            print(f"  {cat:20s}: {count:5d}")

    if failed > 0:
        print()
        print("Failed documents:")
        for r in results:
            if not r["success"]:
                print(f"  - {r['doc_id']}: {r.get('error', 'Unknown error')}")

    print("=" * 60)


def main():
    """Main entry point for the processing pipeline orchestrator."""
    parser = argparse.ArgumentParser(
        description="Full document processing pipeline: extract, classify, validate, report."
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path("sources/originals"),
        help="Path to source PDFs (default: sources/originals)",
    )
    parser.add_argument(
        "--manifest-dir",
        type=Path,
        default=Path("sources/manifests"),
        help="Path to provenance manifests (default: sources/manifests)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("processed/sections"),
        help="Output directory for section files (default: processed/sections)",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=Path("processed/reports"),
        help="Directory for verification reports (default: processed/reports)",
    )
    parser.add_argument(
        "--corrections-dir",
        type=Path,
        default=Path("processed/corrections"),
        help="Directory for corrections overlays (default: processed/corrections)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="llama3.1:8b",
        help="Ollama model for classification (default: llama3.1:8b)",
    )
    parser.add_argument(
        "--skip-extraction",
        action="store_true",
        help="Skip PDF extraction, only classify existing sections",
    )
    parser.add_argument(
        "--skip-classification",
        action="store_true",
        help="Skip classification, only run extraction + validation",
    )
    parser.add_argument(
        "--single",
        type=str,
        default=None,
        help="Process a single document by doc_id (e.g., FM-21-76)",
    )
    args = parser.parse_args()

    # Create output directories
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.reports_dir.mkdir(parents=True, exist_ok=True)
    args.corrections_dir.mkdir(parents=True, exist_ok=True)

    # Check Ollama availability for classification
    if not args.skip_classification:
        if not check_ollama_ready(args.model):
            print()
            print("Ollama is required for classification. Either:")
            print("  1. Start Ollama: ollama serve")
            print(f"  2. Pull model: ollama pull {args.model}")
            print("  3. Or run with --skip-classification to skip LLM classification")
            sys.exit(1)

    start_time = time.time()

    # Determine which documents to process
    if args.single:
        doc_ids = [args.single]
    elif args.skip_extraction:
        # Use existing extracted sections
        doc_ids = discover_document_dirs(args.output_dir)
    else:
        # Check if sections already exist (Plan 01 already ran)
        existing_dirs = discover_document_dirs(args.output_dir)
        if existing_dirs:
            logger.info(
                f"Found {len(existing_dirs)} existing document directories. "
                f"Skipping extraction, running classification on existing sections."
            )
            doc_ids = existing_dirs
        else:
            # Need to run extraction first
            logger.info("No existing sections found. Running extraction first...")
            pdfs = discover_pdfs(args.source_dir)
            if not pdfs:
                logger.error(f"No PDFs found in {args.source_dir}")
                sys.exit(1)

            # Import and use extract_all's processing logic
            from pipeline.extract_all import process_single_pdf

            for i, pdf_path in enumerate(pdfs, 1):
                logger.info(f"[{i}/{len(pdfs)}] Extracting {pdf_path.name}...")
                process_single_pdf(pdf_path, args.manifest_dir, args.output_dir)

            doc_ids = discover_document_dirs(args.output_dir)

    if not doc_ids:
        logger.error("No documents to process.")
        sys.exit(1)

    # Process each document: classify + validate + report
    results = []
    total_docs = len(doc_ids)

    for i, doc_id in enumerate(doc_ids, 1):
        doc_dir = args.output_dir / doc_id
        if not doc_dir.exists() or not doc_dir.is_dir():
            logger.warning(f"Document directory not found: {doc_dir}")
            continue

        logger.info(f"[{i}/{total_docs}] Processing {doc_id}...")
        result = process_document_sections(
            doc_id=doc_id,
            sections_dir=args.output_dir,
            corrections_dir=args.corrections_dir,
            reports_dir=args.reports_dir,
            model=args.model,
            skip_classification=args.skip_classification,
        )
        results.append(result)

    # Generate master processing manifest
    manifest_path = Path("processed/processing-manifest.yaml")
    try:
        generate_processing_manifest(args.reports_dir, manifest_path)
        logger.info(f"Processing manifest written to {manifest_path}")
    except Exception as e:
        logger.error(f"Failed to generate processing manifest: {e}")

    elapsed = time.time() - start_time
    print_summary(results, elapsed, args.skip_classification)


if __name__ == "__main__":
    main()
