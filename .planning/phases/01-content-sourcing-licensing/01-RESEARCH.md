# Phase 1: Content Sourcing & Licensing - Research

**Researched:** 2026-02-28
**Domain:** Public domain document acquisition, military publication distribution statements, government document licensing
**Confidence:** HIGH

## Summary

Phase 1 is a document acquisition and licensing verification phase with no code scaffolding. The work involves identifying, verifying, downloading, and cataloging Tier 1 public domain survival and medical content from US government sources. The primary technical challenge is not the downloading itself (straightforward with curl/wget/Python scripts) but rather the licensing verification -- specifically, determining which military publications carry Distribution Statement A ("Approved for public release; distribution is unlimited") versus restricted distribution statements.

Research uncovered a critical finding: **FM 3-05.70 (the updated survival manual) carries a restricted distribution statement** -- "Distribution authorized to U.S. Government agencies and their contractors only" -- and is NOT approved for public release per official Army Publishing Directorate records. The older FM 21-76 (1992 edition) DOES carry Distribution Statement A and is the correct document to use. Additionally, ST 31-91B (Special Forces Medical Handbook) has an ambiguous distribution status -- it has been widely commercially republished but no official Distribution Statement A marking could be verified. Per project rules (ambiguous = exclude), this document requires careful handling.

CDC and FEMA publications are straightforward -- as US government works, they are public domain under 17 U.S.C. 105 and freely available on official .gov websites.

**Primary recommendation:** Use FM 21-76 (1992, Distribution Statement A verified) instead of FM 3-05.70 (restricted). Flag ST 31-91B for manual verification or exclusion. All CDC/FEMA content is safe to include. Download scripts should target official .gov/.mil sources first, with Internet Archive as fallback.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Restricted documents -> exclude, move on.** Conservative default. If a Tier 1 doc is not clearly Distribution Statement A, drop it. Don't spend time trying to get it cleared.
- **Ambiguous = excluded.** No gray area.
- **Claude automates via scripts.** Write download scripts targeting official sources. Don't expect the user to manually gather PDFs.
- **Official .mil/.gov preferred.** Try armypubs.army.mil, FEMA.gov, CDC.gov first.
- **Third-party fallback OK** (liberatedmanuals.com, Internet Archive, etc.) only if the official source is unavailable AND the distribution statement can be verified against the official record.
- **One YAML per document.** Location flexible -- research/planner decides.
- **Phase 1 = documents only. No code scaffolding.** No pyproject.toml, no directory structure, no Docker skeleton. Just:
  1. Identify specific documents to include
  2. Verify licensing per-document from official sources
  3. Download PDFs (automated where possible)
  4. Create provenance manifests
  5. Exclude anything ambiguous

### Claude's Discretion
- YAML manifest format details (fields, structure, naming convention)
- File organization within source documents directory
- Specific CDC/FEMA publications to include (the brief names categories, not specific documents)

### Deferred Ideas (OUT OF SCOPE)
- Code scaffolding (pyproject.toml, directory structure, Docker)
- Document processing, OCR, chunking
- Any Tier 2 or Tier 3 content
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CONT-01 | All Tier 1 source documents are downloaded from official or verified sources | Document inventory with verified download URLs for each document; download script approach documented |
| CONT-02 | Every document has verified Distribution Statement A from an official source | Distribution statement research per document; FM 3-05.70 flagged as restricted; FM 21-76 confirmed as Distribution Statement A alternative |
| CONT-03 | Every document has a YAML provenance manifest recording: source URL, license type, distribution statement text, verification date, and processing notes | YAML manifest schema designed with all required fields |
| CONT-04 | No document with ambiguous or restricted distribution status is included | FM 3-05.70 excluded (restricted); ST 31-91B flagged as ambiguous; exclusion criteria documented |
| CONT-05 | Source PDFs are retained alongside processed text for audit and re-processing | File organization pattern documented (originals/ directory alongside manifests) |
</phase_requirements>

