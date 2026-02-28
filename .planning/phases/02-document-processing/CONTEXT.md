# Phase 2 Discussion Context

**Phase:** Document Processing
**Discussed:** 2026-02-28

## Decisions from Discussion

### OCR Verification Workflow
- **Lean on Docling, not a bespoke review process.** Modern PDF-to-Markdown converters handle most extraction quality. Born-digital PDFs (majority of Tier 1 from .mil/.gov) won't need OCR at all.
- **Scanned PDFs: Tesseract first, EasyOCR fallback.** Docling supports both backends. Try Tesseract, fall back to EasyOCR for degraded pages.
- **Auto-flag critical fields with regex.** After extraction, pattern-match for dosages (numbers + units: mg, mL, cc, gr, etc.) and measurements. Log anomalies (implausible values, garbled text adjacent to numbers) for human spot-check.
- **Poor OCR quality = exclude the document.** If neither OCR engine produces reliable text, drop the document. Better no answer than a wrong one.
- **Lightweight verification report per document.** Log: extraction method used (born-digital vs OCR engine), pages flagged for review, any corrections applied, confidence notes.

### Content Classification Rules
- **LLM-assisted classification.** Run each section through a local LLM (via Ollama) to classify content type. Requires Ollama running during the processing pipeline.
- **Four content types:** `procedure`, `reference_table`, `safety_warning`, `general`.
- **Multi-type: keep section intact, tag both.** A procedure with an embedded WARNING stays as one section. Classified as primary=`procedure` with secondary types (e.g., `safety_warning`). Warning text is also captured in metadata so it surfaces even when this specific section isn't the top retrieval result (feeds CHNK-04 in Phase 3).
- **Preserve all three military warning levels:** `warning` (risk of death/serious injury), `caution` (risk of equipment damage), `note` (additional information). Stored as a sub-level on `safety_warning` classifications.
- **Non-actionable content (introductions, historical context, narrative) → `general`.** No filtering or exclusion at this stage.

### Category Tagging Strategy
- **Multiple categories allowed per section (1-3).** A section on water purification tablets with dosage instructions gets tagged `[water, medical]`. Improves retrieval coverage.
- **LLM per section for category assignment.** Same approach as content type classification — run through local LLM.
- **Starting taxonomy (9 categories):** `medical`, `water`, `shelter`, `fire`, `food`, `navigation`, `signaling`, `tools`, `first_aid`.
- **Taxonomy is extensible after first pass.** After initial processing, review what content falls into ambiguous buckets. Decide then whether to add categories like `hygiene`, `general_survival`, `psychology`, etc. The taxonomy isn't permanently locked — but it's locked for the initial processing run.
- **`medical` and `first_aid` are distinct categories.** `first_aid` = immediate emergency treatment (bleeding control, CPR, splinting, shock). `medical` = broader medical knowledge (diseases, medications, dosages, ongoing care, preventive medicine).

### Output Format & Structure
- **Markdown files.** Docling outputs Markdown natively. Standard format for LLM consumption. Human-readable for review and correction. Researcher should confirm this is best practice for the Docling → LlamaIndex pipeline.
- **Split output by section.** Every major section of a source document becomes its own file. Aligns with per-section classification/tagging. Creates more files but feeds directly into Phase 3 chunking.
- **File naming convention:** TBD by planner — must encode source document, section order, and be sortable.
- **Tables preserved as-is from Docling.** Docling's TableFormer model extracts tables. No custom table processing layer. Whatever format Docling produces (typically Markdown tables) is kept.
- **Idempotent pipeline.** The processing pipeline can be re-run on the same source PDFs and produce identical output. Manual corrections are stored in a separate corrections layer (e.g., a corrections YAML per document) and applied as a post-processing step. This allows pipeline improvements without losing human review work.

## Phase Boundary

**In scope:**
- PDF text extraction (born-digital and scanned)
- OCR with quality verification
- Text cleaning (headers, footers, page numbers, watermarks, artifacts)
- Content type classification (procedure, reference_table, safety_warning, general)
- Category tagging (medical, water, shelter, etc.)
- Output as clean, classified, tagged Markdown sections

**Out of scope (belongs to other phases):**
- Chunking strategy and chunk size decisions → Phase 3
- Embedding model selection and benchmarking → Phase 3
- Vector database storage → Phase 3
- Retrieval logic → Phase 4
- Any UI or API work → Phase 7

## Dependencies

- **Phase 1 output required:** Downloaded PDFs with provenance manifests
- **Ollama required during processing:** LLM-assisted classification and category tagging need a running Ollama instance with a model loaded

## Requirements Covered
PROC-01, PROC-02, PROC-03, PROC-04, PROC-05

## Deferred Ideas
- Extended taxonomy categories (hygiene, general_survival, psychology) — revisit after first processing pass
- Custom table processing for complex merged-cell tables — only if Docling output proves insufficient
