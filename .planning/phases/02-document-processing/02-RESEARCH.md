# Phase 2: Document Processing - Research

**Researched:** 2026-02-28
**Domain:** PDF text extraction, OCR, text cleaning, content classification, category tagging
**Confidence:** HIGH

## Summary

Phase 2 transforms raw Tier 1 PDFs from Phase 1 into clean, classified, category-tagged Markdown sections ready for chunking in Phase 3. The pipeline has four stages: (1) PDF text extraction using Docling with automatic born-digital vs. scanned detection, (2) OCR with Tesseract (primary) and EasyOCR (fallback) for scanned pages, (3) text cleaning to strip headers, footers, page numbers, watermarks, and OCR artifacts, and (4) LLM-assisted classification and category tagging via Ollama.

Docling v2.75.0 (MIT, LF AI & Data Foundation, 42K+ GitHub stars, 1.5M+ monthly PyPI downloads) is the locked choice for extraction. It natively outputs Markdown, detects and removes page headers/footers, reconstructs tables via its TableFormer model, and provides a structured `DoclingDocument` API for iterating sections. The biggest risk is OCR quality on older scanned military PDFs -- Docling's OCR is the most expensive operation and results on degraded scans can be disappointing. The user decision to exclude documents with poor OCR rather than attempt heroic recovery is critical for maintaining data quality.

For content classification and category tagging, the pipeline uses Ollama's structured output capability (JSON schema via Pydantic models, `format` parameter) to get deterministic, parseable results from a local LLM. Llama 3.1 8B (the project's default model per DEPL-03) can handle zero-shot classification with constrained output reliably.

**Primary recommendation:** Build a Python pipeline script that processes each source PDF through Docling, splits output by section using `iterate_items()`, runs regex-based dosage/measurement validation on medical content, classifies and tags each section via Ollama, and writes per-section Markdown files with YAML front matter containing metadata. Manual corrections are stored in separate YAML files and applied as a post-processing step for idempotency.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Lean on Docling, not a bespoke review process.** Modern PDF-to-Markdown converters handle most extraction quality. Born-digital PDFs (majority of Tier 1 from .mil/.gov) won't need OCR at all.
- **Scanned PDFs: Tesseract first, EasyOCR fallback.** Docling supports both backends. Try Tesseract, fall back to EasyOCR for degraded pages.
- **Auto-flag critical fields with regex.** After extraction, pattern-match for dosages (numbers + units: mg, mL, cc, gr, etc.) and measurements. Log anomalies (implausible values, garbled text adjacent to numbers) for human spot-check.
- **Poor OCR quality = exclude the document.** If neither OCR engine produces reliable text, drop the document. Better no answer than a wrong one.
- **Lightweight verification report per document.** Log: extraction method used (born-digital vs OCR engine), pages flagged for review, any corrections applied, confidence notes.
- **LLM-assisted classification.** Run each section through a local LLM (via Ollama) to classify content type. Requires Ollama running during the processing pipeline.
- **Four content types:** `procedure`, `reference_table`, `safety_warning`, `general`.
- **Multi-type: keep section intact, tag both.** A procedure with an embedded WARNING stays as one section. Classified as primary=`procedure` with secondary types (e.g., `safety_warning`). Warning text is also captured in metadata so it surfaces even when this specific section isn't the top retrieval result (feeds CHNK-04 in Phase 3).
- **Preserve all three military warning levels:** `warning` (risk of death/serious injury), `caution` (risk of equipment damage), `note` (additional information). Stored as a sub-level on `safety_warning` classifications.
- **Non-actionable content (introductions, historical context, narrative) -> `general`.** No filtering or exclusion at this stage.
- **Multiple categories allowed per section (1-3).** A section on water purification tablets with dosage instructions gets tagged `[water, medical]`. Improves retrieval coverage.
- **LLM per section for category assignment.** Same approach as content type classification -- run through local LLM.
- **Starting taxonomy (9 categories):** `medical`, `water`, `shelter`, `fire`, `food`, `navigation`, `signaling`, `tools`, `first_aid`.
- **Taxonomy is extensible after first pass.** After initial processing, review what content falls into ambiguous buckets. Decide then whether to add categories like `hygiene`, `general_survival`, `psychology`, etc. The taxonomy isn't permanently locked -- but it's locked for the initial processing run.
- **`medical` and `first_aid` are distinct categories.** `first_aid` = immediate emergency treatment (bleeding control, CPR, splinting, shock). `medical` = broader medical knowledge (diseases, medications, dosages, ongoing care, preventive medicine).
- **Markdown files.** Docling outputs Markdown natively. Standard format for LLM consumption. Human-readable for review and correction.
- **Split output by section.** Every major section of a source document becomes its own file. Aligns with per-section classification/tagging. Creates more files but feeds directly into Phase 3 chunking.
- **File naming convention:** TBD by planner -- must encode source document, section order, and be sortable.
- **Tables preserved as-is from Docling.** Docling's TableFormer model extracts tables. No custom table processing layer. Whatever format Docling produces (typically Markdown tables) is kept.
- **Idempotent pipeline.** The processing pipeline can be re-run on the same source PDFs and produce identical output. Manual corrections are stored in a separate corrections layer (e.g., a corrections YAML per document) and applied as a post-processing step. This allows pipeline improvements without losing human review work.

