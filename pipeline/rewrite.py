"""Query rewriting for multi-turn conversations.

Every user message is rewritten into a standalone query that carries the full
conversational context. This ensures the retrieval engine always finds relevant
chunks, whether the user asks a brand new question or continues a thread.
"""

import logging

import ollama

import pipeline.generate as gen

logger = logging.getLogger(__name__)

_REWRITE_SYSTEM = (
    "You rewrite user messages into standalone search queries that carry "
    "the full conversational context. Output ONLY the rewritten query — "
    "nothing else. No quotes, no preamble."
)

_REWRITE_PROMPT = """Conversation so far:
{context}

The user just said: "{query}"

Rewrite this as a standalone question or statement that captures the full
context of what they need. Someone reading ONLY your rewrite should understand
exactly what the user is asking without seeing the conversation. Under 30 words.

REWRITTEN QUERY:"""


def rewrite_with_context(query: str, history: list[dict]) -> str:
    """Rewrite a user message using conversation history.

    Always rewrites when history exists so the retrieval engine gets a
    context-rich query. Returns the original query only when there is
    no prior conversation or if the rewrite fails.
    """
    if not history or len(history) < 2:
        return query

    stripped = query.strip()

    # Build context from last 6 messages (3 exchanges)
    recent = history[-6:]
    lines = []
    for msg in recent:
        role = "User" if msg.get("role") == "user" else "Assistant"
        content = msg.get("content", "")[:300]
        lines.append(f"{role}: {content}")
    context = "\n".join(lines)

    prompt = _REWRITE_PROMPT.format(context=context, query=stripped)

    try:
        response = ollama.generate(
            model=gen._model,
            prompt=prompt,
            system=_REWRITE_SYSTEM,
            stream=False,
            options={"num_predict": 60, "temperature": 0.1},
        )
        rewritten = response.get("response", "").strip().strip('"')
        if not rewritten:
            return query
        logger.info("Query rewritten: %r -> %r", query, rewritten)
        return rewritten
    except Exception:
        logger.warning("Query rewrite failed, using original", exc_info=True)
        return query
