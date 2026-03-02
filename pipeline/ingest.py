"""ChromaDB ingestion module for loading Phase 3 JSONL chunk files.

Loads pre-embedded ChunkRecords from JSONL files into a ChromaDB collection
configured with cosine distance space. Supports batched ingestion, deduplication,
and metadata conversion for ChromaDB compatibility.

The collection stores pre-computed 768-dim nomic-embed-text embeddings with
full provenance metadata including array categories for $contains filtering.
"""

import json
import logging
from pathlib import Path

import pipeline._chromadb_compat  # noqa: F401 -- must patch before chromadb import
import chromadb

from pipeline.models import ChunkMetadata, ChunkRecord

logger = logging.getLogger(__name__)

# ChromaDB persistent storage directory
CHROMA_PATH = "./data/chroma"

# ChromaDB collection name
COLLECTION_NAME = "survivalrag"

# Batch size for ChromaDB add() calls to avoid memory issues on large ingests
BATCH_SIZE = 500


def get_collection(path: str = CHROMA_PATH) -> chromadb.Collection:
    """Get or create the survivalrag ChromaDB collection with cosine distance.

    Creates a PersistentClient at the specified path and returns the collection
    configured with HNSW cosine distance space.

    Args:
        path: Directory path for ChromaDB persistent storage.

    Returns:
        ChromaDB Collection configured with cosine distance space.
    """
    client = chromadb.PersistentClient(path=path)
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        configuration={
            "hnsw": {
                "space": "cosine",
                "ef_construction": 200,
                "ef_search": 100,
            }
        },
    )
    return collection


def load_jsonl(filepath: Path) -> list[ChunkRecord]:
    """Load ChunkRecords from a JSONL file.

    Each line in the file should be a JSON object matching the ChunkRecord schema.
    Lines that fail to parse are skipped with a warning log.

    Args:
        filepath: Path to the JSONL file.

    Returns:
        List of successfully parsed ChunkRecords.
    """
    records: list[ChunkRecord] = []
    filepath = Path(filepath)

    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                record = ChunkRecord.model_validate(data)
                records.append(record)
            except Exception as e:
                logger.warning(
                    "Failed to parse line %d in %s: %s", line_num, filepath.name, e
                )

    logger.info("Loaded %d chunks from %s", len(records), filepath.name)
    return records


def chunk_to_chroma_id(chunk: ChunkRecord) -> str:
    """Generate a deterministic, unique ID for a chunk.

    Format: {source_document}_{page_number:03d}_{chunk_index:03d}
    Example: FM-21-76_045_002

    Args:
        chunk: ChunkRecord to generate an ID for.

    Returns:
        Deterministic string ID for the chunk.
    """
    return (
        f"{chunk.metadata.source_document}"
        f"_{chunk.metadata.page_number:03d}"
        f"_{chunk.metadata.chunk_index:03d}"
    )


def chunk_metadata_to_dict(metadata: ChunkMetadata) -> dict:
    """Convert ChunkMetadata to a flat dict suitable for ChromaDB metadata storage.

    ChromaDB metadata values must be: str, int, float, bool, or list[str/int/float].
    None values are converted to empty strings since ChromaDB does not support None.
    Categories are stored as a list (not comma-separated string) for $contains filtering.

    Args:
        metadata: ChunkMetadata to convert.

    Returns:
        Flat dict with ChromaDB-compatible value types.
    """
    return {
        "source_document": metadata.source_document,
        "source_title": metadata.source_title,
        "section_header": metadata.section_header,
        "page_number": metadata.page_number,
        "content_type": metadata.content_type,
        "categories": metadata.categories,  # list[str] for $contains filtering
        "source_url": metadata.source_url,
        "license": metadata.license,
        "distribution_statement": metadata.distribution_statement,
        "verification_date": metadata.verification_date,
        "chunk_index": metadata.chunk_index,
        "chunk_total": metadata.chunk_total,
        "embedding_model": metadata.embedding_model,
        "embedding_model_version": metadata.embedding_model_version,
        "warning_level": metadata.warning_level if metadata.warning_level is not None else "",
        "warning_text": metadata.warning_text if metadata.warning_text is not None else "",
    }