### Claude's Discretion
- File naming convention details (must encode source document, section order, and be sortable)
- Specific pipeline script structure and organization
- Regex patterns for dosage/measurement validation
- Prompt templates for LLM classification
- Verification report format

### Deferred Ideas (OUT OF SCOPE)
- Extended taxonomy categories (hygiene, general_survival, psychology) -- revisit after first processing pass
- Custom table processing for complex merged-cell tables -- only if Docling output proves insufficient
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PROC-01 | PDF text extraction handles both born-digital and scanned documents | Docling v2.75.0 auto-detects born-digital vs scanned via bitmap_area_threshold; supports Tesseract and EasyOCR backends; force_full_page_ocr option for fully scanned PDFs |
| PROC-02 | OCR output for scanned documents is human-reviewed for Tier 1 medical content -- zero corrupted dosages, measurements, or safety warnings | Regex-based auto-flagging of dosage patterns (numbers + units); verification report per document; corrections YAML overlay for human fixes; exclude-on-failure policy |
| PROC-03 | Extracted text is cleaned of headers/footers, page numbers, watermarks, and OCR artifacts | Docling natively detects and excludes page headers/footers (ContentLayer.FURNITURE); additional regex cleaning for OCR artifacts, stray characters, page number patterns |
| PROC-04 | Each text section is classified by content type: procedure, reference_table, safety_warning, or general | Ollama structured output with Pydantic schema; JSON-constrained classification with temperature=0; multi-type support via primary + secondary classification |
| PROC-05 | Each text section is tagged with a content category (medical, water, shelter, fire, food, navigation, signaling, tools, first_aid) | Ollama structured output with Literal type constraints; 1-3 categories per section; same Pydantic pattern as PROC-04 |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| docling | 2.75.0 | PDF text extraction, table recognition, OCR orchestration, Markdown export | MIT, LF AI Foundation project, 42K+ GitHub stars, 1.5M monthly downloads, native header/footer removal, TableFormer table extraction |
| ollama (Python) | 0.6.1 | LLM-assisted content classification and category tagging | Official Ollama Python client, structured output with Pydantic, JSON schema constraints |
| pydantic | >=2.0 | Schema definition for classification output, corrections YAML validation | Standard for data validation in Python, required by both Docling and Ollama client |
| pyyaml | >=6.0 | Read/write YAML front matter for section files, corrections overlay, verification reports | Standard YAML library for Python |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| docling[tesserocr] | (extra) | Tesseract OCR backend | Primary OCR engine for scanned pages |
| docling[easyocr] | (extra) | EasyOCR backend | Fallback when Tesseract produces poor results |
| tesseract-ocr | >=5.0 | System-level Tesseract binary | Required by tesserocr Python binding |
| regex (re module) | stdlib | Dosage/measurement pattern matching, OCR artifact detection | Post-extraction validation of medical content |
| pathlib | stdlib | File path management | All file I/O operations |
| json | stdlib | Structured output parsing from Ollama | Parse LLM classification responses |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Docling | PyMuPDF4LLM | Faster but no built-in table structure recognition or OCR orchestration; less section-aware |
| Docling | marker-pdf | Good quality but less ecosystem integration; no built-in header/footer detection |
| Tesseract | RapidOCR | ONNX-based, possibly faster; less battle-tested than Tesseract for English military documents |
| Ollama structured output | Regex-based classification | No LLM needed but brittle; military documents have non-standard formatting that would break rule-based classification |

**Installation:**
```bash
# Core processing dependencies
pip install "docling[tesserocr,easyocr]" pyyaml ollama

# System dependency: Tesseract OCR engine
# Windows: Download installer from https://github.com/UB-Mannheim/tesseract/wiki
# macOS: brew install tesseract leptonica pkg-config
# Debian/Ubuntu: apt-get install tesseract-ocr tesseract-ocr-eng libtesseract-dev libleptonica-dev

# CPU-only PyTorch (if no GPU, saves disk space):
pip install docling --extra-index-url https://download.pytorch.org/whl/cpu

# Ollama must be running with a model loaded:
# ollama pull llama3.1:8b
```

## Architecture Patterns

### Recommended Project Structure
```
pipeline/
  process_documents.py      # Main processing orchestrator
  extract.py                # Docling PDF extraction logic
  clean.py                  # Text cleaning and artifact removal
  classify.py               # LLM-based content type + category classification
  validate.py               # Dosage/measurement regex validation
  report.py                 # Verification report generation
  models.py                 # Pydantic models for classification schemas

sources/
  originals/                # Phase 1 output: raw PDFs
    military/
    fema/
    cdc/
  manifests/                # Phase 1 output: YAML provenance manifests

processed/
  sections/                 # Output: per-section Markdown files with YAML front matter
    FM-21-76/
      FM-21-76_001_survival-medicine.md
      FM-21-76_002_water-procurement.md
      ...
    are-you-ready/
      are-you-ready_001_introduction.md
      ...
  corrections/              # Human corrections YAML overlay per document
    FM-21-76-corrections.yaml
    TC-4-02-1-corrections.yaml
  reports/                  # Per-document verification reports
    FM-21-76-report.yaml
    are-you-ready-report.yaml
  processing-manifest.yaml  # Master log of all processed documents
```

