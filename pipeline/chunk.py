"""Content-type-aware chunking module for the document processing pipeline.

Reads section Markdown files (with YAML front matter from Phase 2) and splits
them into ChunkRecords using type-specific strategies:

- Procedures: Split at numbered step boundaries (never mid-step)
- Reference tables: Keep as single chunks with headers preserved
- Safety warnings: Emit as own retrievable chunks
- General: Split at paragraph breaks, then sentence boundaries if needed

Safety warning metadata (warning_level, warning_text) from the section's YAML
front matter is propagated to ALL chunks from the same section.

No chunk merging. No overlap between consecutive chunks.
"""

import logging
import re
from pathlib import Path
from typing import Optional

import yaml

from pipeline.models import ChunkMetadata, ChunkRecord

logger = logging.getLogger(__name__)

# Chunk size limits (512 tokens at ~4 chars/token heuristic)
MAX_CHUNK_TOKENS = 512
MAX_CHUNK_CHARS = 2048  # 512 * 4


def estimate_tokens(text: str) -> int:
    """Estimate token count using character-based heuristic.

    BERT tokenizer averages ~4 characters per token for English prose.
    This is conservative (overestimates) which is safer for chunk sizing.

    Args:
        text: Input text to estimate tokens for.

    Returns:
        Estimated token count.
    """
    return len(text) // 4


def read_section_file(filepath: Path) -> tuple[dict, str]:
    """Read a section Markdown file, returning (metadata_dict, content_str).

    Splits at YAML front matter delimiters (---), parses the metadata with
    yaml.safe_load(), and returns the content after the front matter.

    Args:
        filepath: Path to the section Markdown file.

    Returns:
        Tuple of (metadata dict, content string). Returns ({}, full_text)
        if no front matter is found.
    """
    text = filepath.read_text(encoding="utf-8")

    # Split at YAML front matter delimiters
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            metadata = yaml.safe_load(parts[1])
            if metadata is None:
                metadata = {}
            content = parts[2].strip()
            return metadata, content

    # No front matter -- return empty metadata and full text
    return {}, text


def chunk_section(content: str, metadata: dict) -> list[ChunkRecord]:
    """Dispatch to content-type-specific chunker based on metadata.

    Reads content_type.primary from metadata dict. Defaults to "general"
    if empty string, missing, or None. After chunking, sets chunk_total
    on all records and propagates warning metadata.

    Args:
        content: The Markdown content text (without YAML front matter).
        metadata: The parsed YAML front matter as a dict.

    Returns:
        List of ChunkRecords with full metadata.
    """
    # Read content_type.primary, defaulting to "general"
    content_type = (
        metadata.get("content_type", {}).get("primary", "general") or "general"
    )

    # Dispatch to type-specific chunker
    if content_type == "procedure":
        chunks = _chunk_procedure(content, metadata)
    elif content_type == "reference_table":
        chunks = _chunk_table(content, metadata)
    elif content_type == "safety_warning":
        chunks = _chunk_safety_warning(content, metadata)
    else:
        chunks = _chunk_general(content, metadata)

    # Set chunk_total on all records
    total = len(chunks)
    for chunk in chunks:
        chunk.metadata.chunk_total = total

    # Propagate warning metadata to ALL chunks in this section
    warning_level = metadata.get("warning_level")
    warning_text = metadata.get("warning_text")
    if warning_level or warning_text:
        for chunk in chunks:
            chunk.metadata.warning_level = warning_level
            chunk.metadata.warning_text = warning_text

    return chunks


