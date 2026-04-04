"""WikiMed extraction pipeline: fetch Wikipedia medical articles, chunk, embed, write JSONL.

Fetches curated Wikipedia articles via the MediaWiki API, splits into sections,
chunks using the existing content-type-aware chunker, embeds via Ollama
nomic-embed-text, and writes JSONL files compatible with the ChromaDB ingestion
pipeline.

Wikipedia content is CC BY-SA 4.0. Each chunk carries full attribution metadata
including article title, revision ID, and license information.

Usage:
    # Fetch, chunk, embed all articles (requires Ollama with nomic-embed-text)
    python -m pipeline.wikimed

    # Fetch only (no embedding, useful for testing)
    python -m pipeline.wikimed --fetch-only

    # Process a single article
    python -m pipeline.wikimed --article "Hypothermia"

    # Resume from where you left off (skips already-processed articles)
    python -m pipeline.wikimed --resume
"""

import json
import logging
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

from pipeline.models import ChunkMetadata, ChunkRecord

logger = logging.getLogger(__name__)

# Paths
ARTICLE_LIST_PATH = Path("data/wikimed/article_list.json")
SECTIONS_DIR = Path("processed/wikimed_sections")
OUTPUT_DIR = Path("processed/chunks")
MANIFEST_DIR = Path("sources/manifests")

# Wikipedia API
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "SurvivalRAG/0.3.0 (survival knowledge base; bdkoeh@gmail.com)"

# Rate limiting
REQUEST_DELAY = 0.5  # seconds between API requests

# Chunk sizing (matches existing pipeline)
MAX_CHUNK_CHARS = 2048  # 512 tokens * 4 chars/token

# Minimum section length to keep (skip stubs and empty sections)
MIN_SECTION_CHARS = 80

# Wikipedia sections to skip (not useful for survival knowledge)
SKIP_SECTIONS = {
    "see also", "references", "external links", "further reading",
    "notes", "bibliography", "citations", "sources", "footnotes",
}


def load_article_list() -> list[dict]:
    """Load the curated article list from JSON."""
    with open(ARTICLE_LIST_PATH) as f:
        data = json.load(f)
    return data["articles"]


def fetch_article_wikitext(title: str) -> Optional[dict]:
    """Fetch article wikitext and metadata from Wikipedia API.

    Returns dict with keys: title, pageid, revid, wikitext.
    Returns None if article not found.
    """
    params = {
        "action": "parse",
        "page": title,
        "prop": "wikitext|revid",
        "format": "json",
        "formatversion": "2",
        "redirects": "1",  # auto-resolve redirects
    }
    url = f"{WIKIPEDIA_API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.error("Failed to fetch '%s': %s", title, e)
        return None

    if "error" in data:
        logger.warning("Wikipedia API error for '%s': %s", title, data["error"].get("info", ""))
        return None

    parse = data.get("parse", {})
    resolved_title = parse.get("title", title)
    if resolved_title != title:
        logger.info("Redirect: '%s' -> '%s'", title, resolved_title)

    wikitext = parse.get("wikitext", "")

    # Detect redirect pages that weren't resolved (backup check)
    if wikitext.strip().upper().startswith("#REDIRECT"):
        logger.warning("Unresolved redirect for '%s': %s", title, wikitext[:100])
        return None

    return {
        "title": resolved_title,
        "pageid": parse.get("pageid", 0),
        "revid": parse.get("revid", 0),
        "wikitext": wikitext,
    }