### Pattern 1: Docling PDF Extraction with OCR Fallback
**What:** Extract text from PDF using Docling, automatically handling born-digital and scanned pages.
**When to use:** Every source PDF in the pipeline.
**Example:**
```python
# Source: Docling official docs + pipeline options reference
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    TesseractOcrOptions,
    EasyOcrOptions,
    TableFormerMode,
)
from docling.datamodel.base_models import InputFormat

def create_converter(ocr_backend="tesseract"):
    """Create a Docling converter with appropriate OCR settings."""
    pipeline_options = PdfPipelineOptions(
        do_ocr=True,
        do_table_structure=True,
    )

    # Table extraction: use ACCURATE mode for military reference tables
    pipeline_options.table_structure_options.mode = TableFormerMode.ACCURATE

    # OCR backend selection
    if ocr_backend == "tesseract":
        pipeline_options.ocr_options = TesseractOcrOptions(
            lang=["eng"],
        )
    elif ocr_backend == "easyocr":
        pipeline_options.ocr_options = EasyOcrOptions(
            lang=["en"],
            use_gpu=False,  # CPU-only for reproducibility
        )

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options,
            )
        }
    )
    return converter


def extract_document(pdf_path: str, ocr_backend="tesseract"):
    """Extract a PDF, falling back to alternate OCR if needed."""
    converter = create_converter(ocr_backend)
    result = converter.convert(pdf_path)
    return result.document
```

### Pattern 2: Iterate Sections and Export Per-Section Markdown
**What:** Walk the DoclingDocument structure, split by section headers, export each section as a Markdown file.
**When to use:** After extraction, before classification.
**Example:**
```python
# Source: Docling DoclingDocument reference + iterate_items API
from docling_core.types.doc import TextItem, TableItem

def split_into_sections(doc, source_doc_id: str):
    """
    Split a DoclingDocument into sections based on section headers.
    Returns list of dicts with section text, metadata, and order index.
    """
    sections = []
    current_section = {
        "heading": "Untitled",
        "items": [],
        "page_start": 1,
        "order": 0,
    }

    for item, level in doc.iterate_items():
        label = getattr(item, "label", None)
        if label and "section_header" in str(label).lower():
            # Save current section if it has content
            if current_section["items"]:
                sections.append(current_section)
            # Start new section
            current_section = {
                "heading": item.text if hasattr(item, "text") else "Untitled",
                "items": [],
                "page_start": _get_page_number(item),
                "order": len(sections),
            }
        else:
            current_section["items"].append(item)

    # Don't forget the last section
    if current_section["items"]:
        sections.append(current_section)

    return sections


def section_to_markdown(section, doc) -> str:
    """Convert a section's items to Markdown text."""
    parts = [f"## {section['heading']}\n"]
    for item in section["items"]:
        if isinstance(item, TextItem):
            parts.append(item.text)
        elif isinstance(item, TableItem):
            table_df = item.export_to_dataframe(doc=doc)
            parts.append(table_df.to_markdown())
        # Other item types handled as plain text
        elif hasattr(item, "text"):
            parts.append(item.text)
    return "\n\n".join(parts)
```

### Pattern 3: LLM Classification with Ollama Structured Output
**What:** Classify each section by content type and categories using Ollama with JSON schema constraints.
**When to use:** After text extraction, for every section.
**Example:**
```python
# Source: Ollama structured outputs documentation
from ollama import chat
from pydantic import BaseModel, Field
from typing import Literal, Optional
from enum import Enum

class ContentType(str, Enum):
    PROCEDURE = "procedure"
    REFERENCE_TABLE = "reference_table"
    SAFETY_WARNING = "safety_warning"
    GENERAL = "general"

class WarningLevel(str, Enum):
    WARNING = "warning"       # Risk of death/serious injury
    CAUTION = "caution"       # Risk of equipment damage
    NOTE = "note"             # Additional information

class SectionClassification(BaseModel):
    """Classification schema for a document section."""
    primary_type: ContentType = Field(
        description="The primary content type of this section"
    )
    secondary_types: list[ContentType] = Field(
        default_factory=list,
        description="Additional content types present in this section"
    )
    categories: list[Literal[
        "medical", "water", "shelter", "fire", "food",
        "navigation", "signaling", "tools", "first_aid"
    ]] = Field(
        min_length=1,
        max_length=3,
        description="1-3 content categories this section belongs to"
    )
    warning_level: Optional[WarningLevel] = Field(
        default=None,
        description="Military warning level if this section contains a safety warning"
    )
    warning_text: Optional[str] = Field(
        default=None,
        description="Exact text of any WARNING, CAUTION, or NOTE present"
    )
    reasoning: str = Field(
        description="Brief explanation for the classification"
    )


CLASSIFICATION_PROMPT = """You are classifying sections of US military survival manuals and government emergency preparedness documents.

Classify this section into:
- primary_type: The main content type (procedure, reference_table, safety_warning, general)
  - procedure: Step-by-step instructions, how-to guides, action sequences
  - reference_table: Data tables, lookup charts, comparison matrices
  - safety_warning: Standalone warnings, cautions, or safety notices
  - general: Introductions, background, narrative, definitions, non-actionable content

- secondary_types: Any additional types present (e.g., a procedure containing a warning)

- categories: 1-3 categories from [medical, water, shelter, fire, food, navigation, signaling, tools, first_aid]
  - medical: Diseases, medications, dosages, ongoing care, preventive medicine
  - first_aid: Immediate emergency treatment (bleeding control, CPR, splinting, shock)
  - water: Water procurement, purification, storage, safety
  - shelter: Building shelters, insulation, site selection
  - fire: Fire starting, maintenance, signaling fires
  - food: Food procurement, preservation, edible plants, hunting
  - navigation: Map reading, compass use, celestial navigation, terrain association
  - signaling: Rescue signals, mirror, smoke, ground-to-air
  - tools: Improvised tools, knives, cordage, containers

- warning_level: If a WARNING (death/injury risk), CAUTION (equipment damage), or NOTE is present
- warning_text: The exact warning text if present

Respond in the specified JSON format.

SECTION TEXT:
{section_text}"""


def classify_section(section_text: str, model: str = "llama3.1:8b") -> SectionClassification:
    """Classify a section using Ollama with structured output."""
    response = chat(
        model=model,
        messages=[{
            "role": "user",
            "content": CLASSIFICATION_PROMPT.format(section_text=section_text[:4000]),
        }],
        format=SectionClassification.model_json_schema(),
        options={"temperature": 0},
    )
    return SectionClassification.model_validate_json(response.message.content)
```

