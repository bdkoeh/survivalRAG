# WikiMed Extraction Plan

## Status: Deferred (Planning Only)

This document plans the future extraction of curated Wikipedia medical articles for Tier 2 content. Execution is deferred to a separate phase/task after the core Tier 1 pipeline is proven.

## Scope

- **Target**: ~500-1000 Wikipedia medical articles curated by WikiProject Medicine
- **Quality filter**: Articles rated B-class or above by WikiProject Medicine importance ratings
- **License**: CC BY-SA 4.0 (Creative Commons Attribution-ShareAlike)

## Target Categories

Articles from these medical/survival-relevant categories:

1. **Emergency Medicine** - cardiac arrest, shock, anaphylaxis, acute abdomen
2. **Trauma** - fractures, burns, lacerations, crush injury, blast injury
3. **Wound Healing** - wound infection, suturing, debridement, tetanus
4. **Infectious Disease** - waterborne diseases, zoonoses, wound infections, tropical diseases
5. **Toxicology** - snakebite, spider bite, poisonous plants, mushroom poisoning, carbon monoxide
6. **Environmental Medicine** - hypothermia, hyperthermia, altitude sickness, dehydration, drowning
7. **First Aid** - CPR, choking, bleeding control, splinting, triage
8. **Nutrition & Hydration** - malnutrition, dehydration, water purification, edible plants
9. **Mental Health** - PTSD, acute stress reaction, psychological first aid

## Extraction Approach

### Option A: Wikipedia API (Recommended)
- Use Wikipedia API to fetch article content by title
- Filter by WikiProject Medicine category and quality rating
- Extract plain text or HTML, convert to markdown
- Pros: Incremental, can filter by quality, respects rate limits
- Cons: Slower, requires building title list

### Option B: Wikipedia Dump
- Download latest Wikipedia dump (English)
- Parse XML dump to extract target articles
- Filter by category membership
- Pros: Complete, offline processing, faster bulk extraction
- Cons: Very large download (~20GB compressed), requires dump parsing tools

### Recommended: Option A with pre-built title list from PetScan/SPARQL query of WikiProject Medicine articles.

## License Implications

**CC BY-SA 4.0 differs from public domain:**
- **Attribution required**: Must credit Wikipedia and article contributors
- **Share-alike required**: Derivative works must use same or compatible license
- **Not public domain**: Cannot strip license; must preserve attribution chain

**Impact on SurvivalRAG:**
- Tier 2 content must be architecturally separated from Tier 1 (public domain)
- Each chunk from Wikipedia must carry CC BY-SA 4.0 attribution metadata
- Responses citing Wikipedia content must include attribution notice
- Project license (MIT/Apache 2.0) is compatible as long as Wikipedia content carries its own license

## Quality Assurance

- WikiProject Medicine B-class articles have been reviewed for medical accuracy
- Cross-reference with MedlinePlus for fact verification
- Flag articles with active dispute/cleanup tags
- Exclude stub articles and articles with insufficient references

## Provenance Tracking

Each Wikipedia article manifest would include:
- Article title and permanent revision ID
- Extraction date
- WikiProject Medicine quality rating
- CC BY-SA 4.0 license with attribution to Wikipedia contributors
- Article URL with revision ID for reproducibility

## Open Questions

1. Should we extract the full article or only specific sections (e.g., Signs/Symptoms, Treatment, First Aid)?
2. What is the minimum WikiProject Medicine quality rating to include?
3. How do we handle articles that span multiple medical topics?
4. Should we include article images (most are CC BY-SA but some have other licenses)?

---

*Created: 2026-02-28*
*Status: Planning only - execution deferred*