def strip_wikitext(text: str) -> str:
    """Convert wikitext to clean plain text suitable for RAG chunking.

    Strips wiki markup while preserving structure (lists, paragraphs).
    Prioritizes information density over formatting.
    """
    # Remove <ref>...</ref> and <ref .../> (citations)
    text = re.sub(r"<ref[^>]*/>", "", text)
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.DOTALL)

    # Remove HTML comments
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)

    # Remove large multi-line templates (infoboxes, sidebars, navboxes)
    # These use nested {{ }} so we strip from outermost match
    for _ in range(5):
        before = text
        text = re.sub(
            r"\{\{(?:Infobox|Speciesbox|Taxobox|Sidebar|Navbox|Short description|"
            r"Good article|Featured article|pp-|Use [dm]my dates|"
            r"Medical resources|Diagnostic method|Medref|Authority control|"
            r"Portal|Commons category)[^{}]*(?:\{\{[^{}]*\}\}[^{}]*)*\}\}",
            "", text, flags=re.IGNORECASE | re.DOTALL,
        )
        if text == before:
            break

    # Remove templates like {{cite...}}, {{sfn...}}, {{efn...}}
    # Handle nested templates by iterating
    for _ in range(5):  # max nesting depth
        before = text
        text = re.sub(r"\{\{(?:cite|sfn|efn|refn|harvnb|cn|citation needed|clarify|when|who|fact)[^{}]*\}\}", "", text, flags=re.IGNORECASE)
        if text == before:
            break

    # Convert common templates
    text = re.sub(r"\{\{convert\|([^|]+)\|([^|{}]+)(?:\|[^{}]*)?\}\}", r"\1 \2", text, flags=re.IGNORECASE)
    text = re.sub(r"\{\{circa\|(\d+)\}\}", r"c. \1", text, flags=re.IGNORECASE)
    text = re.sub(r"\{\{lang\|[^|]+\|([^}]+)\}\}", r"\1", text, flags=re.IGNORECASE)
    text = re.sub(r"\{\{ICD-?10\|[^}]+\}\}", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\{\{ICD-?9\|[^}]+\}\}", "", text, flags=re.IGNORECASE)

    # Remove remaining templates (but keep content of simple ones)
    # First pass: simple single-arg templates
    text = re.sub(r"\{\{[^|{}]*\|([^{}]*)\}\}", r"\1", text)
    # Second pass: remove empty/no-content templates
    for _ in range(3):
        before = text
        text = re.sub(r"\{\{[^{}]*\}\}", "", text)
        if text == before:
            break

    # Convert wiki links: [[Link|text]] -> text, [[Link]] -> Link
    text = re.sub(r"\[\[[^|\]]*\|([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)

    # Remove external links: [http://... text] -> text
    text = re.sub(r"\[https?://[^\s\]]+\s+([^\]]+)\]", r"\1", text)
    text = re.sub(r"\[https?://[^\]]+\]", "", text)

    # Convert formatting
    text = re.sub(r"'{3,}", "", text)  # bold
    text = re.sub(r"'{2}", "", text)   # italic

    # Remove gallery tags
    text = re.sub(r"<gallery[^>]*>.*?</gallery>", "", text, flags=re.DOTALL)

    # Remove remaining HTML tags but keep content
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</?(?:small|big|sub|sup|span|div|center|blockquote)[^>]*>", "", text, flags=re.IGNORECASE)

    # Convert HTML lists to plain text
    text = re.sub(r"<li[^>]*>", "- ", text, flags=re.IGNORECASE)
    text = re.sub(r"</li>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</?[uo]l[^>]*>", "\n", text, flags=re.IGNORECASE)

    # Remove tables (complex wiki tables don't convert well to plain text)
    text = re.sub(r"\{\|.*?\|\}", "", text, flags=re.DOTALL)

    # Convert bullet lists: * item -> - item
    text = re.sub(r"^\*+\s*", "- ", text, flags=re.MULTILINE)

    # Convert numbered lists: # item -> 1. item (rough)
    text = re.sub(r"^#+\s*", "- ", text, flags=re.MULTILINE)

    # Convert definition lists: ; term : definition
    text = re.sub(r"^;\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^:\s*", "  ", text, flags=re.MULTILINE)

    # Remove category links
    text = re.sub(r"\[\[Category:[^\]]+\]\]", "", text, flags=re.IGNORECASE)

    # Remove file/image links
    text = re.sub(r"\[\[(?:File|Image):[^\]]+\]\]", "", text, flags=re.IGNORECASE)

    # Remove leftover template parameter lines (e.g., "| key = value")
    # Only match lines starting with | to avoid stripping real content
    text = re.sub(r"^\|\s*\w+\s*=\s*[^\n]*$", "", text, flags=re.MULTILINE)

    # Remove stray template parameter fragments (e.g., "name-list-style=vanc")
    text = re.sub(r"^[a-z][\w-]+=\w+\s*$", "", text, flags=re.MULTILINE)

    # Clean up whitespace
    text = re.sub(r"[ \t]+", " ", text)  # collapse horizontal whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)  # max 2 newlines
    text = re.sub(r"^\s+$", "", text, flags=re.MULTILINE)  # empty lines

    return text.strip()


def split_sections(wikitext: str) -> list[tuple[str, str]]:
    """Split wikitext into (heading, content) sections.

    Splits at == Level 2 == and === Level 3 === headings.
    Returns list of (heading_text, section_content) tuples.
    The first tuple has heading="" for the article lead section.
    """
    # Split at section headings (== or ===)
    parts = re.split(r"^(={2,3})\s*(.+?)\s*\1\s*$", wikitext, flags=re.MULTILINE)

    sections = []

    # First part is the lead section (before any heading)
    lead = parts[0].strip()
    if lead:
        sections.append(("Overview", lead))

    # Remaining parts come in groups of 3: (level_markers, heading_text, content)
    i = 1
    while i + 2 <= len(parts):
        heading = parts[i + 1].strip()
        content = parts[i + 2].strip() if i + 2 < len(parts) else ""
        i += 3

        # Skip non-useful sections
        if heading.lower() in SKIP_SECTIONS:
            continue

        if content:
            sections.append((heading, content))

    return sections


def make_source_document_id(title: str) -> str:
    """Convert article title to a source_document identifier.

    Example: "Cardiopulmonary resuscitation" -> "WikiMed-Cardiopulmonary_resuscitation"
    """
    safe = title.replace(" ", "_").replace("/", "-")
    return f"WikiMed-{safe}"


def make_chunk_id(source_document: str, page_number: int, chunk_index: int) -> str:
    """Generate a chunk ID matching existing format: {source}_{page:03d}_{chunk:03d}."""
    return f"{source_document}_{page_number:03d}_{chunk_index:03d}"


def sections_to_chunks(
    article_info: dict,
    sections: list[tuple[str, str]],
    categories: list[str],
) -> list[ChunkRecord]:
    """Convert article sections into ChunkRecords.

    Each section becomes one or more chunks based on size. Chunks inherit
    the article's categories and carry full Wikipedia attribution metadata.
    """
    source_document = make_source_document_id(article_info["title"])
    source_url = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(article_info['title'].replace(' ', '_'))}"
    revision_url = f"https://en.wikipedia.org/w/index.php?oldid={article_info['revid']}"

    all_chunks = []
    # Use section index as "page number" for chunk ID ordering
    for section_idx, (heading, raw_content) in enumerate(sections):
        content = strip_wikitext(raw_content)

        if len(content) < MIN_SECTION_CHARS:
            continue

        # Split into chunks if content exceeds limit
        chunk_texts = _split_text(content, MAX_CHUNK_CHARS)

        for chunk_idx, text in enumerate(chunk_texts):
            text = text.strip()
            if not text or len(text) < 40:
                continue

            metadata = ChunkMetadata(
                source_document=source_document,
                source_title=f"Wikipedia: {article_info['title']}",
                section_header=heading,
                page_number=section_idx,
                content_type="general",
                categories=categories,
                source_url=revision_url,
                license="CC BY-SA 4.0",
                distribution_statement=(
                    f"Wikipedia article '{article_info['title']}', "
                    f"revision {article_info['revid']}. "
                    f"Licensed under CC BY-SA 4.0. "
                    f"Contributors: {source_url}"
                ),
                verification_date="2026-04-03",
                chunk_index=chunk_idx,
                chunk_total=len(chunk_texts),
                embedding_model="",
                embedding_model_version="",
                warning_level=None,
                warning_text=None,
            )
            all_chunks.append(ChunkRecord(text=text, metadata=metadata))

    return all_chunks


