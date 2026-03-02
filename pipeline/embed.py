"""Batch-safe Ollama embedding wrapper with nomic-embed-text prefix convention.

Wraps all embedding calls through helper functions that enforce the required
search_document: / search_query: prefixes for nomic-embed-text and limit
batch sizes to 8 per Ollama issue #6262 (batch 16+ degrades quality).

IMPORTANT: Never call ollama.embed() directly from outside this module.
All embedding must go through embed_documents() or embed_query() to ensure
correct prefixes are always applied.
"""

import logging
from typing import Optional

import ollama

from pipeline.models import ChunkRecord
from pipeline.spellcheck import correct_query

logger = logging.getLogger(__name__)

# Safe batch size per Ollama issue #6262 (batch 16+ degrades quality)
BATCH_SIZE = 8

# Default embedding model (locked decision from CONTEXT.md)
DEFAULT_MODEL = "nomic-embed-text"

# Expected embedding dimension for nomic-embed-text
EMBEDDING_DIM = 768


def get_model_version(model: str = DEFAULT_MODEL) -> str:
    """Query Ollama for the model version/digest string.

    Args:
        model: Model name to query. Defaults to nomic-embed-text.

    Returns:
        Model digest/version string.

    Raises:
        ConnectionError: If Ollama is not running.
        RuntimeError: If the model is not available.
    """
    try:
        info = ollama.show(model)
        # Extract digest from model info
        if isinstance(info, dict):
            # Try modelinfo.general.file_type or digest
            details = info.get("details", {})
            digest = info.get("digest", "")
            family = details.get("family", "")
            parameter_size = details.get("parameter_size", "")
            quantization = details.get("quantization_level", "")
            version_parts = [p for p in [family, parameter_size, quantization, digest[:12]] if p]
            return " ".join(version_parts) if version_parts else str(info.get("digest", "unknown"))
        else:
            # Typed object access
            details = getattr(info, "details", None)
            digest = getattr(info, "digest", "unknown")
            if details:
                family = getattr(details, "family", "")
                parameter_size = getattr(details, "parameter_size", "")
                quantization = getattr(details, "quantization_level", "")
                version_parts = [p for p in [family, parameter_size, quantization, str(digest)[:12]] if p]
                return " ".join(version_parts) if version_parts else str(digest)[:12]
            return str(digest)[:12]
    except ConnectionError:
        raise ConnectionError(
            "Ollama is not running. Start it with: ollama serve"
        )
    except ollama.ResponseError as e:
        raise RuntimeError(
            f"Model '{model}' is not available. Pull it with: ollama pull {model}\n"
            f"Error: {e}"
        )
    except Exception as e:
        if "connection" in str(e).lower() or "refused" in str(e).lower():
            raise ConnectionError(
                "Ollama is not running or nomic-embed-text is not pulled. "
                "Run: ollama pull nomic-embed-text"
            )
        raise