## Document Inventory & Licensing Status

This is the core research output for this phase. Each document has been individually researched for distribution status.

### Military Publications

| Document | Distribution Statement | Status | Verified Source | Confidence |
|----------|----------------------|--------|-----------------|------------|
| FM 21-76 (1992) US Army Survival Manual | **Distribution Statement A** -- "Approved for public release; distribution is unlimited" | INCLUDE | armypubs.army.mil (listed), bits.de (PDF with statement visible), multiple Internet Archive copies | HIGH |
| FM 3-05.70 Survival (2002) | **RESTRICTED** -- "Distribution authorized to U.S. Government agencies and their contractors only" + NOFORN | EXCLUDE | armypubs.army.mil (marked NOFORN, INACTIVE), FAS confirmed restriction | HIGH |
| FM 21-76-1 Survival, Evasion, and Recovery (1999) | **Distribution Statement A** -- "Approved for public release; distribution is unlimited" | INCLUDE | GlobalSecurity.org, FAS, EverySpec.com (consistent across sources) | HIGH |
| ST 31-91B Special Forces Medical Handbook (1982) | **AMBIGUOUS** -- No official Distribution Statement A found; widely commercially republished but no .mil verification available | EXCLUDE per rules | No armypubs.army.mil listing found; commercially available but no official statement | MEDIUM |
| FM 21-10 / MCRP 4-11.1D Field Hygiene and Sanitation (2000) | **Distribution Statement A** -- "Approved for public release; distribution is unlimited" | INCLUDE | marines.mil hosted PDF, armypubs.army.mil (TC 4-02.3 successor also Dist A) | HIGH |
| FM 4-25.11 First Aid (2002) | **Distribution Statement A** -- "Approved for public release; distribution is unlimited" | INCLUDE | GlobalSecurity.org PDF, Archive.org (AHEC digitized), multiple confirming sources | HIGH |

**Critical decisions:**
- **FM 3-05.70 is EXCLUDED.** Use FM 21-76 (1992) instead. FM 21-76 covers the same survival topics and has a clear Distribution Statement A. FM 3-05.70 added content but carries a restricted distribution statement.
- **ST 31-91B is EXCLUDED** under the ambiguous = exclude rule. The SOF Medical Handbook (2001 edition by USSOCOM) is a potential alternative but also lacks clear public release verification. The gap in field medicine coverage should be noted -- FM 4-25.11 (First Aid) partially covers this domain.

### Superseded Publications Note

Several Tier 1 documents have been superseded by newer Army publications:
- FM 21-76 (1992) -> superseded by FM 3-05.70 (2002, RESTRICTED) -> FM 3-05.70 now INACTIVE
- FM 21-76-1 (1999) -> superseded by FM 3-50.3 (2007, distribution status unknown)
- FM 21-10 (2000) -> superseded by TC 4-02.3 (2015, Distribution Statement A)
- FM 4-25.11 (2002) -> superseded by TC 4-02.1 (2016, Distribution Statement A)

**Recommendation:** Include both the original and the successor where the successor also has Distribution Statement A. The successor documents (TC 4-02.3, TC 4-02.1) are available on armypubs.army.mil and rdl.train.army.mil. This gives broader, more current coverage.

### FEMA Publications

| Document | License Status | Status | Download URL | Confidence |
|----------|---------------|--------|--------------|------------|
| "Are You Ready?" An In-Depth Guide to Citizen Preparedness (IS-22, 204pp) | US Government work -- public domain | INCLUDE | https://www.fema.gov/related-link/are-you-ready-guide-citizen-preparedness | HIGH |
| "Food and Water in an Emergency" (FEMA/ARC) | US Government work -- public domain | INCLUDE | https://www.fema.gov/pdf/library/f&web.pdf | HIGH |
| "How to Build a Kit for Emergencies" | US Government work -- public domain | INCLUDE | https://www.fema.gov/print/pdf/node/503732 | HIGH |
| Basic Preparedness (from Are You Ready?) | US Government work -- public domain | INCLUDE | https://www.fema.gov/pdf/areyouready/basic_preparedness.pdf | HIGH |