### Pattern 4: Section File with YAML Front Matter
**What:** Each section is a Markdown file with YAML front matter containing all metadata.
**When to use:** Output format for every processed section.
**Example:**
```markdown
---
source_document: FM-21-76
source_title: "US Army Survival Manual"
section_order: 5
section_heading: "Water Procurement"
page_start: 42
page_end: 56
content_type:
  primary: procedure
  secondary:
    - safety_warning
categories:
  - water
  - survival
warning_level: caution
warning_text: "CAUTION: Do not drink seawater or urine. Both will increase dehydration."
extraction_method: born-digital
ocr_engine: null
processing_date: "2026-02-28"
corrections_applied: false
provenance:
  source_url: "https://www.bits.de/NRANEU/others/amd-us-archive/FM21-76(92).pdf"
  license: "US Government Work - Public Domain"
  distribution_statement: "Distribution Statement A: Approved for public release"
---

## Water Procurement

In a survival situation, you cannot live more than about three days
without water...

**CAUTION:** Do not drink seawater or urine. Both will increase
dehydration and hasten your physical deterioration.

### Finding Water

Look for water along valley floors...
```

### Pattern 5: Corrections YAML Overlay
**What:** Human corrections stored separately from pipeline output for idempotency.
**When to use:** When OCR errors are found during human review.
**Example:**
```yaml
# corrections/FM-21-76-corrections.yaml
# Manual corrections applied as post-processing step
# Pipeline can be re-run without losing these fixes

document: FM-21-76
corrections_date: "2026-02-28"
corrections_by: "human"

corrections:
  - section_file: "FM-21-76_012_water-purification.md"
    type: text_replacement
    original: "Add 2 drops of 2 perc3nt tincture"
    corrected: "Add 2 drops of 2 percent tincture"
    reason: "OCR garbled 'percent' as 'perc3nt'"

  - section_file: "FM-21-76_023_medication-dosages.md"
    type: text_replacement
    original: "325 rng aspirin"
    corrected: "325 mg aspirin"
    reason: "OCR misread 'mg' as 'rng'"

  - section_file: "FM-21-76_023_medication-dosages.md"
    type: text_replacement
    original: "Dosage: I0 mL"
    corrected: "Dosage: 10 mL"
    reason: "OCR misread '10' as 'I0' (capital I for digit 1)"
```

