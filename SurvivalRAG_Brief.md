# SurvivalRAG

*A Pre-Built Survival & Medical Knowledge Base for Local LLMs*

---

## What Is This?

SurvivalRAG is an open-source, pre-built retrieval-augmented generation (RAG) knowledge base containing curated public domain survival, medical, and emergency preparedness content. It ships as a ready-to-use package that anyone running a local LLM can deploy immediately — no data collection, document processing, or embedding work required.

It is also the foundational data layer for a larger planned project: an off-grid AI survival assistant accessible over Meshtastic mesh radio (see "Future Vision" below).

## Why Does This Need to Exist?

### The Core Problem

There is no high-quality, pre-built, openly licensed knowledge base optimized for survival and field medicine use cases. This gap forces every person trying to build something useful to repeat the same expensive work from scratch: data curation, licensing research, document processing, chunking strategy, embedding model selection, and evaluation.

### What's Out There Falls Short

Several projects attempt to solve the offline survival AI problem but all share the same fundamental flaw — they place PDFs alongside a generic LLM with no retrieval pipeline connecting the two. The LLM has no awareness of the documents and falls back on training data, which for medical and survival content can be dangerously incomplete or wrong.

| Project | What It Does | Gap |
|---|---|---|
| SurvivalNet ($100–$700) | Pi + offline content + Ollama | No RAG pipeline; LLM has no connection to documents |
| Doom Box ($699) | Ruggedized Pi with offline AI | Same pattern — no structured retrieval |
| R.E.A.D.I. Console | Pi with survival guides + AI | No retrieval, just generic LLM next to PDFs |
| MedRAG | Medical RAG toolkit (public domain code) | Pipeline only, no data; optimized for clinical QA not field medicine |
| MESH-API | Meshtastic-to-LLM bridge | Bridge only, no knowledge base |

Meanwhile, RAG toolkits like LangChain, LlamaIndex, and MedRAG provide excellent retrieval infrastructure but ship zero data.

**SurvivalRAG is the missing data layer that makes all of these projects significantly more useful.**

## Who Is This For?

- **Anyone preparing for emergencies** who wants a local AI that gives grounded answers instead of hallucinated ones
- **Homelab enthusiasts** who want to run a useful local AI service
- **Meshtastic / off-grid builders** who need a knowledge backend for mesh-accessible AI
- **Humanitarian and disaster response organizations** exploring offline AI tools for field deployment
- **Open-source developers** who want to build on top of a solid survival/medical knowledge layer
- **Communities in remote or underserved areas** where reliable internet access isn't guaranteed

## What Should It Do?

The project should deliver these capabilities:

1. **Pre-built knowledge base** — Curated public domain documents cleaned, structured, and embedded, ready for retrieval out of the box
2. **Source-cited responses** — Every answer must cite which source document the information comes from so users can verify
3. **Safety-first responses** — When context is insufficient, the system should say so rather than guess. Safety warnings from source material must be preserved and surfaced.
4. **Field-manual-style answers** — Concise, actionable steps rather than conversational prose
5. **Category-filtered retrieval** — Users should be able to scope queries to specific topics (e.g., only medical, only water-related)
6. **Multiple response modes** — Full responses for local use, compact responses for mobile/low-bandwidth, and ultra-short responses suitable for mesh radio transmission (~200 characters)
7. **Easy deployment** — A new user should be able to go from nothing to a working system quickly with minimal technical knowledge
8. **Query interfaces** — At minimum, a web-based chat interface and a command-line interface
9. **LLM-agnostic** — Should work with the user's choice of local LLM
10. **Fully offline capable** — Must function with no internet connection after initial setup

## What This Project Does NOT Do

- **Diagnose conditions.** This is a reference tool, not a medical system.
- **Replace professional training.** A RAG can recite the steps; it cannot teach the skill.
- **Guarantee accuracy.** Small local LLMs can misinterpret context. Citations let users verify.
- **Make money.** This is a community project, not a commercial venture. No paywalls, no premium tiers, no monetization.

## Knowledge Base Content

All content must be **public domain** (US government works) or **openly licensed** (CC BY, CC BY-SA, CC0). No copyrighted material. Every document must have clear provenance, license status, distribution statement verification, and a download URL.

### Tier 1 — Core (MVP)

The minimum viable knowledge base covering the most critical survival and medical scenarios. This list is a starting point and should be refined during planning — additional high-value public domain sources may exist.

**Survival & Field Skills**
- FM 21-76: US Army Survival Manual
- FM 3-05.70: Survival (shelter, water, food, navigation, health, firecraft, plants, climate-specific, tools)
- FM 21-76-1: Survival, Evasion, and Recovery (pocket guide)
- FEMA "Are You Ready?" Citizen Preparedness Guide

**Field Medicine**
- ST 31-91B: Special Forces Medical Handbook (400+ pages)
- FM 21-10: Field Hygiene and Sanitation
- FM 4-25.11: First Aid
- CDC disaster first aid, wound care, water treatment, and food safety guidelines

**Water, Food, Shelter**
- FM 21-10 sections on water purification
- FEMA emergency water and food storage guides
- USDA food safety guidelines (public domain)

### Tier 2 — Expanded

