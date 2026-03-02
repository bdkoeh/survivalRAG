#!/usr/bin/env python3
"""Quick interactive query tool for testing the RAG pipeline."""

import sys

import pipeline.retrieve as retrieve
import pipeline.generate as gen


def main():
    print("Loading knowledge base...", flush=True)
    retrieve.init(chroma_path="./data/chroma")
    gen.init()
    print(f"Ready. Model: {gen._model}  |  Chunks: {retrieve._collection.count()}")
    print("Type a question, or 'quit' to exit.\n")

    while True:
        try:
            query = input(">> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not query or query.lower() in ("quit", "exit", "q"):
            break

        # Pick mode from prefix
        mode = "full"
        if query.startswith("/compact "):
            mode = "compact"
            query = query[9:]
        elif query.startswith("/ultra "):
            mode = "ultra"
            query = query[7:]

        status, tokens = gen.answer_stream(query_text=query, mode=mode)
        if status == "refused":
            for t in tokens:
                print(t, end="", flush=True)
        else:
            for t in tokens:
                print(t, end="", flush=True)
        print("\n")


if __name__ == "__main__":
    main()
