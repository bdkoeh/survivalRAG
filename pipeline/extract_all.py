#!/usr/bin/env python3
"""Extraction orchestrator: processes all Tier 1 PDFs into per-section Markdown files.

Walks source PDF directories, extracts text using Docling, splits into sections,
cleans text, and writes per-section Markdown files with YAML front matter.

This script handles extraction, splitting, and cleaning only.
Classification and category tagging happen in Plan 02.

Usage:
    python pipeline/extract_all.py                           # Process all PDFs
    python pipeline/extract_all.py --single sources/originals/cdc/make-water-safe-emergency.pdf
"""

import argparse
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is on Python path when running as script
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import yaml

from pipeline.clean import clean_text
from pipeline.extract import extract_with_fallback
from pipeline.models import SectionMetadata
from pipeline.split import section_to_markdown, split_into_sections
from pipeline.writer import write_section_file

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def find_manifest(pdf_path: Path, manifest_dir: Path) -> dict | None:
    """Find and load the provenance manifest for a given PDF.

    Matches by PDF filename stem (e.g., FM-21-76.pdf -> FM-21-76.yaml).

    Args:
        pdf_path: Path to the PDF file.
        manifest_dir: Directory containing YAML manifests.

    Returns:
        Parsed manifest dict, or None if no manifest found.
    """
    stem = pdf_path.stem
    manifest_path = manifest_dir / f"{stem}.yaml"

    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    logger.warning(f"No manifest found for {pdf_path.name} (looked for {manifest_path})")
    return None


def get_doc_id(pdf_path: Path, manifest: dict | None) -> str:
    """Derive a document ID from the manifest or PDF filename.

    Uses the manifest designation for military documents (e.g., "FM 21-76"
    -> "FM-21-76") since those are well-known unique identifiers. For civilian
    documents (CDC factsheets, FEMA guides, etc.), uses the PDF filename stem
    to avoid collisions (multiple docs share designations like "CDC Factsheet").

    Args:
        pdf_path: Path to the PDF file.
        manifest: Parsed manifest dict, or None.

    Returns:
        Document ID string (filesystem-safe).
    """
    if manifest and "document" in manifest:
        designation = manifest["document"].get("designation", "")
        if designation:
            # Sanitize designation for filesystem use:
            # replace spaces and forward slashes with hyphens,
            # collapse multiple hyphens, strip edges
            import re as _re
            clean_designation = designation.replace(" ", "-").replace("/", "-")
            clean_designation = _re.sub(r"-{2,}", "-", clean_designation)
            clean_designation = clean_designation.strip("-")
            # Only use designation as doc_id for military document identifiers
            # (FM, TC, ATP, ATTP, CALL, AFH patterns). Civilian designations
            # like "CDC Factsheet" are not unique across documents.
            if any(
                clean_designation.startswith(prefix)
                for prefix in ("FM-", "TC-", "ATP-", "ATTP-", "CALL-", "AFH-")
            ):
                return clean_designation
    return pdf_path.stem


def build_section_metadata(
    doc_id: str,
    source_title: str,
    section_order: int,
    section_heading: str,
    page_start: int,
    extraction_method: str,
    ocr_engine: str | None,
    manifest: dict | None,
) -> SectionMetadata:
    """Build SectionMetadata from extraction info and manifest data.

    Content type and categories are left empty -- classification
    happens in Plan 02.

    Args:
        doc_id: Document identifier.
        source_title: Full document title.
        section_order: Section order within the document.
        section_heading: Section heading text.
        page_start: Starting page number.
        extraction_method: "born-digital", "tesseract", or "easyocr".
        ocr_engine: OCR engine used, or None for born-digital.
        manifest: Parsed manifest dict for provenance info.

    Returns:
        SectionMetadata instance.
    """
    # Extract provenance from manifest
    provenance = {
        "source_url": "",
        "license": "",
        "distribution_statement": "",
    }
    if manifest:
        source_info = manifest.get("source", {})
        licensing_info = manifest.get("licensing", {})
        provenance = {
            "source_url": source_info.get("primary_url", ""),
            "license": licensing_info.get("license_type", ""),
            "distribution_statement": licensing_info.get("distribution_statement", ""),
        }

    return SectionMetadata(
        source_document=doc_id,
        source_title=source_title,
        section_order=section_order,
        section_heading=section_heading,
        page_start=page_start,
        page_end=None,
        content_type={"primary": "", "secondary": []},
        categories=[],
        warning_level=None,
        warning_text=None,
        extraction_method=extraction_method,
        ocr_engine=ocr_engine,
        processing_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        corrections_applied=False,
        provenance=provenance,
    )