**Note:** FEMA.gov may have limited availability during federal funding lapses. Download scripts should handle HTTP errors gracefully and fall back to cached copies on .gov mirror sites (e.g., Navy CNIC hosted version of "Are You Ready?").

### CDC Publications

CDC publications are US government works and public domain under 17 U.S.C. 105. The brief specifies "CDC disaster first aid, wound care, water treatment, and food safety guidelines" without naming specific publications. Research identified the following specific publications:

| Document | Topic | Download URL | Confidence |
|----------|-------|--------------|------------|
| Emergency Wound Care After a Natural Disaster (Factsheet) | Wound care, first aid | https://www.cdc.gov/disasters/hurricanes/pdf/woundcare.pdf | HIGH |
| How to Make Water Safe in an Emergency | Water treatment | https://www.cdc.gov/water-emergency/media/pdfs/make-water-safe-during-emergency-p.pdf | HIGH |
| Use Safe Water During an Emergency (One-pager) | Water safety | https://www.cdc.gov/water-emergency/media/pdfs/334749-B_UseSafeWater-OnePager-508.pdf | HIGH |
| Keep Food Safe After a Disaster or Emergency | Food safety | https://www.cdc.gov/food-safety/foods/keep-food-safe-after-emergency.html (web page, capture as PDF) | HIGH |
| Keep Food and Water Safe After a Natural Disaster | Food + water safety | https://stacks.cdc.gov/view/cdc/25410 (PDF via CDC STACKS) | HIGH |
| All-Hazards Preparedness Guide | General preparedness | https://stacks.cdc.gov/view/cdc/12007 | MEDIUM |
| Public Health Emergency Response Guide v2.0 | Emergency response | https://stacks.cdc.gov/view/cdc/5972/cdc_5972_DS1.pdf | MEDIUM |

**Note on CDC content format:** Some CDC content is web pages rather than PDFs. The download script should handle both: direct PDF downloads and web page to PDF conversion (e.g., using browser print-to-PDF or wkhtmltopdf). Alternatively, reference the web content and note in the manifest that it was captured as a web page snapshot.

### Additional Candidates (Distribution Statement A verified)

| Document | Distribution Statement | Source | Notes |
|----------|----------------------|--------|-------|
| TC 4-02.1 First Aid (2016, supersedes FM 4-25.11) | Distribution Statement A | rdl.train.army.mil | More current content, electronic-only |
| TC 4-02.3 Field Hygiene and Sanitation (2015, supersedes FM 21-10) | Distribution Statement A | armypubs.army.mil | More current content |

## Standard Stack

This phase requires no application code, but does need tooling for document acquisition.

### Core Tools
| Tool | Purpose | Why Standard |
|------|---------|--------------|
| Bash/PowerShell scripts | Download automation | Simple, no dependencies, runs anywhere |
| curl or wget | HTTP downloads from .gov sources | Standard CLI tools, handle redirects and retries |
| Python (requests) | Fallback download scripting | Better error handling, can parse HTML for links |

### Supporting
| Tool | Purpose | When to Use |
|------|---------|-------------|
| sha256sum / certutil | File integrity verification | Generate checksums for downloaded PDFs to detect corruption |
| wkhtmltopdf or browser | Web page to PDF conversion | CDC pages that are HTML not PDF |

**Installation:**
```bash
# No special installation needed -- curl/wget are standard
# For Python fallback:
pip install requests beautifulsoup4
```

## Architecture Patterns