### Pattern 6: Dosage/Measurement Regex Validation
**What:** Auto-detect and flag potential OCR errors in dosages, measurements, and safety-critical numbers.
**When to use:** Post-extraction on all medical and first_aid content.
**Example:**
```python
import re
from dataclasses import dataclass

@dataclass
class DosageFlag:
    text: str
    value: str
    unit: str
    line_number: int
    reason: str
    severity: str  # "critical" or "review"

# Pattern matches numbers followed by medical units
DOSAGE_PATTERN = re.compile(
    r'(\d+\.?\d*)\s*(mg|mL|ml|cc|g|gr|grain|grains|mcg|'
    r'units?|tabs?|caps?|IU|oz|drops?|tsp|tbsp|L|dL|'
    r'percent|%|ppm|mmHg|bpm)\b',
    re.IGNORECASE
)

# Patterns that suggest OCR corruption near numbers
OCR_CORRUPTION_PATTERNS = [
    re.compile(r'[Il1|]{2,}\s*(mg|mL|ml)', re.IGNORECASE),  # Ambiguous 1/I/l/|
    re.compile(r'\d+\s*[rn](g|L)\b'),                         # 'mg' misread as 'rng' or 'ng'
    re.compile(r'[0O]{2,}\s*(mg|mL)', re.IGNORECASE),         # Ambiguous 0/O
    re.compile(r'\d+\.\d{4,}\s*(mg|mL)', re.IGNORECASE),      # Implausible decimal precision
    re.compile(r'(?<!\d)\d{5,}\s*(mg|mL)', re.IGNORECASE),    # Implausibly large values
]

def validate_dosages(text: str) -> list[DosageFlag]:
    """Find and flag potential dosage issues in extracted text."""
    flags = []
    for i, line in enumerate(text.split('\n'), 1):
        # Find all dosage mentions
        for match in DOSAGE_PATTERN.finditer(line):
            value, unit = match.groups()
            # Flag implausible values
            num = float(value)
            if unit.lower() in ('mg', 'mcg') and num > 10000:
                flags.append(DosageFlag(
                    text=match.group(),
                    value=value, unit=unit,
                    line_number=i,
                    reason=f"Implausibly large dosage: {value} {unit}",
                    severity="critical",
                ))

        # Check for OCR corruption patterns near numbers
        for pattern in OCR_CORRUPTION_PATTERNS:
            for match in pattern.finditer(line):
                flags.append(DosageFlag(
                    text=match.group(),
                    value="", unit="",
                    line_number=i,
                    reason=f"Possible OCR corruption: '{match.group()}'",
                    severity="critical",
                ))
    return flags
```

### Anti-Patterns to Avoid
- **Processing all PDFs with force_full_page_ocr:** Born-digital PDFs (most Tier 1 .mil/.gov documents) should use native text extraction. Forcing OCR on born-digital PDFs is slower and produces worse results.
- **Running OCR without the Tesseract system binary installed:** The `tesserocr` Python binding requires the system-level Tesseract binary. Installing the Python package alone is insufficient.
- **Classifying the entire document at once:** Military manuals are 200-500+ pages. Classify per-section, not per-document. The LLM context window and classification quality both degrade with longer inputs.
- **Storing corrections inline in generated files:** This breaks idempotency. Pipeline re-runs would overwrite corrections. Always store corrections in a separate overlay.
- **Truncating table Markdown:** Docling's TableFormer output should be preserved as-is. Truncating or reformatting tables loses structural information needed in Phase 3.
- **Skipping verification reports:** Every document needs a verification report even if no issues are found. The report is the audit trail that proves PROC-02 compliance.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PDF text extraction | Custom PDF parser | Docling DocumentConverter | Handles born-digital, scanned, tables, headers/footers, reading order |
| Table structure recognition | Custom table parser | Docling's TableFormer (ACCURATE mode) | Transformer-based model trained on table structure; handles merged cells, headers |
| Header/footer removal | Regex to strip first/last lines per page | Docling's ContentLayer.FURNITURE detection | Layout-model-based detection far more accurate than line-position heuristics |
| OCR orchestration | Manual Tesseract/EasyOCR calls | Docling's OCR pipeline with bitmap_area_threshold | Automatically detects which pages need OCR vs native text extraction |
| Text classification | Keyword matching / rule-based classifier | Ollama structured output with Pydantic schemas | Military documents use non-standard formatting; LLM handles nuance rule-based cannot |
| JSON output parsing from LLM | String manipulation / regex on LLM output | Ollama format parameter + Pydantic model_validate_json | Grammar-constrained generation ensures valid JSON; Pydantic validates types |

**Key insight:** Docling's strength is its unified pipeline that handles the born-digital vs. scanned detection, OCR routing, table extraction, and header/footer removal as a single coherent system. Trying to hand-roll any of these individually would miss the interconnections (e.g., table cells need to align with OCR text, header detection needs layout model output).

## Common Pitfalls

