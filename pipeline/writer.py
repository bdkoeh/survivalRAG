"""Markdown file writer with YAML front matter from section metadata.

Writes per-section Markdown files with provenance metadata, and applies
corrections from a separate YAML overlay for pipeline idempotency.
"""

import logging
import re
from pathlib import Path

import yaml

from pipeline.models import DocumentCorrections, SectionMetadata

logger = logging.getLogger(__name__)


def slugify(text: str) -> str:
    """Convert heading text to a filesystem-safe slug.

    - Lowercase
    - Replace non-alphanumeric characters with hyphens
    - Collapse multiple hyphens
    - Truncate to 50 characters
    - Strip leading/trailing hyphens

    Args:
        text: Heading text to slugify.

    Returns:
        Filesystem-safe slug string.
    """
    slug = text.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = re.sub(r"-{2,}", "-", slug)
    slug = slug[:50]
    slug = slug.strip("-")
    return slug or "untitled"


def write_section_file(
    output_dir: Path,
    doc_id: str,
    section_order: int,
    heading: str,
    markdown_content: str,
    metadata: SectionMetadata,
) -> Path:
    """Write a single section as a Markdown file with YAML front matter.

    File naming convention: {doc_id}_{order:03d}_{slugified_heading}.md
    Example: FM-21-76_001_survival-medicine.md

    Args:
        output_dir: Base output directory for section files.
        doc_id: Document identifier (e.g., "FM-21-76").
        section_order: Section order number (0-indexed).
        heading: Section heading text.
        markdown_content: Cleaned Markdown content for the section.
        metadata: SectionMetadata with provenance and extraction info.

    Returns:
        Path to the written file.
    """
    # Create document-specific subdirectory
    doc_dir = output_dir / doc_id
    doc_dir.mkdir(parents=True, exist_ok=True)

    # Build filename
    slug = slugify(heading)
    filename = f"{doc_id}_{section_order:03d}_{slug}.md"
    filepath = doc_dir / filename

    # Serialize metadata to YAML front matter
    meta_dict = metadata.model_dump()
    front_matter = yaml.dump(
        meta_dict,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
        width=120,
    )

    # Write file with YAML front matter + content
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("---\n")
        f.write(front_matter)
        f.write("---\n\n")
        f.write(markdown_content)
        f.write("\n")

    logger.debug(f"Wrote section file: {filepath}")
    return filepath


def apply_corrections(corrections_path: Path, sections_dir: Path) -> int:
    """Apply text corrections from a YAML overlay to section files.

    Corrections are stored separately from pipeline output so the pipeline
    can be re-run without losing human review work. Each correction specifies
    a section file, the original text, and the corrected replacement.

    Args:
        corrections_path: Path to the corrections YAML file.
        sections_dir: Base directory containing section files.

    Returns:
        Count of corrections successfully applied.
    """
    if not corrections_path.exists():
        logger.warning(f"Corrections file not found: {corrections_path}")
        return 0

    with open(corrections_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    doc_corrections = DocumentCorrections.model_validate(raw)
    applied_count = 0

    for correction in doc_corrections.corrections:
        # Find the section file
        section_path = sections_dir / doc_corrections.document / correction.section_file
        if not section_path.exists():
            logger.warning(
                f"Section file not found for correction: {section_path}"
            )
            continue

        # Read, apply replacement, write back
        content = section_path.read_text(encoding="utf-8")
        if correction.original in content:
            content = content.replace(correction.original, correction.corrected, 1)
            section_path.write_text(content, encoding="utf-8")

            # Update corrections_applied flag in front matter
            if "corrections_applied: false" in content:
                content = content.replace(
                    "corrections_applied: false", "corrections_applied: true"
                )
                section_path.write_text(content, encoding="utf-8")

            applied_count += 1
            logger.info(
                f"Applied correction to {section_path.name}: "
                f"{correction.reason}"
            )
        else:
            logger.warning(
                f"Original text not found in {section_path.name}: "
                f"'{correction.original[:50]}...'"
            )

    logger.info(
        f"Applied {applied_count}/{len(doc_corrections.corrections)} "
        f"corrections for {doc_corrections.document}"
    )
    return applied_count
