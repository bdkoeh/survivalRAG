---
phase: 06-evaluation-framework
plan: 02
subsystem: testing
tags: [evaluation, retrieval-recall, citation-faithfulness, refusal-testing, safety-warnings, cli-runner]

# Dependency graph
requires:
  - phase: 06-evaluation-framework
    plan: 01
    provides: "Golden query dataset (58 queries) and refusal dataset (20 queries) in JSONL format"
  - phase: 04-retrieval-pipeline
    provides: "retrieve.retrieve() for retrieval recall and safety warning evaluation"
  - phase: 05-response-generation
    provides: "gen.answer() for refusal and citation faithfulness evaluation, gen.verify_citations()"
provides:
  - "Evaluation runner at pipeline/evaluate.py with 4 dimensions"
  - "Terminal summary table with PASS/FAIL per dimension"
  - "Detailed JSON results at processed/eval/results.json"
  - "Suite selection via --suite flag (retrieval, refusal, citation, safety, all)"
  - "Non-zero exit code on threshold failure (CI-friendly)"
affects: [07-user-interfaces, 08-deployment]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "4-dimension evaluation: retrieval recall, refusal, citation faithfulness, safety warnings"
    - "Graded per-query scoring (0.0-1.0) with aggregate thresholds"
    - "Medical terminology retrieval measured separately against 85% threshold"
    - "Suite selection for fast iteration (retrieval-only skips LLM, runs in seconds)"
    - "Pre-flight chunk ID validation against ChromaDB with graceful degradation"

key-files:
  created:
    - pipeline/evaluate.py
  modified: []

key-decisions:
  - "Retrieval recall overall is INFO-only; threshold applies to medical_terminology subset per roadmap spec"
  - "Safety warnings dimension is informational (no numeric threshold) -- any percentage above 0% is acceptable"
  - "Failure details always shown when any query scores below 1.0, not just when overall thresholds fail"
  - "Suite selection enables fast dev iteration: --suite retrieval skips LLM generation entirely"

patterns-established:
  - "Evaluation result dict contract: query, dimension, score, plus dimension-specific fields"
  - "aggregate_results() produces label, score, count, threshold, status per dimension"
  - "print_summary() + print_failures() terminal reporting pattern"

requirements-completed: [EVAL-02, EVAL-03, EVAL-04, EVAL-05]

# Metrics
duration: 3min
completed: 2026-03-02
---

# Phase 6 Plan 2: Evaluation Runner Summary

**4-dimension evaluation runner measuring retrieval recall, refusal compliance, citation faithfulness, and safety warning surfacing with terminal summary table, JSON output, and --suite selection for fast iteration**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-02T17:37:22Z
- **Completed:** 2026-03-02T17:41:07Z
- **Tasks:** 2
- **Files created:** 1

## Accomplishments
- Complete evaluation runner with 4 dimensions: retrieval recall (EVAL-02), hallucination refusal (EVAL-03), citation faithfulness (EVAL-04), safety warning surfacing (EVAL-05)
- Graded per-query scoring (0.0-1.0) with aggregate thresholds: 85% retrieval recall on medical terminology, 90% citation faithfulness, 100% refusal
- Suite selection via `--suite` flag for fast development iteration (retrieval-only requires no LLM)
- Pre-flight chunk ID validation against ChromaDB with graceful degradation (missing IDs reduce scores naturally)
- Terminal summary table with query counts and PASS/FAIL/INFO status, plus detailed failure reporting with expected vs actual

## Task Commits

Each task was committed atomically:

1. **Task 1: Build evaluation functions for all four dimensions** - `2c2018a` (feat)
2. **Task 2: Build runner with CLI, terminal reporting, JSON output, and exit codes** - `e54b375` (feat)

## Files Created/Modified
- `pipeline/evaluate.py` - Complete evaluation runner: 4 dimension functions (evaluate_retrieval, evaluate_refusal, evaluate_citation_faithfulness, evaluate_safety_warnings), aggregation, terminal summary table, JSON output, argparse CLI with --suite, non-zero exit codes

## Decisions Made
- **Medical terminology threshold applies to filtered subset:** The roadmap says "recall >85% on medical terminology queries" -- overall retrieval is reported as INFO-only while the threshold check applies to query_type=="medical_terminology" entries only
- **Safety warnings are informational:** No numeric threshold for safety warning surfacing -- reported as INFO since any surfacing is beneficial, and the dimension is inherently binary per query
- **Always show individual failures:** Failure details printed whenever any query scores below 1.0, not just when aggregate thresholds fail -- aids debugging during development
- **Status-based refusal check (not message string matching):** Check `result["status"] == "refused"` per CONTEXT.md discretion recommendation, not exact REFUSAL_MESSAGE text comparison

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- `python -m pipeline.evaluate --help` cannot run on build machine due to missing bm25s dependency (required by retrieve.py at import time). This is a pre-existing environment limitation -- the module is syntactically valid and all functions verified via AST parsing.

## User Setup Required

None - no external service configuration required. Running the evaluation suite requires Ollama with a populated ChromaDB (same prerequisites as the existing pipeline).

## Next Phase Readiness
- Evaluation framework complete: golden dataset (Plan 01) + evaluation runner (Plan 02) ready for use
- Run with `python -m pipeline.evaluate` after corpus ingestion and Ollama setup
- Fast iteration: `python -m pipeline.evaluate --suite retrieval` for retrieval-only testing (no LLM needed)
- Phase 6 provides the quality gate for Phase 7 (User Interfaces) and Phase 8 (Deployment)

## Self-Check: PASSED

- FOUND: pipeline/evaluate.py
- FOUND: 06-02-SUMMARY.md
- FOUND: commit 2c2018a
- FOUND: commit e54b375

---
*Phase: 06-evaluation-framework*
*Completed: 2026-03-02*
