# SurvivalRAG

## What This Is

SurvivalRAG is an open-source, pre-built RAG knowledge base containing curated public domain survival, medical, and emergency preparedness content. It ships as a Docker container that anyone running a local LLM can deploy immediately — pull the image, open a browser, ask a question. No data collection, document processing, or embedding work required by the end user.

## Core Value

Every answer is grounded in cited public domain source documents — when context is insufficient, the system says so rather than guessing. Safety-critical information must never be hallucinated.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Pre-built knowledge base from curated Tier 1 public domain documents (US Army survival manuals, SF Medical Handbook, FEMA guides, CDC guidelines)
- [ ] Source-cited responses — every answer cites which document the information came from
- [ ] Safety-first responses — preserves safety warnings, refuses to guess when context is insufficient
- [ ] Field-manual-style answers — concise, actionable steps, not conversational prose
- [ ] Category-filtered retrieval — scope queries to specific topics (medical, water, shelter, etc.)
- [ ] Web-based chat interface as primary user experience
- [ ] Command-line interface for power users
- [ ] Docker container deployment with bundled Ollama and default small model — zero config
- [ ] LLM-agnostic — configurable to use external Ollama/llama.cpp instances
- [ ] Fully offline capable after initial docker pull
- [ ] Full response mode only for v1 (compact and ultra-short deferred)
- [ ] Document provenance manifest — source URL, license type, distribution statement, verification date for every document
- [ ] Retrieval quality validated with real survival/medical queries

### Out of Scope

- Meshtastic mesh radio integration — separate future milestone
- Compact and ultra-short response modes — deferred until mesh milestone
- User document ingestion pipeline — v2 feature, ship pre-built only for v1
- Medical diagnosis — this is a reference tool, not a diagnostic system
- Tier 2 and Tier 3 content — v1 is Tier 1 only
- Community contribution framework — v2, after core knowledge base is proven
- Non-English content — English only for v1
- Monetization — this is a community project

## Context

- No documents have been collected yet — document sourcing, licensing verification, and processing is part of the build work
- Tier 1 sources are primarily US military field manuals and US government publications (public domain by law)
- Scanned military PDFs may have poor OCR quality requiring manual cleanup
- Small local LLMs are known to hallucinate medical procedures even with RAG grounding — retrieval quality and citation enforcement are critical safety measures
- Embedding model selection matters significantly for domain-specific medical terminology retrieval accuracy
- Related projects (SurvivalNet, Doom Box, READI Console) all lack a proper retrieval pipeline — they place PDFs next to LLMs with no connection between them
- MedRAG from NLM provides architecture reference but no data
- The tech stack will be determined through domain research

## Constraints

- **Content licensing**: All content must be US government works (public domain) or CC BY/CC BY-SA/CC0. Ambiguous licensing = exclude.
- **Deployment**: Must run in Docker with zero external dependencies after pull. Bundled Ollama + default model.
- **Offline**: Must function with no internet after initial setup.
- **Safety**: Must preserve source material safety warnings. Must cite sources. Must refuse when context is insufficient.
- **Audience**: Non-technical users should be able to deploy this — `docker pull` and open browser.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Docker as primary distribution | Zero-config experience for non-technical users | — Pending |
| Bundle Ollama + default model | Eliminates "bring your own LLM" friction for first-time users | — Pending |
| Full response mode only for v1 | Mesh is out of scope, compact/ultra-short can wait | — Pending |
| Pre-built knowledge base only | User doc ingestion adds complexity, ship core value first | — Pending |
| Tier 1 content only for v1 | Focus on highest-value, most-verified sources first | — Pending |
| Tech stack via research | Let domain research recommend the best RAG stack rather than pre-committing | — Pending |

---
*Last updated: 2026-02-28 after initialization*
