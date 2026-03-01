"""Section splitting module using Docling iterate_items() with heading detection.

Walks the DoclingDocument structure, splits at section headers, and converts
each section to Markdown. Handles edge cases: untitled first sections,
documents with no section headers, and mixed content types.
"""

import logging
from typing import Any

from docling_core.types.doc import DoclingDocument, TableItem, TextItem

logger = logging.getLogger(__name__)


def _get_page_number(item: Any) -> int:
    """Extract page number from a Docling item.

    Checks item.prov (list of ProvenanceItem) for page numbers.
    Defaults to 1 if page information is unavailable.

    Args:
        item: A Docling document item (TextItem, TableItem, etc.)

    Returns:
        Page number (1-indexed).
    """
    if hasattr(item, "prov") and item.prov:
        for prov in item.prov:
            if hasattr(prov, "page_no"):
                return prov.page_no
    return 1


def split_into_sections(
    doc: DoclingDocument, source_doc_id: str
) -> list[dict]:
    """Split a DoclingDocument into sections based on section headers.

    Walks the document structure using iterate_items(). When a section
    header is encountered, the current section is saved and a new one
    begins. Handles edge cases:
    - Untitled first section (before any header): labeled "Untitled"
    - Documents with no headers: entire document is one section
    - Empty sections (header with no content): skipped

    Args:
        doc: DoclingDocument from Docling extraction.
        source_doc_id: Document identifier for logging.

    Returns:
        List of section dicts with keys: heading, items, page_start, order.
    """
    sections: list[dict] = []
    current_section: dict = {
        "heading": "Untitled",
        "items": [],
        "page_start": 1,
        "order": 0,
    }

    for item, level in doc.iterate_items():
        label = getattr(item, "label", None)

        # Check if this item is a section header
        if label and "section_header" in str(label).lower():
            # Save current section if it has content
            if current_section["items"]:
                sections.append(current_section)

            # Start new section
            heading_text = item.text if hasattr(item, "text") else "Untitled"
            current_section = {
                "heading": heading_text,
                "items": [],
                "page_start": _get_page_number(item),
                "order": len(sections),
            }
        else:
            current_section["items"].append(item)

    # Save the last section if it has content
    if current_section["items"]:
        sections.append(current_section)

    # Handle edge case: document with no sections at all
    if not sections:
        logger.warning(
            f"Document {source_doc_id} produced no sections. "
            f"Creating a single section from the full document."
        )
        # Try to get full text as a fallback
        full_text = doc.export_to_markdown()
        if full_text.strip():
            sections.append(
                {
                    "heading": "Full Document",
                    "items": [],
                    "page_start": 1,
                    "order": 0,
                    "_fallback_text": full_text,
                }
            )

    logger.info(
        f"Split {source_doc_id} into {len(sections)} sections"
    )
    return sections


def section_to_markdown(section: dict, doc: DoclingDocument) -> str:
    """Convert a section's items to Markdown text.

    Handles TextItem (plain text), TableItem (exported as Markdown table
    via pandas), and other items with a .text attribute.

    Args:
        section: Section dict from split_into_sections().
        doc: The parent DoclingDocument (needed for table export).

    Returns:
        Markdown string for the section content.
    """
    # Handle fallback sections (created when iterate_items produced nothing)
    if "_fallback_text" in section:
        return section["_fallback_text"]

    parts = [f"## {section['heading']}\n"]

    for item in section["items"]:
        if isinstance(item, TextItem):
            parts.append(item.text)
        elif isinstance(item, TableItem):
            try:
                table_df = item.export_to_dataframe(doc=doc)
                parts.append(table_df.to_markdown())
            except Exception as e:
                logger.warning(
                    f"Failed to export table to Markdown: {e}. "
                    f"Falling back to text representation."
                )
                if hasattr(item, "text") and item.text:
                    parts.append(item.text)
        elif hasattr(item, "text") and item.text:
            parts.append(item.text)

    return "\n\n".join(parts)