def _chunk_procedure(content: str, metadata: dict) -> list[ChunkRecord]:
    """Split procedure content at step boundaries.

    Detects numbered steps (1., 2., a., b., 1), a)) and splits at each
    step boundary. Steps exceeding MAX_CHUNK_CHARS are further split at
    sentence boundaries. If no numbered steps are detected, falls back
    to general chunking.

    Args:
        content: Procedure text content.
        metadata: Section metadata dict.

    Returns:
        List of ChunkRecords, one per step (or sentence group if step is large).
    """
    # Pattern matches: "1.", "2.", "a.", "b.", "1)", "a)", etc. at line start
    step_pattern = re.compile(r"^(\d+[\.\)]\s|[a-z][\.\)]\s)", re.MULTILINE)

    # Find all step boundaries
    matches = list(step_pattern.finditer(content))

    if not matches:
        # No numbered steps found -- fall back to general chunking
        return _chunk_general(content, metadata)

    chunk_texts = []

    # Extract preamble text before the first step
    if matches[0].start() > 0:
        preamble = content[: matches[0].start()].strip()
        if preamble:
            chunk_texts.append(preamble)

    # Split at each step boundary
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        step_text = content[start:end].strip()

        if not step_text:
            continue

        if len(step_text) <= MAX_CHUNK_CHARS:
            chunk_texts.append(step_text)
        else:
            # Step too long -- split at sentence boundaries
            chunk_texts.extend(_split_at_sentences(step_text, MAX_CHUNK_CHARS))

    # Build ChunkRecords
    records = []
    for i, text in enumerate(chunk_texts):
        text = text.strip()
        if text:
            records.append(_build_chunk_record(text, metadata, i))

    return records


def _chunk_table(content: str, metadata: dict) -> list[ChunkRecord]:
    """Emit entire table section as a single chunk.

    Tables are kept whole with headers preserved per locked decision (CHNK-02).
    Even if content exceeds MAX_CHUNK_CHARS, tables are never split -- a log
    warning is emitted instead.

    Args:
        content: Table text content.
        metadata: Section metadata dict.

    Returns:
        List containing a single ChunkRecord.
    """
    content = content.strip()
    if not content:
        return []

    if len(content) > MAX_CHUNK_CHARS:
        logger.warning(
            "Table chunk exceeds MAX_CHUNK_CHARS (%d chars) for section '%s' "
            "in %s -- emitting as single chunk anyway (tables are never split)",
            len(content),
            metadata.get("section_heading", "unknown"),
            metadata.get("source_document", "unknown"),
        )

    return [_build_chunk_record(content, metadata, 0)]


def _chunk_safety_warning(content: str, metadata: dict) -> list[ChunkRecord]:
    """Emit safety warning as its own retrievable chunk.

    Safety warning sections produce their own chunks so they surface in
    search results when users query directly for warnings. If content
    exceeds MAX_CHUNK_CHARS, split at sentence boundaries.

    Args:
        content: Safety warning text content.
        metadata: Section metadata dict.

    Returns:
        List of ChunkRecords (usually one, more if content is very long).
    """
    content = content.strip()
    if not content:
        return []

    if len(content) <= MAX_CHUNK_CHARS:
        return [_build_chunk_record(content, metadata, 0)]

    # Split at sentence boundaries if too long
    texts = _split_at_sentences(content, MAX_CHUNK_CHARS)
    records = []
    for i, text in enumerate(texts):
        text = text.strip()
        if text:
            records.append(_build_chunk_record(text, metadata, i))
    return records


def _chunk_general(content: str, metadata: dict) -> list[ChunkRecord]:
    """Chunk general content at paragraph breaks, then sentence boundaries.

    If content fits within MAX_CHUNK_CHARS, emit as single chunk.
    Otherwise, split at paragraph breaks (double newline) first.
    If any paragraph exceeds MAX_CHUNK_CHARS, split at sentence boundaries.
    No overlap between chunks.

    Args:
        content: General text content.
        metadata: Section metadata dict.

    Returns:
        List of ChunkRecords.
    """
    content = content.strip()
    if not content:
        return []

    if len(content) <= MAX_CHUNK_CHARS:
        return [_build_chunk_record(content, metadata, 0)]

    # Split at paragraph breaks (double newline)
    paragraphs = re.split(r"\n\n+", content)
    chunk_texts = []

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(para) <= MAX_CHUNK_CHARS:
            chunk_texts.append(para)
        else:
            # Paragraph too long -- split at sentence boundaries
            chunk_texts.extend(_split_at_sentences(para, MAX_CHUNK_CHARS))

    # Build ChunkRecords
    records = []
    for i, text in enumerate(chunk_texts):
        text = text.strip()
        if text:
            records.append(_build_chunk_record(text, metadata, i))

    return records