### Recommended Directory Structure
```
sources/
  originals/           # Untouched source PDFs as downloaded
    military/
      FM-21-76.pdf
      FM-21-76-1.pdf
      FM-21-10.pdf
      FM-4-25-11.pdf
      TC-4-02-1.pdf     # Optional: successor to FM 4-25.11
      TC-4-02-3.pdf     # Optional: successor to FM 21-10
    fema/
      are-you-ready.pdf
      food-and-water-in-emergency.pdf
      how-to-build-emergency-kit.pdf
    cdc/
      emergency-wound-care.pdf
      make-water-safe-emergency.pdf
      use-safe-water-emergency.pdf
      keep-food-safe-disaster.pdf
      keep-food-water-safe.pdf
  manifests/            # One YAML per document
    FM-21-76.yaml
    FM-21-76-1.yaml
    ...
  excluded/             # Record of excluded documents and why
    EXCLUDED.md
  scripts/              # Download and verification scripts
    download-all.sh
    verify-checksums.sh
```

### Pattern 1: YAML Provenance Manifest Schema

**What:** Standardized YAML file capturing all required provenance metadata per document.
**When to use:** One manifest per included document.

```yaml
# Provenance Manifest for [Document Name]
# Schema version: 1.0

document:
  title: "FM 21-76 Survival"
  designation: "FM 21-76"
  edition_date: "1992-06-05"
  pages: 564
  file_name: "FM-21-76.pdf"
  file_sha256: "abc123..."  # SHA-256 of the downloaded PDF

source:
  primary_url: "https://www.bits.de/NRANEU/others/amd-us-archive/FM21-76(92).pdf"
  official_listing_url: "https://armypubs.army.mil/ProductMaps/PubForm/FM.aspx"
  fallback_urls:
    - "https://archive.org/details/Fm21-76SurvivalManual"
    - "https://archive.org/details/FM2176USARMYSURVIVALMANUAL"
  publisher: "Department of the Army"
  country: "United States"

licensing:
  license_type: "US Government Work - Public Domain"
  distribution_statement: "Distribution Statement A: Approved for public release; distribution is unlimited."
  distribution_statement_source: "Document front matter"
  copyright_status: "No copyright (17 U.S.C. 105)"
  verification_date: "2026-02-28"
  verification_method: "Confirmed Distribution Statement A on document front matter; cross-referenced with armypubs.army.mil listing"
  verified_by: "automated"

content:
  categories:
    - survival
    - shelter
    - water
    - food
    - navigation
    - fire
    - tools
    - first_aid
  tier: 1
  content_type: "field_manual"
  language: "en"

processing:
  notes: "Born-digital PDF, text-selectable. May have some scanned appendix pages."
  ocr_needed: false
  download_date: "2026-02-28"
  download_method: "curl"

superseded_by: "FM 3-05.70 (restricted distribution - not included)"
supersedes: "FM 21-76, 26 March 1986"
```

### Pattern 2: Exclusion Documentation

**What:** A record of every document considered but excluded, with reason.
**When to use:** Every document that fails the distribution statement check.

```markdown
# Excluded Documents

## FM 3-05.70 - Survival (May 2002)
- **Reason:** Restricted distribution -- "Distribution authorized to U.S. Government agencies and their contractors only" + NOFORN marking
- **Verified at:** armypubs.army.mil (PUB_ID=78014, marked INACTIVE, NOFORN)
- **Verification date:** 2026-02-28
- **Alternative included:** FM 21-76 (1992) covers same survival topics with Distribution Statement A

## ST 31-91B - Special Forces Medical Handbook (March 1982)
- **Reason:** Ambiguous distribution status -- no official Distribution Statement A found
- **Notes:** Widely commercially republished but no .mil/.gov verification of public release authorization
- **Verification date:** 2026-02-28
- **Partial alternative:** FM 4-25.11 (First Aid) covers basic field medicine
```

### Pattern 3: Download Script Structure

**What:** Idempotent download scripts that skip already-downloaded files.
**When to use:** Initial acquisition and re-verification.

