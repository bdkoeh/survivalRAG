---
phase: 01-content-sourcing-licensing
plan: 02
subsystem: content
tags: [yaml, provenance, licensing, validation, distribution-statement, public-domain]

# Dependency graph
requires:
  - 01-01 (downloaded PDFs, checksums)
provides:
  - 16 YAML provenance manifests with verified licensing for all Tier 1 documents
  - Exclusion documentation for 3 rejected documents (FM 3-05.70, ST 31-91B, FM 3-50.3)
  - Automated manifest validation script (Python and bash versions)
  - Complete provenance chain linking manifests to PDFs to checksums
affects: [02-document-processing]

# Tech tracking
tech-stack:
  added: [yaml, sha256-cross-reference]
  patterns: [provenance-manifest-schema-v1, exclusion-documentation, automated-validation]

key-files:
  created:
    - sources/manifests/FM-21-76.yaml
    - sources/manifests/FM-21-76-1.yaml
    - sources/manifests/FM-21-10.yaml
    - sources/manifests/FM-4-25-11.yaml
    - sources/manifests/TC-4-02-3.yaml
    - sources/manifests/TC-4-02-1.yaml
    - sources/manifests/are-you-ready.yaml
    - sources/manifests/food-and-water-in-emergency.yaml
    - sources/manifests/how-to-build-emergency-kit.yaml
    - sources/manifests/basic-preparedness.yaml
    - sources/manifests/emergency-wound-care.yaml
    - sources/manifests/make-water-safe-emergency.yaml
    - sources/manifests/use-safe-water-emergency.yaml
    - sources/manifests/keep-food-water-safe.yaml
    - sources/manifests/all-hazards-preparedness-guide.yaml
    - sources/manifests/public-health-emergency-response.yaml
    - sources/excluded/EXCLUDED.md
    - sources/scripts/validate-manifests.py
    - sources/scripts/validate-manifests.sh
  modified: []

key-decisions:
  - "Schema version 1.0 with 5 top-level sections: document, source, licensing, content, processing"
  - "Military documents verified via Distribution Statement A; civilian documents verified via 17 U.S.C. 105 (US Government Work)"
  - "Bash validation script created alongside Python script since Python/PyYAML not available on build system"
  - "No manifest for CDC Keep Food Safe web page (not downloaded in 01-01)"

patterns-established:
  - "YAML provenance manifest schema v1.0: document/source/licensing/content/processing sections"
  - "Distribution statement verification: military docs need explicit Dist Statement A; FEMA/CDC are inherently public domain"
  - "Cross-reference validation: manifest SHA-256 matches both checksums.sha256 file and actual file on disk"
  - "Exclusion documentation pattern: reason, verification source, verification date, alternative included"

requirements-completed: [CONT-02, CONT-03, CONT-04]

# Metrics
duration: 5min
completed: 2026-02-28
---

# Phase 1 Plan 02: Create Provenance Manifests and Validate Summary

**16 YAML provenance manifests with verified licensing (Distribution Statement A for military, 17 U.S.C. 105 for civilian), exclusion documentation for 3 rejected documents, and automated validation confirming complete provenance chain**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-28T22:03:38Z
- **Completed:** 2026-02-28T22:09:14Z
- **Tasks:** 2
- **Files created:** 19

## Accomplishments

- Created 16 YAML provenance manifests (6 military, 4 FEMA, 6 CDC) following schema v1.0
- Every manifest includes: document metadata, source URLs, licensing verification, content categories, processing notes, and SHA-256 checksums
- All 6 military documents verified with Distribution Statement A ("Approved for public release; distribution is unlimited")
- All 10 civilian documents verified as US Government Works (public domain under 17 U.S.C. 105)
- Documented 3 excluded documents with reasons: FM 3-05.70 (restricted), ST 31-91B (ambiguous), FM 3-50.3 (unverifiable)
- Created validation script in both Python (for future use) and bash (for immediate validation)
- All 16 manifests pass automated validation: schema completeness, SHA-256 cross-reference, licensing verification, orphan check, and exclusion cross-check

## Task Commits

Each task was committed atomically:

1. **Task 1: Create YAML provenance manifests and exclusion documentation** - `905cfd0` (feat)
2. **Task 2: Create validation script and verify provenance chain** - `b45d422` (feat)

## Files Created

