#!/bin/bash
set -e

OLLAMA_URL="${OLLAMA_HOST:-http://ollama:11434}"

echo "SurvivalRAG: Waiting for Ollama at $OLLAMA_URL..."
MAX_RETRIES=60
for i in $(seq 1 $MAX_RETRIES); do
    if curl -sf "$OLLAMA_URL/api/tags" > /dev/null 2>&1; then
        echo "SurvivalRAG: Ollama is ready."
        break
    fi
    if [ "$i" -eq "$MAX_RETRIES" ]; then
        echo "SurvivalRAG: WARNING - Ollama not available after ${MAX_RETRIES}s, starting anyway..."
    fi
    sleep 1
done

# Build ChromaDB vector store from pre-embedded chunks if it doesn't exist yet
if [ ! -f "./data/chroma/chroma.sqlite3" ]; then
    echo "SurvivalRAG: Building vector store from pre-embedded chunks (first run only)..."
    python -c "
from pathlib import Path
from pipeline.ingest import ingest_directory, get_collection
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
collection = get_collection('./data/chroma')
total = ingest_directory(Path('./processed/chunks'), collection=collection)
print(f'SurvivalRAG: Vector store built with {total} chunks.')
"
    echo "SurvivalRAG: Vector store ready."
else
    echo "SurvivalRAG: Vector store already exists, skipping build."
fi

echo "SurvivalRAG: Starting application..."
exec python -c "
import os
os.environ.setdefault('SURVIVALRAG_PORT', '8080')
from web import build_source_map, app
import pipeline.retrieve as retrieve
import pipeline.generate as gen
import uvicorn
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
build_source_map()
retrieve.init(chroma_path='./data/chroma')
gen.init()
uvicorn.run(app, host='0.0.0.0', port=int(os.environ.get('SURVIVALRAG_PORT', '8080')))
"