def ingest_chunks(
    chunks: list[ChunkRecord], collection: chromadb.Collection = None
) -> int:
    """Ingest ChunkRecords into ChromaDB with pre-computed embeddings and metadata.

    Deduplicates by chunk ID (keeps first occurrence). Adds chunks in batches
    of BATCH_SIZE to avoid memory issues on large ingests.

    Args:
        chunks: List of ChunkRecords to ingest.
        collection: ChromaDB collection to ingest into. If None, uses default.

    Returns:
        Total number of chunks ingested.
    """
    if collection is None:
        collection = get_collection()

    # Build deduplicated lists
    seen_ids: set[str] = set()
    ids: list[str] = []
    documents: list[str] = []
    embeddings: list[list[float]] = []
    metadatas: list[dict] = []

    for chunk in chunks:
        # Skip chunks with empty embeddings
        if not chunk.embedding:
            logger.warning(
                "Skipping chunk with empty embedding: %s",
                chunk.metadata.source_document,
            )
            continue

        chunk_id = chunk_to_chroma_id(chunk)

        if chunk_id in seen_ids:
            logger.warning("Duplicate chunk ID %s -- keeping first occurrence", chunk_id)
            continue

        seen_ids.add(chunk_id)
        ids.append(chunk_id)
        documents.append(chunk.text)
        embeddings.append(chunk.embedding)
        metadatas.append(chunk_metadata_to_dict(chunk.metadata))

    if not ids:
        logger.warning("No chunks to ingest after deduplication and filtering")
        return 0

    # Add to ChromaDB in batches
    total_batches = (len(ids) + BATCH_SIZE - 1) // BATCH_SIZE
    for batch_idx in range(0, len(ids), BATCH_SIZE):
        batch_end = min(batch_idx + BATCH_SIZE, len(ids))
        batch_num = batch_idx // BATCH_SIZE + 1

        collection.add(
            ids=ids[batch_idx:batch_end],
            documents=documents[batch_idx:batch_end],
            embeddings=embeddings[batch_idx:batch_end],
            metadatas=metadatas[batch_idx:batch_end],
        )

        logger.info(
            "Ingested batch %d/%d (%d chunks)",
            batch_num,
            total_batches,
            batch_end - batch_idx,
        )

    total_ingested = len(ids)
    logger.info("Total chunks ingested: %d", total_ingested)
    return total_ingested


def ingest_directory(
    jsonl_dir: Path, collection: chromadb.Collection = None
) -> int:
    """Ingest all JSONL files in a directory into ChromaDB.

    Loads each .jsonl file and ingests its chunks into the collection.

    Args:
        jsonl_dir: Directory containing JSONL chunk files.
        collection: ChromaDB collection to ingest into. If None, uses default.

    Returns:
        Total number of chunks ingested across all files.
    """
    if collection is None:
        collection = get_collection()

    jsonl_dir = Path(jsonl_dir)
    jsonl_files = sorted(jsonl_dir.glob("*.jsonl"))

    if not jsonl_files:
        logger.warning("No .jsonl files found in %s", jsonl_dir)
        return 0

    total_ingested = 0
    for filepath in jsonl_files:
        chunks = load_jsonl(filepath)
        if chunks:
            count = ingest_chunks(chunks, collection=collection)
            logger.info("Ingested %s: %d chunks", filepath.name, count)
            total_ingested += count

    logger.info("Total ingested from directory: %d chunks", total_ingested)
    return total_ingested


def get_all_chunks_for_bm25(
    collection: chromadb.Collection = None,
) -> tuple[list[str], list[str], list[dict]]:
    """Retrieve all documents and metadata from ChromaDB for BM25 index building.

    Called at application startup by the retrieval module to build the in-memory
    BM25 keyword search index.

    Args:
        collection: ChromaDB collection to read from. If None, uses default.

    Returns:
        Tuple of (ids, documents, metadatas) for BM25 index building.
    """
    if collection is None:
        collection = get_collection()

    result = collection.get(include=["documents", "metadatas"])

    ids = result["ids"]
    documents = result["documents"]
    metadatas = result["metadatas"]

    logger.info("Retrieved %d chunks for BM25 index", len(ids))
    return ids, documents, metadatas
