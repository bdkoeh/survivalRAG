"""Pydantic models for the document processing pipeline.

Defines schemas for content classification, section metadata,
and corrections overlay used across all pipeline modules.
"""

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ContentType(str, Enum):
    """Content type classification for document sections."""

    PROCEDURE = "procedure"
    REFERENCE_TABLE = "reference_table"
    SAFETY_WARNING = "safety_warning"
    GENERAL = "general"


class WarningLevel(str, Enum):
    """Military warning levels for safety-critical content.

    WARNING: Risk of death or serious injury.
    CAUTION: Risk of equipment damage.
    NOTE: Additional information.
    """

    WARNING = "warning"
    CAUTION = "caution"
    NOTE = "note"


# Valid content categories for section tagging (1-3 per section)
VALID_CATEGORIES = [
    "medical",
    "water",
    "shelter",
    "fire",
    "food",
    "navigation",
    "signaling",
    "tools",
    "first_aid",
]

CategoryLiteral = Literal[
    "medical",
    "water",
    "shelter",
    "fire",
    "food",
    "navigation",
    "signaling",
    "tools",
    "first_aid",
]


class SectionClassification(BaseModel):
    """Schema for Ollama structured output: content type and category classification.

    Used with Ollama's format parameter to get deterministic, parseable
    classification results from a local LLM.
    """

    primary_type: ContentType = Field(
        description="The primary content type of this section"
    )
    secondary_types: list[ContentType] = Field(
        default_factory=list,
        description="Additional content types present in this section",
    )
    categories: list[CategoryLiteral] = Field(
        min_length=1,
        max_length=3,
        description="1-3 content categories this section belongs to",
    )
    warning_level: Optional[WarningLevel] = Field(
        default=None,
        description="Military warning level if this section contains a safety warning",
    )
    warning_text: Optional[str] = Field(
        default=None,
        description="Exact text of any WARNING, CAUTION, or NOTE present",
    )
    reasoning: str = Field(
        description="Brief explanation for the classification decision"
    )


class SectionMetadata(BaseModel):
    """Metadata for YAML front matter on each extracted section file.

    Contains source document info, section position, content classification,
    extraction method details, and provenance chain.
    """

    source_document: str = Field(description="Document identifier (e.g., FM-21-76)")
    source_title: str = Field(description="Full document title")
    section_order: int = Field(description="Section order within the source document")
    section_heading: str = Field(description="Section heading text")
    page_start: int = Field(description="Starting page number in the source PDF")
    page_end: Optional[int] = Field(
        default=None, description="Ending page number (if known)"
    )
    content_type: dict = Field(
        default_factory=lambda: {"primary": "", "secondary": []},
        description="Content type classification with primary and secondary types",
    )
    categories: list[str] = Field(
        default_factory=list,
        description="Content categories (1-3 from valid category list)",
    )
    warning_level: Optional[str] = Field(
        default=None, description="Warning level if safety-critical content"
    )
    warning_text: Optional[str] = Field(
        default=None, description="Exact warning text if present"
    )
    extraction_method: str = Field(
        description="Extraction method: born-digital, tesseract, or easyocr"
    )
    ocr_engine: Optional[str] = Field(
        default=None, description="OCR engine used, if any"
    )
    processing_date: str = Field(description="ISO date of processing")
    corrections_applied: bool = Field(
        default=False, description="Whether manual corrections have been applied"
    )
    provenance: dict = Field(
        default_factory=lambda: {
            "source_url": "",
            "license": "",
            "distribution_statement": "",
        },
        description="Provenance chain: source URL, license type, distribution statement",
    )


class CorrectionEntry(BaseModel):
    """A single text correction for a section file.

    Corrections are stored separately from pipeline output to maintain
    idempotency -- re-running the pipeline does not lose human review work.
    """

    section_file: str = Field(description="Filename of the section to correct")
    type: str = Field(description="Correction type (e.g., text_replacement)")
    original: str = Field(description="Original (incorrect) text")
    corrected: str = Field(description="Corrected text")
    reason: str = Field(description="Reason for the correction")


class DocumentCorrections(BaseModel):
    """Wrapper for all corrections applied to a single source document."""

    document: str = Field(description="Document identifier")
    corrections_date: str = Field(description="ISO date corrections were made")
    corrections_by: str = Field(description="Who made the corrections")
    corrections: list[CorrectionEntry] = Field(
        default_factory=list, description="List of corrections"
    )
