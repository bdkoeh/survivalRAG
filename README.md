# SurvivalRAG

An offline survival and medical knowledge base for local LLMs — designed to be queryable over Meshtastic mesh radio when the grid is down.

---

When Hurricane Helene hit in September 2024, it knocked out 4,562 cell sites across five states — the worst outage ever recorded. Communities in western North Carolina were isolated for weeks with no cell service, no internet, no way to call for help. After Hurricane Maria in 2017, Puerto Rico averaged 41 days without cell service. A third of the estimated 2,975 excess deaths were attributed to disrupted medical care. Twenty-six people died from drinking contaminated stream water — a preventable outcome if they'd had access to basic water safety information.

This pattern repeats in every major disaster. Infrastructure fails, information channels go dark, and people are left making life-or-death decisions — wound treatment, water purification, shelter, navigation — with no way to look anything up. The 72-hour self-sufficiency window that FEMA recommends turns out to be wildly optimistic.

[Meshtastic](https://meshtastic.org) is changing the communication side of this problem. It's an open-source mesh networking protocol that runs on cheap LoRa radios ($20–$50), requires no license, no cell towers, no internet — just devices talking to each other. It was deployed during Helene, the 2025 LA wildfires, and the Berlin blackout. Communities are building permanent mesh networks so they're not caught off guard again.

But Meshtastic only moves messages. It doesn't know anything. If you send a question over the mesh today, there's nothing on the other end to answer it.

**SurvivalRAG is building that other end.** A curated, public domain knowledge base of survival and medical content — sourced from US military field manuals, FEMA guides, CDC guidelines, and other government publications — processed and structured for RAG retrieval against a local LLM. The goal is a plug-and-play system: connect it to your local model, connect it to your mesh node, and anyone on the network can send a survival or medical question and get a grounded, source-cited answer back.

No internet required. No subscriptions. No cloud. Just a knowledge base, a local model, and a radio.

## Current Status

**This project is in active development. It is not usable yet.**

Here's what exists today and what doesn't:

| Component | Status |
|---|---|
| Source documents (70 PDFs, all public domain, individually license-verified) | Done |
| Provenance manifests (source URL, license, distribution statement per document) | Done |
| Document processing (extraction, cleaning, section splitting — 7,915 sections) | Done |
| Chunking & embedding code (content-type-aware, benchmarked at 88% Recall@5) | Code done, full corpus run pending |
| Retrieval pipeline (hybrid vector + BM25 search, category filtering) | Code done, needs embeddings to run |
| Response generation | Not started |
| CLI or web interface | Not started |
| Deployment packaging | Not started |

The pipeline code works. The blocking step is running the full corpus through embedding (requires Ollama with `nomic-embed-text`), which populates the vector store and makes everything queryable.

If you want to follow along or help out, star/watch the repo.

## What's In the Knowledge Base

All content is **public domain** (US government works) or **openly licensed** (CC BY, CC BY-SA, CC0). No copyrighted material. Every document has a YAML provenance manifest with source URL, license type, distribution statement, and verification date.

**Survival & Field Skills**
- FM 21-76 — US Army Survival Manual
- FM 3-05.70 — Survival (shelter, water, food, navigation, firecraft, tools)
- FM 21-76-1 — Survival, Evasion, and Recovery (pocket guide)
- FEMA "Are You Ready?" Citizen Preparedness Guide

**Field Medicine**
- ST 31-91B — Special Forces Medical Handbook (400+ pages)
- FM 21-10 — Field Hygiene and Sanitation
- FM 4-25.11 — First Aid
- CDC disaster first aid, wound care, water treatment, and food safety guidelines

**Water, Food, Shelter**
- FM 21-10 sections on water purification
- FEMA emergency water and food storage guides
- USDA food safety guidelines

Plus 50+ additional documents covering cold weather operations, preventive medicine, nuclear preparedness, disease guidelines, and more. See `sources/manifests/` for the full list with provenance details.

## How It Works

```
Source PDFs → Extract & Clean → Split into Sections → Chunk by Content Type → Embed → Vector Store
                                                                                         ↓
                                                              User Query → Hybrid Search (Vector + BM25) → Prompt Assembly → LLM → Cited Answer
```

1. **Document processing** — PDFs are extracted, cleaned, and split into logical sections with metadata preserved
2. **Content-aware chunking** — Different strategies for procedures, reference tables, safety warnings, and general content (512-token chunks, never splits mid-step)
3. **Hybrid retrieval** — Vector similarity (ChromaDB) fused with BM25 keyword search (Reciprocal Rank Fusion), with optional category filtering
4. **Safety-first prompting** — Safety warnings are surfaced before other context. When retrieved context is insufficient, the system says so instead of guessing
5. **Source citation** — Every answer cites which document the information came from

The system is LLM-agnostic (works with whatever local model you run via Ollama) and fully offline after initial setup.

## What This Is Not

- **Not a diagnostic tool.** This is a reference system, not a medical system.
- **Not a replacement for training.** It can recite the steps but it cannot teach the skill.
- **Not guaranteed accurate.** Small local LLMs can misinterpret context. That's why every answer includes citations — so you can verify against the source.

## Meshtastic Integration

The mesh radio layer is a separate effort from the core knowledge base — it won't be tackled until the base system is solid. The main constraints are LoRa's 228-character message limit and ~1 kbps throughput, which means responses need to be compressed into a single message or split across a few. Projects like [MESH-API](https://github.com/mr-tbot/mesh-api) and [Radio-LLM](https://github.com/pham-tuan-binh/radio-llm) have already proven that bridging Meshtastic to a local LLM works — the missing piece is a knowledge base worth querying.

## Contributing

This is a community project and there's plenty of ways to help, even if you don't write code:

- **Content** — Finding and verifying public domain survival/medical documents
- **Data quality** — Improving OCR output, cleaning up formatting, fixing chunking issues
- **Code** — Retrieval pipeline, response generation, interfaces, deployment
- **Testing** — Running queries, evaluating answer quality, reporting issues
- **Documentation** — Making it easier for others to deploy and contribute
- **Translation** — Making the knowledge base accessible in more languages

If you're interested, open an issue or start a discussion. A formal contributing guide is coming.

## Project Structure

```
survivalRAG/
├── pipeline/           # Processing and retrieval pipeline (Python)
│   ├── extract.py      # PDF extraction
│   ├── clean.py        # Text cleaning
│   ├── split.py        # Section splitting
│   ├── chunk.py        # Content-aware chunking
│   ├── embed.py        # Ollama embedding wrapper
│   ├── ingest.py       # ChromaDB ingestion
│   ├── retrieve.py     # Hybrid search (vector + BM25)
│   └── prompt.py       # Prompt assembly with safety ordering
├── sources/
│   ├── manifests/      # YAML provenance manifest per document
│   ├── originals/      # Source PDFs (not in git)
│   └── excluded/       # Documents excluded with reasoning
├── processed/
│   ├── sections/       # 7,915 extracted sections (70 documents)
│   ├── chunks/         # Embedded chunks (not yet generated)
│   ├── benchmark/      # Retrieval benchmark results
│   └── reports/        # Per-document classification reports
└── requirements.txt
```

## Requirements

- Python 3.11+
- [Ollama](https://ollama.ai) with `nomic-embed-text` model (for embeddings) and a chat model of your choice
- ~2GB disk for the processed knowledge base

## License

Code: [GNU General Public License v3.0](LICENSE)

Content: All source material in the knowledge base is public domain or openly licensed (CC BY, CC BY-SA, CC0).
