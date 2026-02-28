# Phase 1 Discussion Context

**Phase:** Content Sourcing & Licensing
**Discussed:** 2026-02-28

## Decisions from Discussion

### Licensing
- **Restricted documents → exclude, move on.** Conservative default. If a Tier 1 doc is not clearly Distribution Statement A, drop it. Don't spend time trying to get it cleared.
- **Ambiguous = excluded.** No gray area.

### CDC/FEMA Scope
- **Research specific publications in Phase 1.** The brief says "CDC disaster first aid, wound care, water treatment, and food safety guidelines" but doesn't name specific publications. Part of Phase 1 work is identifying exactly which CDC and FEMA pages/PDFs to include.

### Downloads
- **Claude automates via scripts.** Write download scripts targeting official sources. Don't expect the user to manually gather PDFs.

### Source Priority
- **Official .mil/.gov preferred.** Try armypubs.army.mil, FEMA.gov, CDC.gov first.
- **Third-party fallback OK** (liberatedmanuals.com, Internet Archive, etc.) only if the official source is unavailable AND the distribution statement can be verified against the official record.

### Manifest Format
- **One YAML per document.** Location flexible — research/planner decides.
- User has no strong preference on format details.

### Scope Boundary
- **Phase 1 = documents only. No code scaffolding.** No pyproject.toml, no directory structure, no Docker skeleton. Just:
  1. Identify specific documents to include
  2. Verify licensing per-document from official sources
  3. Download PDFs (automated where possible)
  4. Create provenance manifests
  5. Exclude anything ambiguous

## Tier 1 Document List (from brief)

**Military (verify Distribution Statement A from armypubs.army.mil):**
- FM 21-76: US Army Survival Manual
- FM 3-05.70: Survival
- FM 21-76-1: Survival, Evasion, and Recovery (pocket guide)
- ST 31-91B: Special Forces Medical Handbook (400+ pages)
- FM 21-10: Field Hygiene and Sanitation
- FM 4-25.11: First Aid

**Civilian government (public domain by default as US gov works):**
- FEMA "Are You Ready?" Citizen Preparedness Guide
- FEMA emergency water and food storage guides
- CDC disaster first aid, wound care, water treatment, food safety guidelines (specific pubs TBD)

## Key Risk
ST 31-91B (SF Medical Handbook) is the highest-risk document for distribution restrictions — it's a Special Forces publication. If it's restricted, exclude and find an alternative covering field medicine.

## Requirements Covered
CONT-01, CONT-02, CONT-03, CONT-04, CONT-05