def embed_documents(
    texts: list[str], model: str = DEFAULT_MODEL
) -> list[list[float]]:
    """Embed document texts with the required search_document: prefix.

    Processes texts in batches of BATCH_SIZE to avoid quality degradation.
    Each text is prepended with "search_document: " as required by
    nomic-embed-text.

    Args:
        texts: List of document text strings to embed.
        model: Embedding model name. Defaults to nomic-embed-text.

    Returns:
        List of embedding vectors (each 768 floats for nomic-embed-text).

    Raises:
        ConnectionError: If Ollama is not running.
        ValueError: If embeddings have unexpected dimensions.
    """
    if not texts:
        return []

    all_embeddings: list[list[float]] = []
    total_batches = (len(texts) + BATCH_SIZE - 1) // BATCH_SIZE

    for batch_idx in range(0, len(texts), BATCH_SIZE):
        batch = texts[batch_idx : batch_idx + BATCH_SIZE]
        batch_num = batch_idx // BATCH_SIZE + 1

        # Prepend search_document: prefix (CRITICAL for nomic-embed-text)
        prefixed = [f"search_document: {t}" for t in batch]

        try:
            response = ollama.embed(model=model, input=prefixed)
        except ConnectionError:
            raise ConnectionError(
                "Ollama is not running. Start it with: ollama serve"
            )
        except Exception as e:
            if "connection" in str(e).lower() or "refused" in str(e).lower():
                raise ConnectionError(
                    "Ollama is not running or nomic-embed-text is not pulled. "
                    "Run: ollama pull nomic-embed-text"
                )
            raise

        # Access embeddings -- try dict access first, fall back to attribute
        if isinstance(response, dict):
            embeddings = response["embeddings"]
        else:
            embeddings = response.embeddings

        # Validate dimensions
        for i, emb in enumerate(embeddings):
            if len(emb) != EMBEDDING_DIM:
                raise ValueError(
                    f"Embedding dimension mismatch: expected {EMBEDDING_DIM}, "
                    f"got {len(emb)} for text at index {batch_idx + i}"
                )

        all_embeddings.extend(embeddings)
        logger.info(
            "Embedded batch %d/%d (%d texts)", batch_num, total_batches, len(batch)
        )

    return all_embeddings


def embed_query(
    query: str, model: str = DEFAULT_MODEL, spell_correct: bool = True
) -> list[float]:
    """Embed a search query with the required search_query: prefix.

    Uses the search_query: prefix (different from search_document: used
    for corpus text). This is critical for nomic-embed-text retrieval quality.

    Args:
        query: The search query text.
        model: Embedding model name. Defaults to nomic-embed-text.
        spell_correct: If True, apply domain-aware spell correction before
            embedding. Helps recover typo queries like "diareah" -> "diarrhea".

    Returns:
        Single embedding vector (768 floats for nomic-embed-text).

    Raises:
        ConnectionError: If Ollama is not running.
    """
    # Apply spell correction before prefixing
    if spell_correct:
        query = correct_query(query)

    # Prepend search_query: prefix (CRITICAL: different from document prefix)
    prefixed = f"search_query: {query}"

    try:
        response = ollama.embed(model=model, input=prefixed)
    except ConnectionError:
        raise ConnectionError(
            "Ollama is not running. Start it with: ollama serve"
        )
    except Exception as e:
        if "connection" in str(e).lower() or "refused" in str(e).lower():
            raise ConnectionError(
                "Ollama is not running or nomic-embed-text is not pulled. "
                "Run: ollama pull nomic-embed-text"
            )
        raise

    # Access embeddings
    if isinstance(response, dict):
        embeddings = response["embeddings"]
    else:
        embeddings = response.embeddings

    return embeddings[0]


def embed_chunk_records(
    chunks: list[ChunkRecord], model: str = DEFAULT_MODEL
) -> list[ChunkRecord]:
    """Embed a list of ChunkRecords, populating their embedding fields.

    Gets the model version from Ollama, embeds all chunk texts, and sets
    the embedding vector plus model metadata on each ChunkRecord.

    Mutates records in place for efficiency and returns the same list.

    Args:
        chunks: List of ChunkRecords to embed.
        model: Embedding model name. Defaults to nomic-embed-text.

    Returns:
        The same list of ChunkRecords with embedding fields populated.
    """
    if not chunks:
        return chunks

    # Get model version for metadata
    version = get_model_version(model)
    logger.info("Embedding %d chunks with %s (%s)", len(chunks), model, version)

    # Extract texts and embed
    texts = [chunk.text for chunk in chunks]
    embeddings = embed_documents(texts, model=model)

    # Set embedding and model metadata on each chunk
    for chunk, embedding in zip(chunks, embeddings):
        chunk.embedding = embedding
        chunk.metadata.embedding_model = model
        chunk.metadata.embedding_model_version = version

    logger.info("Embedded %d chunks successfully", len(chunks))
    return chunks
