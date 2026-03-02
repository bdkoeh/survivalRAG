---
phase: 06-evaluation-framework
plan: 01
subsystem: testing
tags: [evaluation, golden-dataset, jsonl, retrieval-recall, refusal-testing]

# Dependency graph
requires:
  - phase: 03-chunking-embedding
    provides: "Chunk ID format ({source_document}_{page:03d}_{chunk_index:03d}) and corpus document inventory"
  - phase: 01-content-sourcing
    provides: "Source document list and provenance manifests for query targeting"
provides:
  - "Golden query dataset (58 in-scope queries) at data/eval/golden_queries.jsonl"
  - "Refusal query dataset (20 out-of-scope queries) at data/eval/refusal_queries.jsonl"
  - "Query type taxonomy: lay_language, medical_terminology, typo_variant, emotional"
  - "Refusal category taxonomy: off_topic, diagnosis_request, harmful, outside_kb"
affects: [06-02-evaluation-runner]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "JSONL format for evaluation datasets (one JSON object per line)"
    - "6-field schema for in-scope queries: query, query_type, category, expected_chunk_ids, key_facts, safety_critical"
    - "4-field schema for refusal queries: query, query_type, category, expected_action"

key-files:
  created:
    - data/eval/golden_queries.jsonl
    - data/eval/refusal_queries.jsonl
  modified: []

key-decisions:
  - "58 golden queries (exceeds 50+ minimum) hand-curated to cover realistic survival/emergency scenarios"
  - "Expected chunk IDs constructed from deterministic format using actual corpus documents -- evaluation runner will validate existence"
  - "Emotional queries reflect realistic distress: incomplete sentences, all lowercase, no punctuation, urgent tone"
  - "Refusal queries crafted to avoid semantic overlap with corpus (per Pitfall 2 from RESEARCH.md)"

patterns-established:
  - "Golden dataset JSONL schema: consistent with processed/benchmark/pairs.jsonl format"
  - "Query type distribution: lay_language > medical_terminology > typo_variant = emotional"

requirements-completed: [EVAL-01, EVAL-06]

# Metrics
duration: 2min
completed: 2026-03-02
---

# Phase 6 Plan 1: Evaluation Test Data Summary

**58-query golden dataset and 20-query refusal dataset in JSONL format covering 9 content categories, 4 query types (including emotional/panicked phrasing), and 4 refusal categories**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-02T17:31:21Z
- **Completed:** 2026-03-02T17:33:45Z
- **Tasks:** 2
- **Files created:** 2

## Accomplishments
- Golden dataset with 58 in-scope evaluation queries spanning all 9 content categories (medical, water, shelter, first_aid, food, fire, tools, signaling, navigation)
- Full query type coverage: 22 lay_language, 16 medical_terminology, 10 typo_variant, 10 emotional -- with emotional queries reflecting realistic panicked/urgent phrasing per EVAL-06
- 18 safety-critical queries targeting medical procedures (tourniquets, CPR, burns, bleeding, hypothermia, chest wounds) that must surface safety warnings
- Refusal dataset with 20 out-of-scope queries distributed evenly across 4 categories (off_topic, diagnosis_request, harmful, outside_kb) with 5 queries each
- Expected chunk IDs reference 30+ actual corpus documents (FM-21-76, stop-the-bleed, hypothermia-prevention, venomous-snakes, etc.) using the deterministic `{source}_{page:03d}_{chunk:03d}` format

## Task Commits

Each task was committed atomically:

1. **Task 1: Create golden query dataset** - `5c3bf73` (feat)
2. **Task 2: Create refusal query dataset** - `8a2f6b3` (feat)

## Files Created/Modified
- `data/eval/golden_queries.jsonl` - 58 in-scope evaluation queries with expected chunk IDs, key facts, category tags, and query type classification
- `data/eval/refusal_queries.jsonl` - 20 out-of-scope queries across 4 refusal categories, all with expected_action="refuse"

## Decisions Made
- **58 queries instead of minimum 50:** Extra queries provide better coverage across the 9 categories and 4 query types without significantly increasing evaluation runtime
- **Chunk IDs based on section files, not ChromaDB lookup:** Since ChromaDB is not yet populated (per STATE.md pending todos), expected chunk IDs were constructed from the deterministic chunk ID format using actual processed section filenames as reference. The evaluation runner (Plan 02) will include a pre-flight check validating these IDs exist before scoring
- **Emotional queries use realistic distress patterns:** "my kid fell and wont stop bleeding what do i do", "im freezing and cant feel my fingers help" -- lowercase, no punctuation, fragmented, reflecting how people actually type in emergencies
- **Refusal queries carefully avoid semantic overlap:** Per Pitfall 2 from RESEARCH.md, harmful queries like "best way to start a wildfire" are distinct from in-scope survival content like "how to start a fire". Off-topic queries use domains with zero survival overlap (pizza, quantum computing, Rubiks cube)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Both JSONL datasets ready for consumption by `pipeline/evaluate.py` in Plan 02
- Golden dataset schema matches the interfaces defined in CONTEXT.md and RESEARCH.md
- Refusal dataset distribution matches the 4-category x 5-query structure specified in CONTEXT.md
- Pre-flight chunk ID validation will be needed in Plan 02 since ChromaDB corpus ingestion is pending

## Self-Check: PASSED

- FOUND: data/eval/golden_queries.jsonl
- FOUND: data/eval/refusal_queries.jsonl
- FOUND: 06-01-SUMMARY.md
- FOUND: commit 5c3bf73
- FOUND: commit 8a2f6b3

---
*Phase: 06-evaluation-framework*
*Completed: 2026-03-02*