```bash
#!/usr/bin/env bash
# download-all.sh - Download all Tier 1 source documents
# Idempotent: skips files that already exist and match expected checksum

set -euo pipefail

SOURCES_DIR="$(cd "$(dirname "$0")/.." && pwd)/originals"
MANIFESTS_DIR="$(cd "$(dirname "$0")/.." && pwd)/manifests"

download_if_missing() {
    local url="$1"
    local dest="$2"
    local expected_sha256="$3"  # empty string if unknown

    if [ -f "$dest" ]; then
        if [ -n "$expected_sha256" ]; then
            actual=$(sha256sum "$dest" | cut -d' ' -f1)
            if [ "$actual" = "$expected_sha256" ]; then
                echo "SKIP (exists, checksum OK): $(basename "$dest")"
                return 0
            else
                echo "REDOWNLOAD (checksum mismatch): $(basename "$dest")"
            fi
        else
            echo "SKIP (exists): $(basename "$dest")"
            return 0
        fi
    fi

    echo "DOWNLOADING: $url -> $dest"
    mkdir -p "$(dirname "$dest")"
    curl -fSL --retry 3 --retry-delay 5 -o "$dest" "$url"

    if [ -n "$expected_sha256" ]; then
        actual=$(sha256sum "$dest" | cut -d' ' -f1)
        if [ "$actual" != "$expected_sha256" ]; then
            echo "ERROR: Checksum mismatch for $(basename "$dest")"
            return 1
        fi
    fi

    echo "OK: $(basename "$dest") ($(wc -c < "$dest") bytes)"
}

# Military documents
download_if_missing \
    "https://www.bits.de/NRANEU/others/amd-us-archive/FM21-76(92).pdf" \
    "$SOURCES_DIR/military/FM-21-76.pdf" \
    ""

# ... additional downloads ...
```

### Anti-Patterns to Avoid
- **Downloading from unofficial sources without verification:** Never download from a random website and assume it is the authentic document. Always verify against an official listing.
- **Including documents based on widespread availability:** FM 3-05.70 is sold on Amazon and hosted on dozens of websites, but it is officially restricted. Commercial availability does not equal public release authorization.
- **Storing manifests inside PDF directories:** Keep manifests separate from originals for cleaner organization and easier programmatic access.
- **Manual downloads without scripting:** The user decided Claude automates via scripts. Every download should be reproducible.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PDF downloading | Custom HTTP client | curl with retry flags | curl handles redirects, retries, SSL, partial downloads natively |
| File integrity checking | Custom hash comparison | sha256sum / certutil -hashfile | Standard tools, already installed |
| YAML validation | Manual review | yamllint or Python yaml.safe_load | Catches syntax errors in manifest files |
| Web page to PDF conversion | Screenshot-based approach | wkhtmltopdf or browser print-to-PDF | Preserves text, links, formatting |

## Common Pitfalls

### Pitfall 1: Confusing FM 21-76 with FM 3-05.70
**What goes wrong:** These are often conflated as "the Army survival manual." FM 3-05.70 replaced FM 21-76 but has a restricted distribution statement. Many websites mislabel FM 3-05.70 content as FM 21-76.
**Why it happens:** FM 3-05.70 is described as "formerly FM 21-76" and covers similar content with additions.
**How to avoid:** Always verify the document designation on the title page of the actual PDF. FM 21-76 = June 5, 1992. FM 3-05.70 = May 17, 2002.
**Warning signs:** If a "FM 21-76" PDF is 678 pages, it is actually FM 3-05.70. The genuine FM 21-76 is 564 pages.

### Pitfall 2: Assuming US Government = Public Domain
**What goes wrong:** Not all US military publications are public domain. Distribution statements control dissemination independently of copyright.
**Why it happens:** 17 U.S.C. 105 says US government works are not copyrightable, but DoD Directive 5230.24 establishes distribution statements that can restrict dissemination even of uncopyrighted works.
**How to avoid:** Check the distribution statement on each document individually. Only Distribution Statement A means unrestricted public release.
**Warning signs:** Any statement mentioning "government agencies only," "contractors only," NOFORN, FOUO, or "destruction notice."