def _split_at_sentences(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """Split text at sentence boundaries to fit within max_chars.

    Splits on sentence-ending punctuation followed by whitespace: '. ', '! ', '? '
    Accumulates sentences into chunks until max_chars is reached.

    Args:
        text: Text to split.
        max_chars: Maximum characters per chunk.

    Returns:
        List of chunk text strings.
    """
    # Split on sentence boundaries: period, exclamation, or question mark
    # followed by a space or newline
    sentences = re.split(r"(?<=[.!?])\s+", text)

    chunks = []
    current_chunk = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        if not current_chunk:
            current_chunk = sentence
        elif len(current_chunk) + 1 + len(sentence) <= max_chars:
            current_chunk += " " + sentence
        else:
            chunks.append(current_chunk)
            current_chunk = sentence

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def _build_chunk_record(text: str, metadata: dict, chunk_index: int) -> ChunkRecord:
    """Build a ChunkRecord from section metadata and chunk text.

    Maps section metadata fields to ChunkMetadata fields. Sets chunk_total
    to 0 (updated later by chunk_section) and leaves embedding model fields
    empty (set during embedding).

    Args:
        text: The chunk text content.
        metadata: Section metadata dict from YAML front matter.
        chunk_index: 0-based index of this chunk within the section.

    Returns:
        ChunkRecord with full metadata.
    """
    # Extract content_type.primary, defaulting to "general"
    content_type = (
        metadata.get("content_type", {}).get("primary", "general") or "general"
    )

    chunk_metadata = ChunkMetadata(
        source_document=metadata.get("source_document", ""),
        source_title=metadata.get("source_title", ""),
        section_header=metadata.get("section_heading", ""),
        page_number=metadata.get("page_start", 0),
        content_type=content_type,
        categories=metadata.get("categories", []),
        source_url=metadata.get("provenance", {}).get("source_url", ""),
        license=metadata.get("provenance", {}).get("license", ""),
        distribution_statement=metadata.get("provenance", {}).get(
            "distribution_statement", ""
        ),
        verification_date=metadata.get("processing_date", ""),
        chunk_index=chunk_index,
        chunk_total=0,  # Set later by chunk_section
        embedding_model="",  # Set later during embedding
        embedding_model_version="",  # Set later during embedding
        warning_level=metadata.get("warning_level"),
        warning_text=metadata.get("warning_text"),
    )

    return ChunkRecord(text=text.strip(), metadata=chunk_metadata)


def chunk_document(sections_dir: Path) -> list[ChunkRecord]:
    """Chunk all section files for a single document.

    Lists all .md files in sections_dir sorted by name (preserving section
    order), reads each file's metadata and content, and produces chunks.

    Args:
        sections_dir: Path to the directory containing section .md files
            for a single document (e.g., processed/sections/FM-21-76/).

    Returns:
        Flat list of all ChunkRecords for the document.
    """
    section_files = sorted(sections_dir.glob("*.md"))
    all_chunks: list[ChunkRecord] = []

    for filepath in section_files:
        try:
            metadata, content = read_section_file(filepath)
            if not content.strip():
                logger.debug("Skipping empty section: %s", filepath.name)
                continue

            chunks = chunk_section(content, metadata)
            all_chunks.extend(chunks)
            logger.debug(
                "Chunked %s: %d chunks from %s",
                filepath.name,
                len(chunks),
                metadata.get("content_type", {}).get("primary", "general"),
            )
        except Exception as e:
            logger.error("Error chunking %s: %s", filepath, e)

    logger.info(
        "Document %s: %d sections -> %d chunks",
        sections_dir.name,
        len(section_files),
        len(all_chunks),
    )

    return all_chunks
