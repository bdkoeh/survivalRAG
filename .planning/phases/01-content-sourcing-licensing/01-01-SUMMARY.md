---
phase: 01-content-sourcing-licensing
plan: 01
subsystem: content
tags: [curl, sha256, bash, pdf, government-documents, public-domain]

# Dependency graph
requires: []
provides:
  - 16 initial Tier 1 public domain PDFs downloaded and verified (6 military, 4 FEMA, 6 CDC) — expanded to 71 PDFs / 11 agencies in Plans 01-03/01-04
  - Idempotent download script with fallback URLs and PDF format validation
  - SHA-256 checksums for all downloaded documents
  - Checksum verification script
affects: [01-02-PLAN (manifests), 02-document-processing]

# Tech tracking
tech-stack:
  added: [curl, sha256sum, bash]
  patterns: [idempotent-download, pdf-format-validation, wayback-id-modifier]

key-files:
  created:
    - sources/scripts/download-all.sh
    - sources/scripts/verify-checksums.sh
    - sources/checksums.sha256
    - sources/scripts/download-report.txt
  modified:
    - .gitignore

key-decisions:
  - "Used Wayback Machine id_ modifier for raw PDF download (standard Wayback returns HTML wrapper)"
  - "FM-21-76-1 fallback from trueprepper.com (FAS primary URL returned empty file)"
  - "Are You Ready? sourced from Wayback Machine (FEMA.gov URL no longer accessible)"
  - "Added PDF header validation (%PDF magic bytes) to reject HTML error pages saved as .pdf"
  - "CDC Keep Food Safe web page deferred for manual capture (wkhtmltopdf not available)"

patterns-established:
  - "PDF download validation: check both file size (>1KB) AND PDF magic bytes (%PDF header)"
  - "Wayback Machine raw download: use id_ modifier (web.archive.org/web/YYYYid_/URL) not /web/latest/"
  - "Download script idempotency: skip files that already exist and pass size check"

requirements-completed: [CONT-01, CONT-05]

# Metrics
duration: 8min
completed: 2026-02-28
---

# Phase 1 Plan 01: Download Tier 1 Source Documents Summary

**16 of 17 Tier 1 public domain PDFs downloaded with SHA-256 integrity verification via idempotent bash scripts with fallback URLs and PDF format validation**

## Performance

- **Duration:** 8 min
- **Started:** 2026-02-28T21:51:14Z
- **Completed:** 2026-02-28T22:00:01Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Downloaded 16 of 17 Tier 1 public domain documents (6 military, 4 FEMA, 6 CDC)
- Created idempotent download script with primary URLs, fallback URLs, Wayback Machine last resort, and PDF format validation
- Generated and verified SHA-256 checksums for all 16 documents
- Established sources/originals/ directory structure with PDFs excluded from git

## Task Commits

Each task was committed atomically:

1. **Task 1: Create directory structure and download script** - `9ae64a8` (feat)
2. **Task 2: Execute downloads and verify acquisition** - `6824b16` (feat)

## Files Created/Modified
- `sources/scripts/download-all.sh` - Idempotent download script with all Tier 1 URLs, fallback URLs, Wayback Machine, and PDF validation (345 lines)
- `sources/scripts/verify-checksums.sh` - SHA-256 checksum verification script (82 lines)
- `sources/checksums.sha256` - SHA-256 checksums for all 16 downloaded PDFs
- `sources/scripts/download-report.txt` - Detailed download report with sources and issues
- `.gitignore` - Added sources/originals/ exclusion (PDFs not committed to git)
- `sources/originals/military/.gitkeep` - Directory structure placeholder
- `sources/originals/fema/.gitkeep` - Directory structure placeholder
- `sources/originals/cdc/.gitkeep` - Directory structure placeholder

## Documents Downloaded

### Military (6 of 6)
| Document | Size | Source |
|----------|------|--------|
| FM-21-76.pdf (US Army Survival Manual, 1992) | 52.4 MB | bits.de (primary) |
| FM-21-76-1.pdf (Survival, Evasion, and Recovery, 1999) | 1.27 MB | trueprepper.com (fallback) |
| FM-21-10.pdf (Field Hygiene and Sanitation, 2000) | 2.91 MB | archive.org (fallback) |
| FM-4-25-11.pdf (First Aid, 2002) | 2.62 MB | globalsecurity.org (primary) |
| TC-4-02-3.pdf (Field Hygiene, 2015) | 362 KB | armypubs.army.mil (primary) |
| TC-4-02-1.pdf (First Aid, 2016) | 1.63 MB | rdl.train.army.mil (primary) |