def _split_text(text: str, max_chars: int) -> list[str]:
    """Split text into chunks at paragraph boundaries, then sentences."""
    if len(text) <= max_chars:
        return [text]

    # Try paragraph splits first
    paragraphs = re.split(r"\n\n+", text)
    chunks = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if not current:
            current = para
        elif len(current) + 2 + len(para) <= max_chars:
            current += "\n\n" + para
        else:
            chunks.append(current)
            current = para

    if current:
        chunks.append(current)

    # Check if any chunk is still too long (split at sentences)
    final = []
    for chunk in chunks:
        if len(chunk) <= max_chars:
            final.append(chunk)
        else:
            final.extend(_split_at_sentences(chunk, max_chars))

    return final


def _split_at_sentences(text: str, max_chars: int) -> list[str]:
    """Split text at sentence boundaries."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks = []
    current = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        if not current:
            current = sentence
        elif len(current) + 1 + len(sentence) <= max_chars:
            current += " " + sentence
        else:
            chunks.append(current)
            current = sentence

    if current:
        chunks.append(current)

    return chunks


def write_jsonl(chunks: list[ChunkRecord], output_path: Path) -> None:
    """Write ChunkRecords to JSONL file matching existing format."""
    with open(output_path, "w") as f:
        for chunk in chunks:
            record = {
                "text": chunk.text,
                "embedding": chunk.embedding,
                "metadata": chunk.metadata.model_dump(),
            }
            f.write(json.dumps(record) + "\n")


def write_manifest(article_info: dict, categories: list[str], chunk_count: int) -> None:
    """Write a YAML provenance manifest for a Wikipedia article."""
    source_document = make_source_document_id(article_info["title"])
    title = article_info["title"]
    safe_title = title.replace(" ", "_")

    manifest = f"""# Provenance Manifest for Wikipedia: {title}
