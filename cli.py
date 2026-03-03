#!/usr/bin/env python3
"""SurvivalRAG CLI -- command-line interface for querying the survival knowledge base.

Provides two usage modes:

  Single-shot:  python cli.py ask "how to purify water" --mode compact
  Interactive:  python cli.py   (drops into REPL)

Uses Click for argument parsing. Safety warnings from source material are
displayed before the main response (safety-first principle).

Exports:
    cli  - Click group entry point
    ask  - Single-shot query subcommand
    repl - Interactive REPL mode
"""

import sys
import logging

import click

import pipeline.retrieve as retrieve
import pipeline.generate as gen

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pipeline initialization
# ---------------------------------------------------------------------------

def _init_pipeline():
    """Initialize retrieval and generation engines. Fail fast with clear error messages."""
    try:
        retrieve.init(chroma_path="./data/chroma")
        gen.init()
    except ConnectionError:
        click.echo(
            "Error: Ollama is not running. Start with: ollama serve", err=True
        )
        sys.exit(1)
    except RuntimeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Startup error: {e}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Response display (plain text -- upgraded to Rich in Task 2)
# ---------------------------------------------------------------------------

def display_response(result: dict):
    """Display a pipeline response dict.

    Displays safety warnings before the main response, handles refusal
    responses gracefully.

    Args:
        result: Dict from gen.answer() with keys: response, status, warnings,
            verification, mode, model.
    """
    # Refusal path
    if result["status"] == "refused":
        print(f"\n[No Results] {result['response']}\n")
        return

    # Safety warnings FIRST (safety-first principle from CLAUDE.md)
    for warning in result.get("warnings", []):
        source = warning.get("source_document", "Unknown")
        page = warning.get("page_number", 0)
        print(f"\n!! WARNING -- {source}, p.{page} !!")
        print(f"   {warning['warning_text']}")

    # Main response
    print()
    print(result["response"])

    # Citation verification note
    verification = result.get("verification") or {}
    if verification.get("passed") is False:
        print(
            "\nNote: Some citations could not be verified "
            "against source documents."
        )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """SurvivalRAG: Offline survival and emergency preparedness knowledge base."""
    if ctx.invoked_subcommand is None:
        repl()


# ---------------------------------------------------------------------------
# Ask subcommand (single-shot)
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("query")
@click.option(
    "--category",
    "-c",
    default=None,
    help="Comma-separated categories: medical,water,shelter,fire,food,navigation,signaling,tools,first_aid",
)
@click.option(
    "--mode",
    "-m",
    "response_mode",
    default="full",
    type=click.Choice(["full", "compact", "ultra"]),
    help="Response mode (default: full)",
)
def ask(query, category, response_mode):
    """Ask a survival or emergency preparedness question."""
    categories = (
        [c.strip() for c in category.split(",")]
        if category
        else None
    )

    _init_pipeline()
    result = gen.answer(
        query_text=query, categories=categories, mode=response_mode
    )
    display_response(result)


# ---------------------------------------------------------------------------
# REPL mode
# ---------------------------------------------------------------------------

def repl():
    """Interactive REPL for querying the knowledge base."""
    print("SurvivalRAG v1.0")
    print("Reference tool only -- not medical advice.")

    _init_pipeline()

    print(
        f"Ready. Model: {gen._model} "
        f"| Chunks: {retrieve._collection.count():,}"
    )
    print("Type a question, or 'quit' to exit.\n")

    while True:
        try:
            raw = input(">> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break

        query = raw.strip()
        if not query:
            continue
        if query.lower() in ("quit", "exit", "q"):
            break

        # Parse mode prefix shortcuts
        mode = "full"
        categories = None

        if query.startswith("/compact "):
            mode = "compact"
            query = query[9:]
        elif query.startswith("/ultra "):
            mode = "ultra"
            query = query[7:]
        elif query.startswith("/full "):
            mode = "full"
            query = query[6:]

        # Parse category prefix: /category medical,water <query> or /cat medical <query>
        if query.startswith("/category ") or query.startswith("/cat "):
            prefix_len = 10 if query.startswith("/category ") else 5
            rest = query[prefix_len:]
            parts = rest.split(" ", 1)
            if len(parts) == 2:
                categories = [c.strip() for c in parts[0].split(",")]
                query = parts[1]
            else:
                print("Usage: /category medical,water <query>")
                continue

        try:
            result = gen.answer(
                query_text=query, categories=categories, mode=mode
            )
            display_response(result)
        except Exception as e:
            print(f"Error: {e}")

        print()  # blank line separator


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli()