def process_single_pdf(
    pdf_path: Path,
    manifest_dir: Path,
    output_dir: Path,
) -> dict:
    """Process a single PDF through the full extraction pipeline.

    Steps: extract -> split -> clean -> write per-section Markdown files.

    Args:
        pdf_path: Path to the PDF file.
        manifest_dir: Directory containing YAML manifests.
        output_dir: Output directory for section files.

    Returns:
        Dict with processing results: doc_id, sections_count,
        extraction_method, warnings, success.
    """
    result = {
        "doc_id": pdf_path.stem,
        "pdf_path": str(pdf_path),
        "sections_count": 0,
        "extraction_method": "unknown",
        "warnings": [],
        "success": False,
    }

    # Load manifest
    manifest = find_manifest(pdf_path, manifest_dir)
    doc_id = get_doc_id(pdf_path, manifest)
    result["doc_id"] = doc_id

    # Get document title from manifest
    source_title = doc_id
    if manifest and "document" in manifest:
        source_title = manifest["document"].get("title", doc_id)

    logger.info(f"Processing: {doc_id} ({pdf_path.name})")

    # Step 1: Extract with Docling (with OCR fallback)
    try:
        doc, engine_used = extract_with_fallback(str(pdf_path))
    except RuntimeError as e:
        logger.error(f"FAILED: {doc_id} - {e}")
        result["warnings"].append(str(e))
        return result

    extraction_method = engine_used
    ocr_engine = engine_used if engine_used != "born-digital" else None
    result["extraction_method"] = extraction_method

    # Step 2: Split into sections
    sections = split_into_sections(doc, doc_id)

    if not sections:
        logger.warning(f"No sections extracted from {doc_id}")
        result["warnings"].append("No sections extracted")
        return result

    # Step 3 & 4: For each section, convert to Markdown, clean, and write
    written_files = []
    for section in sections:
        # Convert section items to Markdown
        markdown_content = section_to_markdown(section, doc)

        # Clean the Markdown text
        markdown_content = clean_text(markdown_content)

        if not markdown_content.strip():
            logger.debug(f"Skipping empty section: {section['heading']}")
            continue

        # Build metadata
        metadata = build_section_metadata(
            doc_id=doc_id,
            source_title=source_title,
            section_order=section["order"],
            section_heading=section["heading"],
            page_start=section["page_start"],
            extraction_method=extraction_method,
            ocr_engine=ocr_engine,
            manifest=manifest,
        )

        # Write section file
        filepath = write_section_file(
            output_dir=output_dir,
            doc_id=doc_id,
            section_order=section["order"],
            heading=section["heading"],
            markdown_content=markdown_content,
            metadata=metadata,
        )
        written_files.append(filepath)

    result["sections_count"] = len(written_files)
    result["success"] = True
    logger.info(
        f"  -> {doc_id}: {len(written_files)} sections, method={extraction_method}"
    )

    return result


def discover_pdfs(source_dir: Path) -> list[Path]:
    """Discover all PDF files in the source directory tree.

    Walks all subdirectories (agency directories like military/, cdc/, fema/).

    Args:
        source_dir: Root directory containing agency subdirectories with PDFs.

    Returns:
        Sorted list of PDF file paths.
    """
    pdfs = sorted(source_dir.rglob("*.pdf"))
    logger.info(f"Discovered {len(pdfs)} PDFs in {source_dir}")
    return pdfs


def print_summary(results: list[dict], elapsed: float) -> None:
    """Print a summary of the extraction run.

    Args:
        results: List of per-document result dicts.
        elapsed: Total elapsed time in seconds.
    """
    total = len(results)
    successful = sum(1 for r in results if r["success"])
    failed = sum(1 for r in results if not r["success"])
    total_sections = sum(r["sections_count"] for r in results)

    # Count extraction methods
    methods = {}
    for r in results:
        if r["success"]:
            m = r["extraction_method"]
            methods[m] = methods.get(m, 0) + 1

    print("\n" + "=" * 60)
    print("EXTRACTION SUMMARY")
    print("=" * 60)
    print(f"Total documents:     {total}")
    print(f"Successful:          {successful}")
    print(f"Failed:              {failed}")
    print(f"Total sections:      {total_sections}")
    print(f"Elapsed time:        {elapsed:.1f}s")
    print()
    print("Extraction methods:")
    for method, count in sorted(methods.items()):
        print(f"  {method}: {count} documents")

    if failed > 0:
        print()
        print("Failed documents:")
        for r in results:
            if not r["success"]:
                warnings = "; ".join(r["warnings"]) if r["warnings"] else "Unknown error"
                print(f"  - {r['doc_id']}: {warnings}")

    # Documents with warnings but successful
    warned = [r for r in results if r["success"] and r["warnings"]]
    if warned:
        print()
        print("Warnings:")
        for r in warned:
            for w in r["warnings"]:
                print(f"  - {r['doc_id']}: {w}")

    print("=" * 60)


def main():
    """Main entry point for the extraction orchestrator."""
    parser = argparse.ArgumentParser(
        description="Extract all Tier 1 PDFs into per-section Markdown files."
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
        "--single",
        type=Path,
        default=None,
        help="Process a single PDF by path (for testing/debugging)",
    )
    args = parser.parse_args()

    # Create output directories
    args.output_dir.mkdir(parents=True, exist_ok=True)
    Path("processed/corrections").mkdir(parents=True, exist_ok=True)
    Path("processed/reports").mkdir(parents=True, exist_ok=True)

    start_time = time.time()

    if args.single:
        # Process a single PDF
        if not args.single.exists():
            logger.error(f"File not found: {args.single}")
            sys.exit(1)
        results = [
            process_single_pdf(args.single, args.manifest_dir, args.output_dir)
        ]
    else:
        # Discover and process all PDFs
        pdfs = discover_pdfs(args.source_dir)
        if not pdfs:
            logger.error(f"No PDFs found in {args.source_dir}")
            sys.exit(1)

        results = []
        for i, pdf_path in enumerate(pdfs, 1):
            logger.info(f"[{i}/{len(pdfs)}] Processing {pdf_path.name}...")
            result = process_single_pdf(pdf_path, args.manifest_dir, args.output_dir)
            results.append(result)

    elapsed = time.time() - start_time
    print_summary(results, elapsed)

    # Exit with error code if any documents failed
    failed_count = sum(1 for r in results if not r["success"])
    if failed_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