### Pitfall 1: Tesseract System Binary Not Installed
**What goes wrong:** `pip install docling[tesserocr]` succeeds but OCR fails at runtime with "tesseract not found" or segfaults.
**Why it happens:** The `tesserocr` Python package is a binding to the C++ Tesseract library. The Python package alone is insufficient -- the system-level Tesseract binary and language data must also be installed.
**How to avoid:** Install Tesseract at the system level before pip install. On Windows, use the UB Mannheim installer (https://github.com/UB-Mannheim/tesseract/wiki). On macOS, `brew install tesseract`. On Linux, `apt-get install tesseract-ocr tesseract-ocr-eng`.
**Warning signs:** Import errors mentioning `libtesseract`, runtime errors about missing tessdata, segmentation faults when converting scanned PDFs.

### Pitfall 2: Docling Header Hierarchy Flattened to H2
**What goes wrong:** Military manuals have deep heading hierarchies (Chapter > Section > Subsection > Paragraph). Docling's Markdown export flattens these to `##` (H2) headers, losing the hierarchy.
**Why it happens:** Docling's layout model detects "section_header" elements but does not always reliably distinguish heading levels from the visual layout. This is a known limitation noted in GitHub issue #1023 and discussion #386.
**How to avoid:** When iterating items with `iterate_items()`, use the `level` parameter (returned as the second element of the tuple) to infer heading depth. Alternatively, accept the flattened headers -- for the purposes of section splitting and classification, the hierarchy within sections is less critical than the section boundaries themselves.
**Warning signs:** All headings appearing as `##` in exported Markdown regardless of original depth.

### Pitfall 3: OCR Corruption of Medical Dosages
**What goes wrong:** OCR misreads digits and units in dosage information. Common errors: `1` read as `l` or `I`, `0` read as `O`, `mg` read as `rng`, `10 mL` read as `I0 mL`.
**Why it happens:** Scanned military PDFs may have low resolution, faded ink, or typewriter fonts where characters are visually ambiguous.
**How to avoid:** (1) Regex-based post-extraction validation flags suspicious patterns. (2) Medical documents with dosages get flagged for human spot-check. (3) Documents with unresolvable OCR corruption are excluded per user decision.
**Warning signs:** Dosage validation regex flags more than 5 anomalies per page; OCR confidence scores (if available) below 0.7 on medical pages.

### Pitfall 4: Ollama Not Running During Pipeline
**What goes wrong:** Classification and tagging steps fail because the Ollama server is not running or the model is not loaded.
**Why it happens:** The processing pipeline requires Ollama as an external dependency. If the user hasn't started Ollama or pulled the model, the pipeline crashes partway through.
**How to avoid:** (1) Pipeline startup checks: verify Ollama is reachable at localhost:11434 before processing begins. (2) Verify the required model (llama3.1:8b) is available. (3) Provide clear error messages with setup instructions.
**Warning signs:** ConnectionRefusedError on port 11434; 404 errors when requesting model.

### Pitfall 5: PyTorch Installation Bloat
**What goes wrong:** Installing Docling pulls in PyTorch with CUDA support, consuming 2-4 GB of disk space unnecessarily if no GPU is available.
**Why it happens:** PyTorch's default pip distribution includes CUDA libraries. Docling depends on PyTorch for its deep learning models (layout detection, table structure).
**How to avoid:** Use the CPU-only index: `pip install docling --extra-index-url https://download.pytorch.org/whl/cpu`. This installs CPU-only PyTorch, saving significant disk space.
**Warning signs:** Virtual environment growing to 5+ GB; long installation times; pip downloading torch with `+cu*` suffix.

### Pitfall 6: Idempotency Broken by In-Place Corrections
**What goes wrong:** A team member manually edits a processed Markdown file to fix an OCR error. The next pipeline run overwrites the correction.
**Why it happens:** Without a corrections overlay, manual fixes are stored in the same files the pipeline generates.
**How to avoid:** Corrections are ALWAYS stored in `processed/corrections/{doc}-corrections.yaml`. The pipeline writes raw output, then applies corrections as a post-processing step. Pipeline re-runs regenerate raw output but always re-apply existing corrections.
**Warning signs:** Git history showing corrections disappearing after pipeline re-runs; team members reluctant to re-run pipeline.

### Pitfall 7: LLM Classification Inconsistency
**What goes wrong:** Running classification on the same section produces different results each time, making the pipeline non-deterministic.
**Why it happens:** LLMs are inherently stochastic. Without temperature=0 and a fixed seed, outputs vary between runs.
**How to avoid:** (1) Set `temperature=0` in all Ollama calls. (2) Use structured output (format parameter) to constrain responses to valid JSON matching the schema. (3) Truncate input to a consistent length (4000 chars) to avoid variable tokenization effects.
**Warning signs:** Classification results changing between pipeline runs on the same input; inconsistent primary_type assignments.

## Code Examples

### Complete Section Processing Flow
```python
# Source: Assembled from Docling docs, Ollama docs, project CONTEXT.md decisions
from pathlib import Path
import yaml

def process_single_document(
    pdf_path: Path,
    manifest_path: Path,
    output_dir: Path,
    corrections_dir: Path,
    reports_dir: Path,
):
    """Process one source PDF into classified, tagged Markdown sections."""
    manifest = yaml.safe_load(manifest_path.read_text())
    doc_id = manifest["document"]["designation"].replace(" ", "-")

    # Step 1: Extract with Docling
    doc = extract_document(str(pdf_path), ocr_backend="tesseract")

    # Step 2: Split into sections
    sections = split_into_sections(doc, doc_id)

    # Step 3: For each section, generate Markdown and classify
    section_files = []
    dosage_flags = []

    for idx, section in enumerate(sections):
        md_text = section_to_markdown(section, doc)

        # Step 3a: Validate dosages in medical content
        flags = validate_dosages(md_text)
        dosage_flags.extend(flags)

        # Step 3b: Classify with LLM
        classification = classify_section(md_text)

        # Step 3c: Build YAML front matter
        front_matter = {
            "source_document": doc_id,
            "source_title": manifest["document"]["title"],
            "section_order": idx + 1,
            "section_heading": section["heading"],
            "page_start": section["page_start"],
            "content_type": {
                "primary": classification.primary_type.value,
                "secondary": [t.value for t in classification.secondary_types],
            },
            "categories": list(classification.categories),
            "warning_level": classification.warning_level.value if classification.warning_level else None,
            "warning_text": classification.warning_text,
            "extraction_method": "born-digital",  # or "tesseract" / "easyocr"
            "processing_date": "2026-02-28",
            "provenance": {
                "source_url": manifest["source"]["primary_url"],
                "license": manifest["licensing"]["license_type"],
                "distribution_statement": manifest["licensing"]["distribution_statement"],
            },
        }

        # Step 3d: Write section file
        safe_heading = _slugify(section["heading"])
        filename = f"{doc_id}_{idx+1:03d}_{safe_heading}.md"
        section_path = output_dir / doc_id / filename

        section_path.parent.mkdir(parents=True, exist_ok=True)
        content = f"---\n{yaml.dump(front_matter, default_flow_style=False)}---\n\n{md_text}"
        section_path.write_text(content, encoding="utf-8")
        section_files.append(filename)

    # Step 4: Apply corrections if they exist
    corrections_file = corrections_dir / f"{doc_id}-corrections.yaml"
    if corrections_file.exists():
        apply_corrections(corrections_file, output_dir / doc_id)

    # Step 5: Generate verification report
    report = {
        "document": doc_id,
        "extraction_method": "born-digital",  # or detected method
        "total_sections": len(sections),
        "total_pages": doc.num_pages,
        "dosage_flags": len(dosage_flags),
        "flagged_items": [
            {"text": f.text, "line": f.line_number, "reason": f.reason, "severity": f.severity}
            for f in dosage_flags
        ],
        "corrections_applied": corrections_file.exists(),
        "processing_date": "2026-02-28",
    }
    report_path = reports_dir / f"{doc_id}-report.yaml"
    report_path.write_text(yaml.dump(report, default_flow_style=False))

    return section_files, dosage_flags
```

### Ollama Connectivity Check
```python
# Source: Ollama Python library documentation
import ollama

def check_ollama_ready(model: str = "llama3.1:8b") -> bool:
    """Verify Ollama is running and the required model is available."""
    try:
        models = ollama.list()
        available = [m.model for m in models.models]
        if not any(model in m for m in available):
            print(f"ERROR: Model '{model}' not found. Available: {available}")
            print(f"Run: ollama pull {model}")
            return False
        return True
    except Exception as e:
        print(f"ERROR: Cannot connect to Ollama: {e}")
        print("Run: ollama serve")
        return False
```

### File Naming Convention
```python
def generate_section_filename(doc_id: str, order: int, heading: str) -> str:
    """
    Generate sortable, descriptive filename for a section.

    Format: {DOC-ID}_{ORDER:03d}_{SLUGIFIED-HEADING}.md

    Examples:
        FM-21-76_001_survival-medicine.md
        FM-21-76_002_water-procurement.md
        TC-4-02-1_015_hemorrhage-control.md
        are-you-ready_003_natural-hazards.md
    """
    slug = _slugify(heading)[:50]  # Truncate long headings
    return f"{doc_id}_{order:03d}_{slug}.md"

def _slugify(text: str) -> str:
    """Convert heading to filesystem-safe slug."""
    import re
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text.strip('-')
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| PyMuPDF / pdfplumber for text extraction | Docling with layout model + table structure | 2024-2025 | Unified pipeline handles text, tables, OCR, structure |
| Manual OCR with pytesseract | Docling's integrated OCR pipeline with backend selection | 2024-2025 | Automatic born-digital detection, multi-backend support |
| Rule-based text classification | LLM-assisted classification with structured output | 2024-2025 | Handles non-standard military document formatting |
| Ollama JSON mode (format: "json") | Ollama structured output (format: JSON schema) | Dec 2024 (Ollama v0.5) | Schema-constrained generation guarantees valid, typed responses |
| Docling v1 (docling-parse) | Docling v2 with docling-parse v5 | 2025-2026 | New parser, better layout detection, VLM support |

**Deprecated/outdated:**
- docling-parse v4 and earlier backends are deprecated as of Docling v2.74.0 (Feb 2026)
- Python 3.9 support dropped in Docling v2.70.0
- Ollama `format: "json"` (without schema) still works but provides no structure guarantees -- use schema-based structured output instead

## Open Questions

1. **Docling performance on specific Tier 1 military PDFs**
   - What we know: Docling handles born-digital PDFs well. Most Tier 1 military documents from .mil/.gov sources should be born-digital. OCR quality on scanned pages can be "disappointing" per community reports.
   - What's unclear: Which specific Tier 1 PDFs are scanned vs. born-digital. FM 21-76 (1992) is old enough that some copies may be scanned. FEMA "Are You Ready?" at 200+ pages may have mixed pages.
   - Recommendation: First pipeline task should assess each PDF's born-digital vs. scanned status. Use Docling's bitmap coverage signals to create an audit before full processing.

2. **Heading hierarchy quality in military documents**
   - What we know: Docling flattens headings to H2 (known issue #1023). Military manuals use strict hierarchical numbering (Chapter > Section > Paragraph, e.g., "3-4. Water Procurement").
   - What's unclear: Whether Docling's layout model reliably detects section boundaries in the specific formatting style of Army FMs (numbered paragraphs like "3-4", "3-5").
   - Recommendation: Accept section_header detection as-is for splitting. Use the `level` parameter from `iterate_items()` where available. The numbered paragraph format (e.g., "3-4.") can be regex-detected as a backup section boundary marker.

3. **Ollama classification quality at scale**
   - What we know: Llama 3.1 8B can handle zero-shot classification tasks. Structured output constrains format. Temperature=0 improves consistency.
   - What's unclear: Classification accuracy across hundreds of sections. Some edge cases may be ambiguous (e.g., is "Water purification tablets" a procedure or a reference?).
   - Recommendation: Build a small validation set of 20-30 manually classified sections. Run the classifier on this set and measure accuracy before full corpus processing. Adjust prompt if accuracy is below 90%.

4. **Processing time for full Tier 1 corpus**
   - What we know: Docling processes born-digital pages at ~0.5-3s per page. OCR adds 1.6-13s per page depending on hardware. Ollama classification adds ~1-2s per section.
   - What's unclear: Total wall-clock time for all 71 Tier 1 documents (estimated 6000-10000 pages total).
   - Recommendation: Process in two waves: (1) extraction + cleaning for all documents, (2) classification + tagging. This allows extraction issues to be caught and fixed before the slower classification step.

## Sources

### Primary (HIGH confidence)
- [Docling GitHub repository](https://github.com/docling-project/docling) - v2.75.0 README, features, installation
- [Docling PyPI](https://pypi.org/project/docling/) - v2.75.0, Python >=3.10 requirement
- [Docling Installation docs](https://docling-project.github.io/docling/getting_started/installation/) - pip extras, OCR backend setup, PyTorch configuration
- [Docling Pipeline Options reference](https://docling-project.github.io/docling/reference/pipeline_options/) - PdfPipelineOptions, OcrOptions, TableStructureOptions
- [Docling Advanced Options](https://docling-project.github.io/docling/usage/advanced_options/) - Table processing, cell matching, remote services, model prefetch
- [Docling DoclingDocument reference](https://docling-project.github.io/docling/reference/docling_document/) - iterate_items(), export_to_markdown(), item types
- [Docling Chunking concepts](https://docling-project.github.io/docling/concepts/chunking/) - HierarchicalChunker, HybridChunker, BaseChunker
- [Ollama Structured Outputs docs](https://docs.ollama.com/capabilities/structured-outputs) - format parameter, JSON schema, Pydantic integration
- [Ollama Python library (PyPI)](https://pypi.org/project/ollama/) - v0.6.1, chat API, structured output

### Secondary (MEDIUM confidence)
- [Docling GitHub Discussion #2755](https://github.com/docling-project/docling/discussions/2755) - Born-digital vs scanned detection, bitmap_area_threshold
- [Docling GitHub Issue #1023](https://github.com/docling-project/docling/issues/1023) - H2-only header export limitation
- [Docling GitHub Discussion #386](https://github.com/docling-project/docling/discussions/386) - Header hierarchy in Markdown output
- [Towards Data Science: "Docling: The Document Alchemist"](https://towardsdatascience.com/docling-the-document-alchemist/) - OCR performance benchmarks, limitations
- [Ollama Blog: Structured Outputs](https://ollama.com/blog/structured-outputs) - Feature announcement Dec 2024, examples
- [DeepWiki: Docling Configuration](https://deepwiki.com/docling-project/docling/2.3-configuration-and-pipeline-options) - Configuration hierarchy, pipeline options
- [Medium: Using Ollama to Categorize Qualitative Data](https://medium.com/@weijiawa/harnessing-local-large-language-models-using-ollama-to-categorize-and-analyze-qualitative-data-35d1975da1e9) - LLM classification patterns

### Tertiary (LOW confidence)
- [Mindfire Technology: Docling for PDF to Markdown](https://www.mindfiretechnology.com/blog/archive/docling-for-pdf-to-markdown-conversion/) - User experience comparison with PyMuPDF4LLM (results vary by document)
- [Procycons: PDF Data Extraction Benchmark 2025](https://procycons.com/en/blogs/pdf-data-extraction-benchmark/) - Comparative benchmarks (methodology not verified)
- [ResearchGate: Regex for dosage information](https://www.researchgate.net/figure/Example-of-regular-expression-grammar-to-match-dosage-information_fig1_46158282) - Academic regex patterns for medication dosages

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Docling v2.75.0 is actively maintained (Feb 2026 release), LF AI Foundation project, MIT license, well-documented API. Ollama structured output is stable since v0.5 (Dec 2024).
- Architecture: HIGH - Patterns derived from official Docling documentation (iterate_items, export_to_markdown) and official Ollama structured output docs. File naming and corrections overlay designed for project-specific requirements.
- Pitfalls: HIGH - Pitfalls verified against GitHub issues (#1023 header hierarchy), official docs (Tesseract system binary requirement), and community reports (OCR quality limitations).
- Classification approach: MEDIUM - LLM-based classification with structured output is well-documented but accuracy on specific military document content is unverified. Recommend validation set before full processing.

**Research date:** 2026-02-28
**Valid until:** 2026-03-30 (Docling releases every 1-2 weeks but API is stable; Ollama structured output API stable since Dec 2024)