# Schema version: 1.0

document:
  title: "Wikipedia: {title}"
  designation: "{source_document}"
  edition_date: "2026-04-03"
  pages: 0
  file_name: "{source_document}.jsonl"

source:
  primary_url: "https://en.wikipedia.org/wiki/{safe_title}"
  revision_url: "https://en.wikipedia.org/w/index.php?oldid={article_info['revid']}"
  revision_id: {article_info['revid']}
  publisher: "Wikipedia contributors"
  country: "International"

licensing:
  license_type: "CC BY-SA 4.0"
  license_url: "https://creativecommons.org/licenses/by-sa/4.0/"
  attribution: "Wikipedia contributors, '{title}', Wikipedia, The Free Encyclopedia"
  copyright_status: "Copyrighted, licensed under CC BY-SA 4.0"
  verification_date: "2026-04-03"
  verification_method: "Wikipedia content is licensed under CC BY-SA 4.0 per Wikimedia Foundation Terms of Use"
  verified_by: "automated"

content:
  categories:
{chr(10).join(f'    - {c}' for c in categories)}
  tier: 2
  content_type: "encyclopedia_article"
  language: "en"
  chunk_count: {chunk_count}

processing:
  notes: "Extracted via MediaWiki API, wikitext converted to plain text, chunked and embedded by SurvivalRAG pipeline"
  ocr_needed: false
  download_date: "2026-04-03"
  download_method: "MediaWiki API (action=parse)"