### FEMA (4 of 4)
| Document | Size | Source |
|----------|------|--------|
| are-you-ready.pdf (Citizen Preparedness Guide) | 22.1 MB | Wayback Machine id_ |
| food-and-water-in-emergency.pdf | 603 KB | fema.gov (primary) |
| how-to-build-emergency-kit.pdf | 36.5 KB | fema.gov (primary) |
| basic-preparedness.pdf | 1.21 MB | fema.gov (primary) |

### CDC (6 of 7)
| Document | Size | Source |
|----------|------|--------|
| emergency-wound-care.pdf | 353 KB | cdc.gov (primary) |
| make-water-safe-emergency.pdf | 731 KB | cdc.gov (primary) |
| use-safe-water-emergency.pdf | 141 KB | cdc.gov (primary) |
| keep-food-water-safe.pdf | 97.9 KB | stacks.cdc.gov (primary) |
| all-hazards-preparedness-guide.pdf | 19.8 MB | stacks.cdc.gov (primary) |
| public-health-emergency-response.pdf | 2.57 MB | stacks.cdc.gov (primary) |

### Missing (1 of 17)
| Document | Reason |
|----------|--------|
| keep-food-safe-disaster.pdf | CDC web page, not PDF. wkhtmltopdf not available for conversion. Manual browser Print-to-PDF needed. |

## Decisions Made
1. **Wayback Machine id_ modifier**: Standard Wayback Machine URLs (`/web/latest/`) return HTML wrapper pages, not raw files. Using the `id_` modifier (`/web/YYYYid_/URL`) returns the original file directly. This was discovered when both FM-21-76-1 and Are You Ready? downloaded as HTML.
2. **FM-21-76-1 fallback source**: Primary URL (irp.fas.org) returned an empty file. Used trueprepper.com as fallback. Distribution Statement A is verified independently via FAS, GlobalSecurity, and EverySpec.com regardless of download source.
3. **Are You Ready? from Wayback**: FEMA.gov no longer hosts this PDF at the expected URL (likely due to site restructuring). Navy CNIC fallback also failed (403). Wayback Machine with id_ modifier provided the authentic 22 MB PDF.
4. **PDF format validation**: Added `%PDF` magic byte checking to the download function to prevent saving HTML error pages as .pdf files. This caught the two Wayback Machine issues during initial download.
5. **CDC web page deferred**: CDC "Keep Food Safe After a Disaster" exists only as a web page. Without wkhtmltopdf, manual browser capture is needed. This is 1 factsheet out of 17 documents and does not block the phase.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Wayback Machine returned HTML wrapper instead of PDF for two files**
- **Found during:** Task 2 (Execute downloads)
- **Issue:** Both FM-21-76-1.pdf and are-you-ready.pdf were downloaded as HTML pages (Wayback Machine HTML wrappers) rather than actual PDFs. Both had identical checksums (154,377 bytes each).
- **Fix:** For FM-21-76-1, downloaded from trueprepper.com fallback (verified 107-page PDF). For Are You Ready?, used Wayback Machine with `id_` modifier for raw download (22 MB PDF). Updated download script with PDF format validation and working fallback URLs.
- **Files modified:** sources/scripts/download-all.sh, sources/scripts/download-report.txt
- **Verification:** All 16 files confirmed as valid PDFs via `file` command. All checksums unique and verified.
- **Committed in:** 6824b16 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Essential fix -- without PDF validation, two files would have been unusable HTML pages. No scope creep.

## Issues Encountered
- **FEMA.gov URL restructuring**: The primary FEMA.gov URL for "Are You Ready?" returned 404. This is a known risk (documented in research). Resolved via Wayback Machine.
- **Internet Archive 503**: archive.org returned 503 (service unavailable) during some download attempts. Not all fallback URLs using archive.org worked. The `id_` modifier on Wayback Machine proved more reliable for direct file access.
- **FAS.org empty file**: irp.fas.org returned a 0-byte file for FM-21-76-1. This was caught by the size validation check.

## User Setup Required

None - no external service configuration required. To re-download documents, run `bash sources/scripts/download-all.sh` from the project root.

## Next Phase Readiness
- All 16 initial Tier 1 PDFs are available for Plan 02 (expanded to 71 PDFs / 11 agencies in Plans 01-03/01-04)
- Directory structure is established: sources/originals/ with 11 agency subdirectories
- Checksums recorded for integrity verification during processing phases
- 1 document (CDC "Keep Food Safe" web page) needs manual PDF capture before Phase 2

## Self-Check: PASSED

All files verified present. Both task commits found (9ae64a8, 6824b16).

---
*Phase: 01-content-sourcing-licensing*
*Completed: 2026-02-28*