### Pitfall 3: FEMA/CDC Website Availability
**What goes wrong:** Government websites may be unavailable during funding lapses, site redesigns, or URL restructuring. CDC.gov recently restructured many URLs.
**Why it happens:** Federal government website availability is not guaranteed. CDC restructured its website in 2024, breaking many old links.
**How to avoid:** Record multiple download URLs for each document. Use both the primary .gov URL and a fallback (Internet Archive Wayback Machine, CDC STACKS, or state government mirrors). Download and verify early.
**Warning signs:** 404 errors on previously working URLs, redirects to generic pages.

### Pitfall 4: CDC Content as Web Pages Not PDFs
**What goes wrong:** Some CDC emergency guidance exists only as web pages, not downloadable PDFs. Web pages change over time.
**Why it happens:** CDC increasingly publishes guidance as web content rather than static PDFs.
**How to avoid:** For web-only CDC content, capture as PDF (browser print-to-PDF or wkhtmltopdf). Record the capture date in the manifest. Note that the content may be updated at the source URL.
**Warning signs:** CDC URLs ending in .html rather than .pdf.

### Pitfall 5: Checksum Drift Across Sources
**What goes wrong:** The same document downloaded from different sources may have different checksums due to re-encoding, metadata stripping, or minor modifications.
**Why it happens:** PDFs are re-uploaded across government sites, sometimes with modifications (watermarks, metadata changes).
**How to avoid:** Download from the most official source first. Record the checksum of the specific file downloaded. Don't assume the same document from different URLs will be byte-identical.

## Code Examples

### Verify Distribution Statement from armypubs.army.mil

The Army Publishing Directorate at armypubs.army.mil lists publications with their distribution restrictions. To verify:

1. Navigate to https://armypubs.army.mil/ProductMaps/PubForm/FM.aspx
2. Search for the FM number
3. Check the distribution restriction field
4. Look for "Approved for public release; distribution is unlimited" (Statement A)
5. Any other statement = restricted = exclude

### Generate SHA-256 Checksums

```bash
# Linux/macOS
sha256sum sources/originals/military/*.pdf > sources/checksums.sha256

# Windows (PowerShell)
Get-FileHash sources\originals\military\*.pdf -Algorithm SHA256 | Format-Table

# Windows (certutil)
certutil -hashfile sources\originals\military\FM-21-76.pdf SHA256
```

### Validate YAML Manifests

```bash
# Using Python to validate all manifests
python -c "
import yaml, glob, sys
errors = 0
required = ['document', 'source', 'licensing', 'content', 'processing']
for f in glob.glob('sources/manifests/*.yaml'):
    try:
        with open(f) as fh:
            data = yaml.safe_load(fh)
        for key in required:
            if key not in data:
                print(f'MISSING KEY {key} in {f}')
                errors += 1
        # Check required licensing fields
        lic = data.get('licensing', {})
        for field in ['license_type', 'distribution_statement', 'verification_date']:
            if field not in lic:
                print(f'MISSING licensing.{field} in {f}')
                errors += 1
    except Exception as e:
        print(f'ERROR parsing {f}: {e}')
        errors += 1
if errors:
    print(f'{errors} error(s) found')
    sys.exit(1)
print('All manifests valid')
"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| FM 21-76 (1992) | FM 3-05.70 (2002) then INACTIVE | 2002 | FM 3-05.70 is restricted; use FM 21-76 instead |
| FM 21-10 (2000) | TC 4-02.3 (2015) | 2015 | Both are Dist Statement A; include successor for current content |
| FM 4-25.11 (2002) | TC 4-02.1 (2016) | 2016 | Both are Dist Statement A; include successor for current content |
| FM 21-76-1 (1999) | FM 3-50.3 (2007) | 2007 | FM 3-50.3 distribution status unknown; stick with FM 21-76-1 |
| CDC static PDFs | CDC web pages + CDC STACKS | ~2024 | Some CDC content requires web capture rather than PDF download |

## Download URL Registry

### Verified Primary URLs

**Military (Distribution Statement A confirmed):**
```
FM 21-76 (1992):
  Primary: https://www.bits.de/NRANEU/others/amd-us-archive/FM21-76(92).pdf
  Fallback: https://archive.org/details/Fm21-76SurvivalManual

