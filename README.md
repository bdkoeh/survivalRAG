# SurvivalRAG

**A pre-built survival & medical knowledge base for local LLMs.**

An open-source, ready-to-deploy RAG knowledge base of curated public domain survival, medical, and emergency preparedness content. No data collection, document processing, or embedding work required — just download and run.

---

## The Problem

There is no high-quality, pre-built, openly licensed knowledge base optimized for survival and field medicine. Every person building an offline survival AI repeats the same work from scratch: finding documents, verifying licenses, cleaning PDFs, choosing chunking strategies, selecting embedding models, and evaluating results.

Meanwhile, existing products like SurvivalNet ($100–$700), Doom Box ($699), and R.E.A.D.I. Console all share the same flaw — they put PDFs next to a generic LLM with no retrieval pipeline. The LLM has no awareness of the documents and falls back on training data, which for medical and survival content can be dangerously wrong.

RAG toolkits like LangChain and LlamaIndex provide great retrieval infrastructure but ship zero data. SurvivalRAG is the missing data layer.

## Features

- **Ready out of the box** — Curated public domain documents already cleaned, structured, and embedded for retrieval
- **Source-cited answers** — Every response cites which document the information comes from so you can verify it
- **Safety-first** — When context is insufficient, the system says so instead of guessing. Safety warnings from source material are preserved and surfaced
- **Field-manual-style output** — Concise, actionable steps rather than conversational prose
- **Category filtering** — Scope queries to specific topics (medical only, water only, etc.)
- **Multiple response modes** — Full responses for local use, compact for mobile, ultra-short (~200 chars) for mesh radio
- **LLM-agnostic** — Works with your choice of local model
- **Fully offline** — No internet needed after initial setup

## Quick Start

> **Coming soon.** The project is in active development. Star/watch the repo to follow along.

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/SurvivalRAG.git
cd SurvivalRAG

# Install dependencies
pip install -r requirements.txt

# Run the knowledge base
python main.py
```

## Knowledge Base Content

All content is **public domain** (US government works) or **openly licensed** (CC BY, CC BY-SA, CC0). No copyrighted material. Every document has verified provenance.

### Core Sources

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

### Expanded Sources

Cold weather manuals, USMC survival handbooks, Navy preventive medicine, CDC/WHO disease guidelines, MedlinePlus references, Hesperian Health Guides (CC-licensed), FEMA nuclear preparedness, and curated Wikipedia medical articles.

### Community Contributions

We maintain a framework for community-submitted content including regional survival knowledge, climate-specific guides, specialized topics (maritime, desert, arctic, tropical, urban), and translations.

## What This Is NOT

- **Not a diagnostic tool.** This is a reference system, not a medical system.
- **Not a replacement for training.** A RAG can recite the steps; it cannot teach the skill.
- **Not guaranteed accurate.** Small local LLMs can misinterpret context. That's why every answer includes citations so you can verify.

## Future: Meshtastic Mesh Radio

The longer-term goal is to make SurvivalRAG queryable over Meshtastic mesh radio — send a survival or medical question from a handheld radio and get a grounded, cited answer from a node on the mesh network.

The people who need survival knowledge most urgently are often the ones with the least connectivity. A mesh-accessible knowledge base could be life-saving in disaster scenarios, remote communities, or grid-down situations.

## Contributing

This is a community project and contributions are welcome:

- **Content** — Finding and verifying public domain survival/medical documents
- **Data quality** — Improving OCR, formatting, and chunking
- **Code** — Retrieval pipeline, interfaces, deployment tooling
- **Testing** — Running queries, evaluating answer quality, reporting issues
- **Documentation** — Making it easier for others to deploy and contribute
- **Translation** — Making the knowledge base accessible in more languages

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE).

All source content in the knowledge base is public domain or openly licensed (CC BY, CC BY-SA, CC0).
