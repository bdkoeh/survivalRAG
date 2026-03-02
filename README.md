# SurvivalRAG

A pre-built survival and medical knowledge base for local LLMs.

---

Every person building an offline survival AI repeats the same work: finding public domain documents, verifying licenses, cleaning scanned PDFs, chunking, embedding, evaluating. Meanwhile, products like SurvivalNet and Doom Box just drop PDFs next to a generic LLM with no retrieval pipeline — the model has no awareness of the documents and falls back on training data, which for medical content can be dangerously wrong.

SurvivalRAG is the missing data layer. Curated public domain survival and medical content, already processed and structured for RAG retrieval, so you can plug it into your local LLM and get source-cited answers instead of hallucinated ones.

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

## Future Goal: Meshtastic Mesh Radio

The longer-term goal is to make SurvivalRAG queryable over Meshtastic mesh radio — send a survival or medical question from a handheld radio and get a grounded, cited answer back from a node on the mesh network.

The people who need survival knowledge most urgently are often the ones with the least connectivity.

This is a separate effort from the core knowledge base and won't be tackled until the base system is solid.

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