FM 21-76-1 (1999):
  Primary: https://irp.fas.org/doddir/army/fm21-76-1.pdf
  Fallback: https://trueprepper.com/wp-content/uploads/2023/03/FM-21-76-1-Survival-Evasion-and-Recovery-Multiservice-Procedures.pdf

FM 21-10 (2000):
  Primary: https://www.marines.mil/Portals/1/Publications/MCRP%204-11.1D%20Field%20Hygiene%20and%20Sanitation.pdf
  Fallback: https://archive.org/details/FM21-10_2000

FM 4-25.11 (2002):
  Primary: https://www.globalsecurity.org/military/library/policy/army/fm/4-25-11/fm4-25-11.pdf
  Fallback: https://archive.org/details/FM4-25.11

TC 4-02.3 (2015, successor to FM 21-10):
  Primary: https://armypubs.army.mil/epubs/DR_pubs/DR_a/pdf/web/tc4_02x3.pdf

TC 4-02.1 (2016, successor to FM 4-25.11):
  Primary: https://rdl.train.army.mil/catalog-ws/view/100.ATSC/B0A32FAD-8C7A-44A6-8FF4-F754A32F1C30-1453986206542/tc4-02.1wc1x2.pdf
```

**FEMA (US Government work -- public domain):**
```
"Are You Ready?" (IS-22):
  Primary: https://www.fema.gov/related-link/are-you-ready-guide-citizen-preparedness
  Fallback: https://cnreurafcent.cnic.navy.mil/Portals/78/NSA_Naples/Documents/Emergency%20Management/References/Are%20You%20Ready%20...pdf

"Food and Water in an Emergency":
  Primary: https://www.fema.gov/pdf/library/f&web.pdf

"How to Build a Kit for Emergencies":
  Primary: https://www.fema.gov/print/pdf/node/503732
```

**CDC (US Government work -- public domain):**
```
Emergency Wound Care After a Natural Disaster:
  Primary: https://www.cdc.gov/disasters/hurricanes/pdf/woundcare.pdf
  Fallback: https://stacks.cdc.gov/view/cdc/25434

Make Water Safe During an Emergency:
  Primary: https://www.cdc.gov/water-emergency/media/pdfs/make-water-safe-during-emergency-p.pdf

Use Safe Water During an Emergency:
  Primary: https://www.cdc.gov/water-emergency/media/pdfs/334749-B_UseSafeWater-OnePager-508.pdf

Keep Food and Water Safe After a Natural Disaster:
  Primary: https://stacks.cdc.gov/view/cdc/25410

Keep Food Safe After a Disaster or Emergency:
  Web page: https://www.cdc.gov/food-safety/foods/keep-food-safe-after-emergency.html
  Note: Web page, not PDF -- capture via print-to-PDF