### Manifests (16 files)
| Manifest | Document | Publisher | License Verification |
|----------|----------|-----------|---------------------|
| FM-21-76.yaml | US Army Survival Manual (1992) | Department of the Army | Distribution Statement A |
| FM-21-76-1.yaml | Survival, Evasion, and Recovery (1999) | Department of the Army | Distribution Statement A |
| FM-21-10.yaml | Field Hygiene and Sanitation (2000) | Department of the Army | Distribution Statement A |
| FM-4-25-11.yaml | First Aid (2002) | Department of the Army | Distribution Statement A |
| TC-4-02-3.yaml | Field Hygiene and Sanitation (2015) | Department of the Army | Distribution Statement A |
| TC-4-02-1.yaml | First Aid (2016) | Department of the Army | Distribution Statement A |
| are-you-ready.yaml | Are You Ready? Citizen Preparedness (IS-22) | FEMA | US Gov Work - 17 U.S.C. 105 |
| food-and-water-in-emergency.yaml | Food and Water in an Emergency | FEMA / ARC | US Gov Work - 17 U.S.C. 105 |
| how-to-build-emergency-kit.yaml | How to Build a Kit for Emergencies | FEMA | US Gov Work - 17 U.S.C. 105 |
| basic-preparedness.yaml | Basic Preparedness | FEMA | US Gov Work - 17 U.S.C. 105 |
| emergency-wound-care.yaml | Emergency Wound Care After a Natural Disaster | CDC | US Gov Work - 17 U.S.C. 105 |
| make-water-safe-emergency.yaml | How to Make Water Safe in an Emergency | CDC | US Gov Work - 17 U.S.C. 105 |
| use-safe-water-emergency.yaml | Use Safe Water During an Emergency | CDC | US Gov Work - 17 U.S.C. 105 |
| keep-food-water-safe.yaml | Keep Food and Water Safe After a Natural Disaster | CDC | US Gov Work - 17 U.S.C. 105 |
| all-hazards-preparedness-guide.yaml | All-Hazards Preparedness Guide | CDC | US Gov Work - 17 U.S.C. 105 |
| public-health-emergency-response.yaml | Public Health Emergency Response Guide v2.0 | CDC | US Gov Work - 17 U.S.C. 105 |

### Other Files
- `sources/excluded/EXCLUDED.md` - Exclusion documentation for 3 rejected documents
- `sources/scripts/validate-manifests.py` - Python validation script (requires PyYAML)
- `sources/scripts/validate-manifests.sh` - Bash validation script (no dependencies)

## Validation Results

```
RESULT: PASS (all checks passed)
  Manifests validated: 16
  PDFs verified: 16
  Excluded documents: 3
```

All checks passed:
- Schema completeness: 16/16 manifests have all required fields
- SHA-256 cross-reference: All manifest hashes match checksums.sha256 and actual files on disk
- Licensing verification: 6 military (Distribution Statement A), 10 civilian (US Government Work)
- Orphan check: Zero orphan PDFs, zero orphan manifests
- Exclusion cross-check: No manifests exist for FM 3-05.70, ST 31-91B, or FM 3-50.3

## Decisions Made

1. **Manifest schema v1.0**: 5 top-level sections (document, source, licensing, content, processing) plus superseded_by/supersedes at root. Schema version recorded in YAML comments for future migration.
2. **Dual validation scripts**: Created both Python (validate-manifests.py, requires PyYAML) and bash (validate-manifests.sh, no dependencies) validation scripts since Python was not available on the build system. Both perform identical checks.
3. **No manifest for CDC Keep Food Safe**: This web page was not downloaded in Plan 01 (wkhtmltopdf not available). No manifest created per plan instructions -- manifests only for successfully downloaded documents.
4. **Supersession tracking**: Each manifest records superseded_by and supersedes relationships between military document editions, establishing a clear lineage (e.g., FM 21-10 superseded by TC 4-02.3).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Python not available on build system**
- **Found during:** Task 2
- **Issue:** The plan specifies creating and running `validate-manifests.py`, but Python is not installed on this Windows system (Microsoft Store alias only, no actual installation).
- **Fix:** Created the Python script as specified for future use, and additionally created `validate-manifests.sh` (bash equivalent) that performs all the same checks. Ran the bash version for validation.
- **Files created:** sources/scripts/validate-manifests.sh
- **Committed in:** b45d422 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 3 - Blocking)
**Impact on plan:** Validation still performed with identical rigor. Python script is available for future use when Python is installed.

## Issues Encountered

- **No Python on build system**: Python/PyYAML not available. Resolved with bash alternative.
- **No issues with manifest creation**: All checksums, URLs, and licensing data matched expected values from research and download report.

## Next Phase Readiness

- Phase 1 is now complete: all 16 Tier 1 documents are downloaded, checksummed, and have provenance manifests
- 3 excluded documents are formally documented with reasons and alternatives
- The sources/ directory is a complete, auditable record ready for Phase 2 (Document Processing)
- 1 document (CDC "Keep Food Safe" web page) still needs manual PDF capture -- documented in STATE.md pending todos

## Self-Check: PASSED
