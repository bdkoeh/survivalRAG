---
phase: 05-response-generation
plan: 02
subsystem: generation
tags: [citation-verification, fuzzy-matching, post-processing, pipeline-integration, sequencematcher]

# Dependency graph
requires:
  - phase: 05-response-generation
    plan: 01
    provides: "Core LLM generation engine (init, generate_stream, generate) with three response modes"
  - phase: 04-retrieval-pipeline
    provides: "Prompt assembly and retrieval pipeline (query, build_response, assemble_prompt)"
provides:
  - "Citation verification: extract_citations() and verify_citations() with fuzzy matching"
  - "Post-processing: _post_process() enforcing bold warnings, numbered steps, ultra truncation"
  - "Full pipeline entry points: answer() and answer_stream() wiring query -> retrieve -> prompt -> generate -> verify"
  - "Phase 5 -> Phase 6/7 contract: complete response dict with verification results"
affects: [06-evaluation, 07-user-interfaces]

# Tech tracking
tech-stack:
  added: [difflib-sequencematcher]
  patterns: [post-generation-verification, citation-fuzzy-matching, pipeline-integration-entry-points, function-level-imports]

key-files:
  created: []
  modified: [pipeline/generate.py]

key-decisions:
  - "Post-generation verification runs AFTER full response, NOT during streaming -- streaming verification would block token output"
  - "Fuzzy matching with SequenceMatcher at 0.6 threshold handles abbreviations and partial document titles"
  - "On verification failure: keep response and append visible warning -- never silently discard"
  - "Ultra mode skips citation verification entirely (no room for citations in 200-char responses)"
  - "Function-level import of pipeline.prompt.query inside answer()/answer_stream() to avoid circular dependency"
  - "Refusal path short-circuits without calling LLM -- canned message returned directly"

patterns-established:
  - "Citation extraction with multi-pattern regex: handles 4 citation formats small LLMs produce"
  - "Verification results as structured data: both logged AND returned in response dict for Phase 6 evaluation"
  - "Full pipeline entry points with function-level imports to avoid circular dependencies"
  - "Post-processing as structural-only formatting: never modifies content words, dosages, or measurements"

requirements-completed: [RESP-01, RESP-02, RESP-07]

# Metrics
duration: 3min
completed: 2026-03-02
---

# Phase 5 Plan 02: Citation Verification & Pipeline Integration Summary

**Citation verification with fuzzy matching against source documents, structural post-processing for field-manual formatting, and answer()/answer_stream() entry points wiring the complete query-to-response pipeline**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-02T01:46:43Z
- **Completed:** 2026-03-02T01:49:50Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- Citation verification system with 4-pattern regex extraction and SequenceMatcher fuzzy matching at 0.6 threshold
- Post-processing enforces bold **WARNING:**/**CAUTION:**/**DANGER:** formatting and consistent numbered steps without altering content
- answer() wires full pipeline (query -> retrieve -> prompt -> generate -> verify) as single entry point for Phase 7
- answer_stream() provides streaming variant returning (status, generator) tuple for CLI and web UI
- Refusal path short-circuits on both entry points without calling the LLM
- generate() now runs _post_process and verify_citations after token collection, with failed verification appending visible warning

## Task Commits

Each task was committed atomically:

1. **Task 1: Add citation verification and post-processing functions** - `f97bb81` (feat)
2. **Task 2: Add answer() and answer_stream() pipeline integration entry points** - `ab72966` (feat)

**Plan metadata:** (pending)

## Files Created/Modified
- `pipeline/generate.py` - Complete Phase 5 module (597 lines): init, generate_stream, generate, answer, answer_stream, extract_citations, verify_citations, _post_process

## Decisions Made
- Post-generation verification runs after full response is complete, not during streaming, because verification needs the complete text and streaming verification would block token output
- Fuzzy matching with SequenceMatcher at 0.6 threshold chosen to handle abbreviations (e.g., "FM 21-76" vs "FM 21-76 Survival") via both substring matching (fast path) and ratio comparison (slow path)
- On verification failure the response is kept with a visible warning appended -- never silently discarding responses since partial citations may still be useful
- Ultra mode skips citation verification entirely since ultra responses have no room for citations (200-char telegram style)
- Function-level import of `pipeline.prompt.query` inside answer()/answer_stream() avoids circular dependency between generate.py and prompt.py
- Refusal path returns canned message directly without calling the LLM (matching the anti-pattern note from research: never send "I don't know" prompts to the LLM)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- ollama Python package was not installed on the build machine -- installed via pip3 to enable import verification (Rule 3 auto-fix, no code change needed)

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 5 (Response Generation) is complete -- all 7 RESP requirements satisfied across Plans 05-01 and 05-02
- pipeline/generate.py exports all 7 functions: init, generate_stream, generate, answer, answer_stream, verify_citations, extract_citations
- answer() is the primary entry point for Phase 7 CLI and web UI integration
- answer_stream() provides streaming for CLI real-time output and web UI SSE
- Verification results are structured data in response dict, ready for Phase 6 evaluation framework
- Requires `ollama pull llama3.2:3b` (or SURVIVALRAG_MODEL env var set) and `ollama serve` running before runtime use

## Self-Check: PASSED

- pipeline/generate.py: FOUND
- 05-02-SUMMARY.md: FOUND
- Commit f97bb81 (Task 1): FOUND
- Commit ab72966 (Task 2): FOUND

---
*Phase: 05-response-generation*
*Completed: 2026-03-02*