"""
    manifest_path = MANIFEST_DIR / f"{source_document}.yaml"
    manifest_path.write_text(manifest)
    logger.info("Wrote manifest: %s", manifest_path)


def process_article(
    title: str,
    categories: list[str],
    embed: bool = True,
    skip_existing: bool = False,
) -> Optional[int]:
    """Process a single Wikipedia article through the full pipeline.

    Returns number of chunks produced, or None on failure.
    """
    source_document = make_source_document_id(title)
    output_path = OUTPUT_DIR / f"{source_document}.jsonl"

    if skip_existing and output_path.exists():
        logger.info("Skipping '%s' (already exists)", title)
        return None

    # Fetch
    logger.info("Fetching '%s'...", title)
    article = fetch_article_wikitext(title)
    if not article or not article["wikitext"]:
        logger.warning("No content for '%s'", title)
        return None

    # Section
    sections = split_sections(article["wikitext"])
    if not sections:
        logger.warning("No sections extracted from '%s'", title)
        return None

    # Chunk
    chunks = sections_to_chunks(article, sections, categories)
    if not chunks:
        logger.warning("No chunks produced from '%s'", title)
        return None

    # Embed
    if embed:
        from pipeline.embed import embed_chunk_records
        chunks = embed_chunk_records(chunks)

        # Filter out chunks with empty embeddings (oversized or failed)
        chunks = [c for c in chunks if c.embedding]

    # Write JSONL
    write_jsonl(chunks, output_path)
    logger.info("Wrote %d chunks to %s", len(chunks), output_path)

    # Write manifest
    write_manifest(article, categories, len(chunks))

    return len(chunks)


def main():
    """Run the WikiMed extraction pipeline."""
    import argparse

    parser = argparse.ArgumentParser(description="WikiMed extraction pipeline")
    parser.add_argument("--article", help="Process a single article by title")
    parser.add_argument("--fetch-only", action="store_true", help="Fetch and chunk without embedding")
    parser.add_argument("--resume", action="store_true", help="Skip already-processed articles")
    parser.add_argument("--limit", type=int, help="Maximum number of articles to process")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    do_embed = not args.fetch_only

    # Verify Ollama is available for embedding
    if do_embed:
        try:
            from pipeline.embed import get_model_version
            version = get_model_version()
            logger.info("Embedding model ready: nomic-embed-text (%s)", version)
        except Exception as e:
            logger.error("Ollama/nomic-embed-text not available: %s", e)
            logger.error("Run with --fetch-only to skip embedding, or start Ollama")
            sys.exit(1)

    # Ensure output dirs exist
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)

    if args.article:
        # Single article mode
        articles = load_article_list()
        match = next((a for a in articles if a["title"].lower() == args.article.lower()), None)
        if match:
            categories = match["categories"]
        else:
            logger.warning("Article '%s' not in curated list, using ['medical'] as default", args.article)
            categories = ["medical"]

        count = process_article(args.article, categories, embed=do_embed)
        if count:
            print(f"Processed '{args.article}': {count} chunks")
        else:
            print(f"Failed to process '{args.article}'")
        return

    # Full pipeline: process all articles
    articles = load_article_list()
    if args.limit:
        articles = articles[:args.limit]

    total_articles = len(articles)
    total_chunks = 0
    processed = 0
    skipped = 0
    failed = 0

    print(f"Processing {total_articles} Wikipedia articles...")
    print(f"  Embedding: {'yes' if do_embed else 'no (fetch-only)'}")
    print(f"  Resume: {'yes' if args.resume else 'no'}")
    print()

    for i, article in enumerate(articles):
        title = article["title"]
        categories = article["categories"]

        print(f"[{i+1}/{total_articles}] {title}...", end=" ", flush=True)

        count = process_article(
            title, categories,
            embed=do_embed,
            skip_existing=args.resume,
        )

        if count is None and args.resume:
            print("skipped (exists)")
            skipped += 1
        elif count is None:
            print("FAILED")
            failed += 1
        else:
            print(f"{count} chunks")
            total_chunks += count
            processed += 1

        # Rate limit
        if i < total_articles - 1:
            time.sleep(REQUEST_DELAY)

    print()
    print(f"Done! Processed: {processed}, Skipped: {skipped}, Failed: {failed}")
    print(f"Total chunks: {total_chunks}")

    if do_embed:
        print(f"\nJSONL files written to {OUTPUT_DIR}/WikiMed-*.jsonl")
        print("Run the app to rebuild ChromaDB with new content.")


if __name__ == "__main__":
    main()
