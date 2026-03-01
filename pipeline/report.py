"""Per-document verification report generator.

Creates YAML verification reports for each processed document and a master
processing manifest summarizing the status of all documents. Reports track
extraction method, dosage flags, classification status, and corrections.

Per user decision: "Lightweight verification report per document."
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

import yaml

from pipeline.validate import DosageFlag

logger = logging.getLogger(__name__)


def generate_report(
    doc_id: str,
    extraction_method: str,
    ocr_engine: str | None,
    total_sections: int,
    total_pages: int,
    dosage_flags: list[DosageFlag],
    corrections_applied: bool,
    section_files: list[str],
    reports_dir: Path,
) -> Path:
    """Generate and write a YAML verification report for a document.

    The report tracks extraction method, dosage validation results,
    classification status, and corrections applied. Status is determined
    by the presence of critical dosage flags:
    - "clean": No critical flags -- document is ready for use
    - "needs_review": Has critical flags -- human review required

    Args:
        doc_id: Document identifier (e.g., "FM-21-76").
        extraction_method: "born-digital", "tesseract", or "easyocr".
        ocr_engine: OCR engine used, or None for born-digital.
        total_sections: Number of sections extracted.
        total_pages: Number of pages in the source PDF.
        dosage_flags: List of DosageFlag from validation.
        corrections_applied: Whether corrections overlay was applied.
        section_files: List of section filenames produced.
        reports_dir: Directory to write the report to.

    Returns:
        Path to the written report YAML file.
    """
    reports_dir.mkdir(parents=True, exist_ok=True)

    critical_flags = [f for f in dosage_flags if f.severity == "critical"]

    report = {
        "document": doc_id,
        "extraction_method": extraction_method,
        "ocr_engine": ocr_engine,
        "total_sections": total_sections,
        "total_pages": total_pages,
        "dosage_flags_count": len(dosage_flags),
        "critical_flags_count": len(critical_flags),
        "flagged_items": [
            {
                "text": f.text,
                "line": f.line_number,
                "reason": f.reason,
                "severity": f.severity,
            }
            for f in dosage_flags
        ],
        "sections_classified": total_sections,
        "corrections_applied": corrections_applied,
        "processing_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "status": "clean" if len(critical_flags) == 0 else "needs_review",
    }

    report_path = reports_dir / f"{doc_id}-report.yaml"
    with open(report_path, "w", encoding="utf-8") as f:
        yaml.dump(
            report,
            f,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
            width=120,
        )

    logger.info(
        f"Report for {doc_id}: {report['status']} "
        f"({len(dosage_flags)} flags, {len(critical_flags)} critical)"
    )
    return report_path


def generate_processing_manifest(
    reports_dir: Path, output_path: Path
) -> dict:
    """Generate a master processing manifest from individual reports.

    Reads all individual document reports and creates a summary manifest
    with aggregate statistics and document status lists.

    Args:
        reports_dir: Directory containing per-document report YAML files.
        output_path: Path to write the processing manifest.

    Returns:
        The manifest dict.
    """
    report_files = sorted(reports_dir.glob("*-report.yaml"))

    total_documents = 0
    total_sections = 0
    documents_needing_review: list[str] = []
    documents_clean: list[str] = []

    for report_file in report_files:
        try:
            with open(report_file, "r", encoding="utf-8") as f:
                report = yaml.safe_load(f)

            total_documents += 1
            total_sections += report.get("total_sections", 0)

            doc_id = report.get("document", report_file.stem.replace("-report", ""))
            status = report.get("status", "unknown")

            if status == "needs_review":
                documents_needing_review.append(doc_id)
            else:
                documents_clean.append(doc_id)

        except Exception as e:
            logger.warning(f"Failed to read report {report_file}: {e}")

    manifest = {
        "total_documents": total_documents,
        "total_sections": total_sections,
        "documents_needing_review": documents_needing_review,
        "documents_clean": documents_clean,
        "documents_needing_review_count": len(documents_needing_review),
        "documents_clean_count": len(documents_clean),
        "processing_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(
            manifest,
            f,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
            width=120,
        )

    logger.info(
        f"Processing manifest: {total_documents} documents, "
        f"{total_sections} sections, "
        f"{len(documents_needing_review)} needing review"
    )
    return manifest
