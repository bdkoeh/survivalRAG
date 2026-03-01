# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-28)

**Core value:** Every survival/medical answer is grounded in cited public domain source documents -- when context is insufficient, the system says so rather than guessing.
**Current focus:** Phase 1 complete (expanded). Ready for Phase 2: Document Processing

## Current Position

Phase: 1 of 8 (Content Sourcing & Licensing) -- COMPLETE
Plan: 5 of 5 in current phase (all plans complete)
Status: Phase complete (expanded corpus)
Last activity: 2026-02-28 -- Completed 01-05-PLAN.md (Planning artifacts + WikiMed plan)

Progress: [█░░░░░░░░░] 12%

## Performance Metrics

**Velocity:**
- Total plans completed: 5
- Average duration: ~6min
- Total execution time: ~0.5 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. Content Sourcing | 5 | ~30min | ~6min |

**Recent Trend:**
- Last 5 plans: 8min, 5min, 6min, 5min, 6min
- Trend: Stable

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: 8-phase pipeline structure following document flow (source -> process -> chunk -> retrieve -> respond -> evaluate -> UI -> deploy)
- [Roadmap]: Eval phase depends on Retrieval + Response phases (build eval alongside backend, validate after)
- [Roadmap]: Web UI and CLI combined into single User Interfaces phase (both are presentation over the same backend)
- [01-01]: Wayback Machine id_ modifier needed for raw PDF downloads (standard /web/latest/ returns HTML wrapper)
- [01-01]: FEMA.gov has restructured URLs -- Are You Ready? no longer at original path
- [01-01]: PDF format validation (%PDF magic bytes) essential to catch HTML error pages
- [01-01]: CDC "Keep Food Safe" web page needs manual browser PDF capture (wkhtmltopdf not available)
- [01-02]: Manifest schema v1.0 established with 5 top-level sections (document, source, licensing, content, processing)
- [01-02]: Military docs verified via Distribution Statement A; civilian docs via 17 U.S.C. 105
- [01-02]: Bash validation script created alongside Python script (Python not available on build system)
- [01-03]: Expanded corpus from 16 docs / 3 agencies to 71 docs / 11 agencies
- [01-03]: Added web_capture() helper function in download script for non-PDF sources
- [01-03]: Dynamic subdirectory scanning replaces hardcoded agency lists in download summary
- [01-04]: Validation scripts updated with dynamic subdirectory discovery (no more hardcoded lists)
- [01-04]: Added Department of the Air Force and 10 civilian publishers to validation
- [01-04]: USDA canning guide split into 8 individual manifests (one per section)
- [01-05]: WikiMed extraction deferred to future phase; CC BY-SA 4.0 requires separate handling from public domain

### Pending Todos

- Download AFH-10-644.pdf (USAF SERE Handbook) and update its manifest hash -- only document not yet acquired (all 3 download sources failed; Distribution Statement A confirmed)

### Blockers/Concerns

- [Research]: Docling is newer than PyMuPDF -- needs hands-on validation with military PDFs in Phase 2
- [Research]: nomic-embed-text medical terminology performance needs empirical testing in Phase 3
- [Research]: Small LLM hallucination risk on medical content -- prompt engineering critical in Phase 5

## Session Continuity

Last session: 2026-02-28
Stopped at: Phase 1 re-verified against expanded corpus (71 PDFs, 72 manifests, 11 agencies). All artifacts aligned. Ready for Phase 2.
Resume file: none
