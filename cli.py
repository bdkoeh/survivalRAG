#!/usr/bin/env python3
"""SurvivalRAG CLI -- command-line interface for querying the survival knowledge base.

Provides two usage modes:

  Single-shot:  python cli.py ask "how to purify water" --mode compact
  Interactive:  python cli.py   (drops into REPL)

Uses Click for argument parsing and Rich for terminal-formatted markdown output.
Safety warnings from source material are rendered as colored panels before the
main response (safety-first principle).

Exports:
    cli  - Click group entry point
    ask  - Single-shot query subcommand
    repl - Interactive REPL mode
"""

import sys
import logging

import click

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

import pipeline.retrieve as retrieve
import pipeline.generate as gen

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level Rich Console
# ---------------------------------------------------------------------------
console = Console()


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
# Response display with Rich formatting
# ---------------------------------------------------------------------------

def display_response(result: dict):
    """Render a pipeline response dict with Rich formatting.

    Displays safety warnings as colored panels, then the main response
    as rendered markdown. Handles refusal responses gracefully.

    Args:
        result: Dict from gen.answer() with keys: response, status, warnings,
            verification, mode, model.
    """
    # Refusal path
    if result["status"] == "refused":
        console.print(
            Panel(result["response"], title="No Results", border_style="yellow")
        )
        return

    # Safety warnings FIRST (safety-first principle from CLAUDE.md)
    for warning in result.get("warnings", []):
        warning_level = warning.get("warning_level", "warning")
        if warning_level in ("danger", "caution"):
            border = "red"
        else:
            border = "yellow"

        source = warning.get("source_document", "Unknown")
        page = warning.get("page_number", 0)
        title = f"WARNING -- {source}, p.{page}"

        console.print(
            Panel(
                Text(warning["warning_text"], style="bold"),
                title=title,
                border_style=border,
            )
        )

    # Main response as Rich Markdown
    console.print(Markdown(result["response"]))

    # Citation verification note (unobtrusive but visible)
    verification = result.get("verification") or {}
    if verification.get("passed") is False:
        console.print(
            "[dim italic]Note: Some citations could not be verified "
            "against source documents.[/dim italic]"
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
    console.print("[bold green]SurvivalRAG v1.0[/bold green]")
    console.print("[dim]Reference tool only -- not medical advice.[/dim]")

    _init_pipeline()

    console.print(
        f"[green]Ready.[/green] Model: {gen._model} "
        f"| Chunks: {retrieve._collection.count():,}"
    )
    console.print("[dim]Type a question, or 'quit' to exit.[/dim]\n")

    while True:
        try:
            raw = console.input("[bold green]>> [/bold green]")
        except (EOFError, KeyboardInterrupt):
            console.print()
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
                console.print("[red]Usage: /category medical,water <query>[/red]")
                continue

        try:
            result = gen.answer(
                query_text=query, categories=categories, mode=mode
            )
            display_response(result)
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

        console.print()  # blank line separator


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli()