- FM 31-70: Basic Cold Weather Manual
- USMC Summer and Winter Survival Course Handbooks
- Navy Preventive Medicine Manual (NAVMED P-5010)
- CDC disease prevention and treatment guidelines
- WHO open-access emergency health publications
- MedlinePlus first aid reference (NLM, public domain)
- Wikipedia medical and survival articles (CC BY-SA, curated subset)
- Hesperian Health Guides (where CC-licensed)
- FEMA nuclear preparedness materials

### Tier 3 — Community Contributed

A framework for community contributions with structured quality review: community-submitted documents, regional and climate-specific survival content, specialized topics (maritime, desert, arctic, tropical, urban), and non-English translations of core content.

The goal is to make it easy for people to contribute knowledge that helps their specific region or situation. A contributor guide and review process should lower the barrier to participation while maintaining quality.

### Data Source Repositories

Known repositories of public domain survival and medical content (non-exhaustive):

- liberatedmanuals.com — 4,800+ free US government manuals
- Internet Archive homesteading-survival-manuals collection
- collapsesurvivalsite.com — 400+ public domain survival books
- trueprepper.com, seasonedcitizenprepper.com — 667+ survival PDFs
- FEMA.gov publications library
- CDC.gov disaster preparedness resources
- NLM MedlinePlus first aid reference

## Licensing & Legal Requirements

- All source content must be public domain (US government works) or openly licensed (CC BY, CC BY-SA, CC0)
- No copyrighted material may be included under any circumstances
- Every document requires individual licensing verification — distribution statements must be checked per-document
- If a document's distribution status is ambiguous, it must be excluded (conservative default)
- Every included document must have a provenance manifest recording: source URL, license type, distribution statement, verification date, and processing notes
- All components of the project must be open-source with permissive licenses suitable for redistribution
- The project itself should use a permissive license (MIT or Apache 2.0) so anyone can use, modify, and build on it freely

## Contributing

SurvivalRAG is a community effort. Contributions are welcome in many forms:

- **Content curation** — Finding, verifying, and submitting public domain survival and medical documents
- **Data quality** — Improving OCR output, cleaning up formatting, fixing chunking issues
- **Code** — Building and improving the retrieval pipeline, interfaces, and deployment tooling
- **Testing** — Running queries, evaluating answer quality, reporting issues
- **Documentation** — Making it easier for others to deploy, use, and contribute
- **Translation** — Helping make the knowledge base accessible in more languages

A detailed contributing guide will be part of the repository.

## Future Vision: Meshtastic Mesh Radio Integration

The longer-term goal is to make SurvivalRAG queryable over Meshtastic mesh radio — enabling anyone on a mesh network to send a survival or medical question from a handheld radio and receive a grounded, cited answer from a node running SurvivalRAG.

This matters because the people who need survival knowledge most urgently are often the ones with the least connectivity. A mesh-accessible knowledge base could be genuinely life-saving in disaster scenarios, remote communities, or grid-down situations.

Key challenges this introduces:

- LoRa radio messages are limited to ~230 bytes per packet — responses must be extremely compressed or split across multiple transmissions
- Request/response protocol over mesh requires message IDs, timeouts, splitting, and reassembly
- Access control decisions: open access vs. authorized nodes only
- Rate limiting when multiple mesh nodes query simultaneously
- The system must produce useful, actionable answers in under 200 characters for mesh mode

This is a separate effort from the core knowledge base and should be planned independently.

## Open Questions

These are unresolved decisions that should be investigated during implementation planning:

| # | Question | Impact |
|---|---|---|
| 1 | How do we maximize retrieval accuracy for survival/medical queries? Some early decisions here may be difficult to change after the knowledge base ships. | High |
| 2 | Should different types of content (procedures vs. reference tables vs. safety warnings) be processed differently for optimal retrieval? | Medium |
| 3 | How do we balance retrieval recall (finding everything relevant) vs. system simplicity for v1? | Medium |
| 4 | How should knowledge base versioning and updates be handled? | Medium |
| 5 | Are all Tier 1 documents truly unrestricted for distribution? | Blocker |
| 6 | Is "SurvivalRAG" distinctive enough as a project name? | Low |
| 7 | How should long responses be delivered over Meshtastic given its severe message size limits? | Medium |
| 8 | What are the minimum hardware and model requirements to produce safe, reliable medical answers? | High |
| 9 | How do we make deployment simple enough that non-technical people can set this up? | High |

## Risks

| Risk | Severity |
|---|---|
| Small LLMs hallucinate medical procedures despite RAG grounding | High |
| Source documents have restricted distribution despite appearing uncopyrighted | High |
| OCR quality of scanned military PDFs produces unusable text | Medium |
| Embedding model produces poor retrieval for domain-specific medical terminology | Medium |
| Meshtastic latency makes query/response impractical | Medium |
| Scope creep delays the core knowledge base | Medium |
| Lack of contributors stalls community tiers | Medium |

## Related Open Source Projects

These projects may be useful as references or integration points:

- **knowledge-rag** — local RAG knowledge base project
- **Skill Seekers** — document-to-knowledge conversion tool
- **MESH-API** — Meshtastic-to-LLM bridge
- **MedRAG** — NLM medical RAG project (architecture reference)
