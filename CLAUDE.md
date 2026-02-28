# SurvivalRAG - Claude Code Guidelines

## Project Overview

SurvivalRAG is an open-source, pre-built RAG (Retrieval-Augmented Generation) knowledge base containing curated **public domain** survival, medical, and emergency preparedness content. It ships as a ready-to-use package for local LLMs — no data collection, processing, or embedding work required by the end user.

Future goal: queryable over Meshtastic mesh radio for off-grid scenarios.

## Key Principles

- **Safety-first**: Medical/survival content must preserve safety warnings. When context is insufficient, say so — never guess.
- **Source-cited**: Every answer must cite which source document the information came from.
- **Public domain only**: All content must be US government works or openly licensed (CC BY, CC BY-SA, CC0). No copyrighted material under any circumstances.
- **Offline capable**: Must function with no internet after initial setup.
- **LLM-agnostic**: Works with the user's choice of local LLM (Ollama, llama.cpp, etc.).
- **Simple deployment**: Non-technical users should be able to set this up.

## Architecture

- **Data layer**: Curated, cleaned, chunked, and embedded public domain documents
- **Retrieval pipeline**: Vector similarity search with category filtering
- **Response modes**: Full (local), compact (mobile/low-bandwidth), ultra-short (~200 chars for mesh radio)
- **Interfaces**: Web chat UI, CLI
- **Provenance tracking**: Every document has source URL, license type, distribution statement, verification date

## Content Tiers

1. **Tier 1 (MVP)**: US Army survival manuals (FM 21-76, FM 3-05.70, etc.), SF Medical Handbook, FEMA guides, CDC guidelines
2. **Tier 2 (Expanded)**: Cold weather manuals, Navy preventive medicine, WHO publications, MedlinePlus, curated Wikipedia medical articles
3. **Tier 3 (Community)**: Community-contributed regional/specialized content with quality review

## Licensing Requirements

- Verify distribution statement per-document (not per-repository)
- Ambiguous licensing = exclude (conservative default)
- Maintain a provenance manifest for every included document
- Project license: MIT or Apache 2.0

## Development Guidelines

- Keep answers field-manual-style: concise, actionable steps — not conversational prose
- Chunk strategies may need to differ by content type (procedures vs. reference tables vs. safety warnings)
- Preserve safety warnings from source material — never strip or summarize them away
- Test retrieval quality with domain-specific medical terminology
- OCR quality from scanned military PDFs may need manual cleanup

## Key Risks to Watch

- Small LLMs hallucinating medical procedures despite RAG grounding
- Poor OCR quality from scanned PDFs producing unusable text
- Embedding models performing poorly on medical terminology
- Scope creep delaying the core knowledge base

## Project Brief

See `SurvivalRAG_Brief.md` for the full project specification, content source list, open questions, and future Meshtastic integration plans.