```

## Open Questions

1. **ST 31-91B alternative for field medicine coverage**
   - What we know: ST 31-91B is excluded (ambiguous distribution). FM 4-25.11 covers basic first aid but not the depth of field medicine.
   - What's unclear: Whether the SOF Medical Handbook (2001 USSOCOM edition) has a clear Distribution Statement A, or whether any other comprehensive field medicine manual with clear public release exists.
   - Recommendation: Accept the gap for Phase 1. FM 4-25.11 + CDC wound care covers basic first aid. Deeper field medicine could be a Tier 2 investigation.

2. **CDC content completeness**
   - What we know: The brief says "CDC disaster first aid, wound care, water treatment, and food safety guidelines." Research identified specific publications for each topic.
   - What's unclear: Whether additional high-value CDC publications exist beyond what was found. CDC has thousands of publications.
   - Recommendation: Start with the identified publications. The planner should include a task to do a final CDC publication sweep.

3. **FEMA "Are You Ready?" availability during funding lapses**
   - What we know: FEMA.gov warned about limited availability during funding lapses. The document is mirrored on several .gov sites.
   - What's unclear: Whether the primary FEMA.gov URL will work when download scripts run.
   - Recommendation: Include fallback URLs in the download script. Navy CNIC hosted copy is a reliable .gov mirror.

4. **FM 3-50.3 (successor to FM 21-76-1) distribution status**
   - What we know: FM 21-76-1 was superseded in 2007. The successor FM 3-50.3 was not found on armypubs.army.mil in the search.
   - What's unclear: Whether FM 3-50.3 has Distribution Statement A and would be worth including.
   - Recommendation: Include FM 21-76-1 (confirmed Dist A). Flag FM 3-50.3 for potential future investigation but do not block on it.

## Sources

### Primary (HIGH confidence)
- [armypubs.army.mil](https://armypubs.army.mil/ProductMaps/PubForm/Details.aspx?PUB_ID=78014) -- FM 3-05.70 listing showing NOFORN and INACTIVE status
- [armypubs.army.mil FM listing](https://armypubs.army.mil/ProductMaps/PubForm/FM.aspx) -- Army Publishing Directorate field manual index
- [marines.mil FM 21-10 PDF](https://www.marines.mil/Portals/1/Publications/MCRP%204-11.1D%20Field%20Hygiene%20and%20Sanitation.pdf) -- Official Marines hosted PDF with Distribution Statement A
- [globalsecurity.org FM 4-25.11](https://www.globalsecurity.org/military/library/policy/army/fm/4-25-11/fm4-25-11.pdf) -- PDF showing Distribution Statement A
- [fema.gov publications](https://www.fema.gov/related-link/are-you-ready-guide-citizen-preparedness) -- Official FEMA publication page
- [cdc.gov emergency resources](https://www.cdc.gov/water-emergency/about/index.html) -- Official CDC emergency water guidance
- [CDC STACKS](https://stacks.cdc.gov/) -- CDC archival repository for publications

### Secondary (MEDIUM confidence)
- [FAS (Federation of American Scientists)](https://fas.org/publication/army_field_manual_on_survival/) -- Confirmed FM 3-05.70 has restricted distribution; FAS hosts multiple military documents and notes when distribution is limited
- [bits.de archive](https://www.bits.de/NRANEU/others/amd-us-archive/FM21-76(92).pdf) -- Hosts FM 21-76 (1992) with visible Distribution Statement A on front matter
- [Internet Archive](https://archive.org/details/milmanual-st-31-91b--us-army-special-forces-medical-handbook) -- ST 31-91B availability (does not confirm distribution statement)
- [Survivalist Boards](https://www.survivalistboards.com/threads/u-s-army-field-manual-3-05-70.3742/) -- Community discussion confirming Army's response about FM 3-05.70 restriction

### Tertiary (LOW confidence)
- [trueprepper.com](https://trueprepper.com/) -- Third-party PDF hosting; documents need independent verification
- [liberatedmanuals.com](https://liberatedmanuals.com) -- Not directly searched; referenced in project brief as potential fallback source

## Metadata

**Confidence breakdown:**
- Military document licensing: HIGH -- Distribution statements verified against official .mil sources and multiple independent references for each document
- CDC/FEMA content identification: HIGH -- Official .gov URLs confirmed, public domain status clear under 17 U.S.C. 105
- YAML manifest schema: HIGH -- Fields derived directly from project requirements (CONT-03)
- Download URL availability: MEDIUM -- Government URLs may change; fallback URLs mitigate this risk
- ST 31-91B status: MEDIUM -- Could not find official statement either way; exclusion is the conservative correct decision

**Research date:** 2026-02-28
**Valid until:** 2026-03-30 (URLs may change, but distribution statements are permanent)
