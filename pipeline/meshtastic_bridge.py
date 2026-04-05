"""Meshtastic mesh radio bridge for SurvivalRAG.

Connects the survival knowledge RAG pipeline to a Meshtastic mesh network,
allowing any radio on the mesh to query the knowledge base by sending a
text message. Responses are split across multiple radio messages with part
numbering, respecting LoRa's 233-byte packet limit.

Requires: pip install meshtastic>=2.7.0
Connection: USB serial (auto-detect) or TCP (WiFi node)

Exports:
    MeshtasticBridge      - Main bridge class (connect, run, disconnect)
    load_config           - Load configuration from env vars
    split_for_mesh        - Message splitting algorithm (usable standalone)
    strip_markdown_for_mesh - Markdown stripping for radio-friendly text
    prepend_warnings      - Prepend safety warnings to response text
"""

import logging
import os
import re
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_CHUNK_SIZE = 194       # 200 - 6 bytes reserved for part numbering
DEFAULT_MAX_PARTS = 5
DEFAULT_CHUNK_DELAY = 2.0
DEFAULT_CHANNEL = 0
DEFAULT_TRIGGER = "?"
DEFAULT_BOT_PREFIX = "[RAG]"
DEFAULT_RESPONSE_MODE = "compact"
MAX_PACKET_BYTES = 233         # Meshtastic protocol hard limit
DEDUP_TTL_SECONDS = 60
RECONNECT_BACKOFF = [5, 10, 20, 40, 60]
THINKING_MSG = "Thinking..."


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def load_config() -> dict:
    """Load bridge configuration from MESHTASTIC_* environment variables."""
    return {
        "enabled": os.getenv("MESHTASTIC_ENABLED", "false").lower() == "true",
        "connection": os.getenv("MESHTASTIC_CONNECTION", "serial"),
        "channel": int(os.getenv("MESHTASTIC_CHANNEL", str(DEFAULT_CHANNEL))),
        "trigger": os.getenv("MESHTASTIC_TRIGGER", DEFAULT_TRIGGER),
        "chunk_size": int(os.getenv("MESHTASTIC_CHUNK_SIZE", str(DEFAULT_CHUNK_SIZE))),
        "max_parts": int(os.getenv("MESHTASTIC_MAX_PARTS", str(DEFAULT_MAX_PARTS))),
        "chunk_delay": float(os.getenv("MESHTASTIC_CHUNK_DELAY", str(DEFAULT_CHUNK_DELAY))),
        "response_mode": os.getenv("MESHTASTIC_RESPONSE_MODE", DEFAULT_RESPONSE_MODE),
        "bot_prefix": os.getenv("MESHTASTIC_BOT_PREFIX", DEFAULT_BOT_PREFIX),
    }


# ---------------------------------------------------------------------------
# Pure functions — no meshtastic dependency, testable standalone
# ---------------------------------------------------------------------------

_CITATION_RE = re.compile(r"\(Source:\s*[^)]+\)")
_BOLD_RE = re.compile(r"\*\*")
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")
_MULTI_SPACE_RE = re.compile(r" {2,}")


def strip_markdown_for_mesh(text: str) -> str:
    """Remove markdown formatting and citations for radio-friendly plaintext.

    Strips bold markers, citation parentheticals, and collapses excess
    whitespace. Content words, dosages, and measurements are never modified.
    """
    text = _BOLD_RE.sub("", text)
    text = _CITATION_RE.sub("", text)
    text = _MULTI_NEWLINE_RE.sub("\n\n", text)
    text = _MULTI_SPACE_RE.sub(" ", text)
    return text.strip()


def prepend_warnings(response_text: str, warnings: list[dict]) -> str:
    """Prepend highest-severity safety warning to response text.

    If warnings exist, formats the first one (highest severity from
    collect_safety_warnings) as "WARNING: <text>" and prepends it.
    The splitting algorithm then naturally places this in part 1.
    """
    if not warnings:
        return response_text

    warning = warnings[0]
    level = warning.get("warning_level", "WARNING").upper()
    text = warning.get("warning_text", "")
    if not text:
        return response_text

    prefix = f"{level}: {text}"
    return f"{prefix}\n{response_text}"


def split_for_mesh(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    max_parts: int = DEFAULT_MAX_PARTS,
) -> list[str]:
    """Split text into radio-sized parts with [i/n] numbering.

    Uses sentence-boundary-first splitting with word-boundary fallback.
    Guarantees every returned part is <= chunk_size + 6 bytes UTF-8
    (i.e. fits in a 200-byte Meshtastic payload with part numbering).

    Args:
        text: The text to split (should already be stripped of markdown).
        chunk_size: Max bytes per part before the [i/n] suffix.
        max_parts: Maximum number of parts to emit.

    Returns:
        List of message strings, each with [i/n] suffix if multi-part.
        Empty list if text is empty.
    """
    if not text:
        return []

    text_bytes = len(text.encode("utf-8"))

    # Single message — no part numbering needed
    if text_bytes <= chunk_size:
        return [text]

    # Split into parts
    parts = []
    remaining = text

    while remaining and len(parts) < max_parts:
        is_last_allowed = len(parts) == max_parts - 1

        # Calculate byte budget for this part's content
        # We don't know total parts yet for numbering, so use max_parts as estimate
        # Final numbering is applied after all parts are determined
        budget = chunk_size

        # Find the split point
        split_idx = _find_split_point(remaining, budget)

        if split_idx <= 0:
            # Edge case: first character is multi-byte and exceeds budget alone
            # Take at least one character
            split_idx = 1

        chunk = remaining[:split_idx].rstrip()
        remaining = remaining[split_idx:].lstrip()

        if is_last_allowed and remaining:
            # Truncation: append ellipsis if we're cutting off content
            chunk_bytes = len(chunk.encode("utf-8"))
            if chunk_bytes + 3 <= budget:
                chunk = chunk + "..."
            else:
                # Re-split to make room for ellipsis
                shorter_idx = _find_split_point(chunk, budget - 3)
                if shorter_idx > 0:
                    chunk = chunk[:shorter_idx].rstrip() + "..."

        parts.append(chunk)

    if not parts:
        return []

    # Single part after splitting (rare but possible if text barely fit)
    if len(parts) == 1:
        return parts

    # Apply part numbering
    total = len(parts)
    numbered = []
    for i, part in enumerate(parts, 1):
        suffix = f" [{i}/{total}]"
        suffix_bytes = len(suffix.encode("utf-8"))
        # Ensure part + suffix fits in budget (chunk_size + suffix overhead)
        part_bytes = len(part.encode("utf-8"))
        if part_bytes + suffix_bytes > chunk_size + 6:
            # Trim part to fit
            part = _trim_to_bytes(part, chunk_size + 6 - suffix_bytes)
        numbered.append(part + suffix)

    return numbered


def _find_split_point(text: str, max_bytes: int) -> int:
    """Find the best character index to split text at, respecting byte budget.

    Prefers sentence boundaries (. ! ? followed by space/newline), then
    word boundaries (space), then hard byte limit.
    """
    # Walk characters, tracking byte length and boundaries
    byte_count = 0
    last_sentence_end = -1
    last_word_end = -1

    for i, char in enumerate(text):
        char_bytes = len(char.encode("utf-8"))

        if byte_count + char_bytes > max_bytes:
            # Over budget — use best boundary found so far
            if last_sentence_end > 0:
                return last_sentence_end
            if last_word_end > 0:
                return last_word_end
            return i  # hard split

        byte_count += char_bytes

        # Track sentence boundaries: . ! ? followed by space or newline or end
        if char in ".!?" and i + 1 < len(text) and text[i + 1] in " \n":
            last_sentence_end = i + 1
        # Track word boundaries
        if char == " ":
            last_word_end = i
        if char == "\n":
            last_word_end = i
            # Newline after sentence-ending punctuation is also a sentence boundary
            if i > 0 and text[i - 1] in ".!?":
                last_sentence_end = i

    # Entire remaining text fits
    return len(text)


def _trim_to_bytes(text: str, max_bytes: int) -> str:
    """Trim text to fit within max_bytes UTF-8, at a word boundary if possible."""
    if len(text.encode("utf-8")) <= max_bytes:
        return text

    last_space = -1
    byte_count = 0
    for i, char in enumerate(text):
        char_bytes = len(char.encode("utf-8"))
        if byte_count + char_bytes > max_bytes:
            if last_space > 0:
                return text[:last_space]
            return text[:i]
        byte_count += char_bytes
        if char == " ":
            last_space = i

    return text


# ---------------------------------------------------------------------------
# Bridge class — requires meshtastic package (imported lazily)
# ---------------------------------------------------------------------------

class MeshtasticBridge:
    """Connects SurvivalRAG to a Meshtastic mesh network.

    Listens for text messages on the configured channel, passes queries
    through the RAG pipeline, and sends responses as multi-part messages.
    """

    def __init__(self, config: dict):
        self.config = config
        self.interface = None
        self._my_node_id = None
        self._seen_packets = OrderedDict()
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._pending_count = 0
        self._running = False

    def connect(self) -> None:
        """Establish connection to Meshtastic radio via Serial or TCP."""
        try:
            from meshtastic.serial_interface import SerialInterface
            from meshtastic.tcp_interface import TCPInterface
        except ImportError:
            raise ImportError(
                "meshtastic package not installed. Run: pip install meshtastic>=2.7.0"
            )

        conn = self.config["connection"]

        if conn.startswith("tcp://"):
            host = conn[6:]  # strip tcp://
            port = 4403      # meshtastic default TCP port
            if ":" in host:
                host, port_str = host.rsplit(":", 1)
                port = int(port_str)
            logger.info("Connecting to Meshtastic via TCP: %s:%d", host, port)
            self.interface = TCPInterface(hostname=host, portNumber=port)
        elif conn.startswith("serial:"):
            device = conn[7:]  # strip serial:
            logger.info("Connecting to Meshtastic via Serial: %s", device)
            self.interface = SerialInterface(devPath=device)
        else:
            # Default: serial auto-detect
            logger.info("Connecting to Meshtastic via Serial (auto-detect)")
            self.interface = SerialInterface()

        self._my_node_id = self._get_my_node_id()
        logger.info("Connected. My node ID: %s", self._my_node_id)

        # Subscribe to incoming text messages
        from pubsub import pub
        pub.subscribe(self._on_receive, "meshtastic.receive.text")
        logger.info(
            "Listening on channel %d, trigger prefix: '%s'",
            self.config["channel"],
            self.config["trigger"],
        )

    def disconnect(self) -> None:
        """Clean teardown of the Meshtastic interface."""
        self._running = False
        self._executor.shutdown(wait=False)
        if self.interface:
            try:
                self.interface.close()
            except Exception:
                pass
            self.interface = None
            logger.info("Meshtastic interface closed")

    def run(self) -> None:
        """Block until interrupted. The receive callback handles queries."""
        self._running = True
        prefix = self.config["bot_prefix"]
        trigger = self.config["trigger"]
        logger.info(
            "Bridge running. Send '%s<query>' on channel %d to query. "
            "Responses prefixed with '%s'.",
            trigger, self.config["channel"], prefix,
        )
        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            self.disconnect()

    def _get_my_node_id(self) -> str:
        """Get own node ID to prevent self-reply loops."""
        try:
            my_info = self.interface.getMyNodeInfo()
            return my_info.get("user", {}).get("id", "")
        except Exception:
            # Fallback: try the myInfo attribute
            try:
                return self.interface.myInfo.my_node_num
            except Exception:
                logger.warning("Could not determine own node ID")
                return ""

    def _on_receive(self, packet, interface) -> None:
        """Pub/sub callback for incoming text messages."""
        try:
            decoded = packet.get("decoded", {})
            text = decoded.get("text", "")
            if not text:
                return

            from_id = packet.get("fromId", "")
            to_id = packet.get("toId", "")
            channel = packet.get("channel", 0)
            packet_id = packet.get("id", 0)

            # Ignore own messages
            if from_id == self._my_node_id:
                return

            # Ignore wrong channel
            if channel != self.config["channel"]:
                return

            # Ignore messages that start with our bot prefix (prevent loops)
            bot_prefix = self.config["bot_prefix"]
            if bot_prefix and text.startswith(bot_prefix):
                return

            # Deduplication
            if self._is_duplicate(packet_id, from_id):
                return

            # Trigger prefix check
            trigger = self.config["trigger"]
            if trigger:
                if not text.startswith(trigger):
                    return
                text = text[len(trigger):].strip()

            if not text:
                return

            # Log incoming query
            snr = packet.get("rxSnr", "?")
            rssi = packet.get("rxRssi", "?")
            hops = packet.get("hopsAway", "?")
            logger.info(
                "Query from %s (SNR:%s RSSI:%s hops:%s): %s",
                from_id, snr, rssi, hops, text,
            )

            # Send thinking ack
            self._send_single(THINKING_MSG, from_id)

            # Dispatch to query handler
            if self._pending_count >= 2:
                self._send_single("Busy, try again shortly.", from_id)
                return

            self._pending_count += 1
            self._executor.submit(self._handle_query_safe, text, from_id)

        except Exception as e:
            logger.error("Error in receive handler: %s", e, exc_info=True)

    def _handle_query_safe(self, query_text: str, sender_id: str) -> None:
        """Wrapper that catches exceptions and decrements pending count."""
        try:
            self._handle_query(query_text, sender_id)
        except Exception as e:
            logger.error("Query handler error: %s", e, exc_info=True)
            try:
                self._send_single("System error, try again.", sender_id)
            except Exception:
                pass
        finally:
            self._pending_count -= 1

    def _handle_query(self, query_text: str, sender_id: str) -> None:
        """Process a query through the RAG pipeline and send response."""
        import pipeline.generate as gen

        try:
            result = gen.answer(
                query_text=query_text,
                mode=self.config["response_mode"],
            )
        except ConnectionError:
            self._send_single("LLM offline, try later.", sender_id)
            return

        if result["status"] == "refused":
            self._send_single(
                "No relevant survival info found. Try rephrasing.", sender_id
            )
            return

        text = result["response"]
        text = prepend_warnings(text, result.get("warnings", []))
        text = strip_markdown_for_mesh(text)
        parts = split_for_mesh(
            text,
            chunk_size=self.config["chunk_size"],
            max_parts=self.config["max_parts"],
        )

        if parts:
            self._send_chunked(parts, sender_id)
        else:
            self._send_single("No response generated.", sender_id)

    def _send_chunked(self, parts: list[str], destination: str) -> None:
        """Send multi-part response with delay between chunks."""
        channel = self.config["channel"]
        bot_prefix = self.config["bot_prefix"]
        delay = self.config["chunk_delay"]

        for i, part in enumerate(parts):
            msg = f"{bot_prefix} {part}" if bot_prefix else part

            # Safety check: never exceed protocol limit
            msg_bytes = len(msg.encode("utf-8"))
            if msg_bytes > MAX_PACKET_BYTES:
                logger.warning(
                    "Message exceeds %d bytes (%d), truncating",
                    MAX_PACKET_BYTES, msg_bytes,
                )
                msg = _trim_to_bytes(msg, MAX_PACKET_BYTES)

            try:
                self.interface.sendText(
                    msg,
                    destinationId=destination,
                    wantAck=True,
                    channelIndex=channel,
                )
                logger.debug("Sent part %d/%d to %s", i + 1, len(parts), destination)
            except Exception as e:
                logger.error("Send failed (part %d/%d): %s", i + 1, len(parts), e)
                return  # Stop sending remaining parts on failure

            if i < len(parts) - 1:
                time.sleep(delay)

    def _send_single(self, text: str, destination: str) -> None:
        """Send a single short message."""
        bot_prefix = self.config["bot_prefix"]
        msg = f"{bot_prefix} {text}" if bot_prefix else text

        msg_bytes = len(msg.encode("utf-8"))
        if msg_bytes > MAX_PACKET_BYTES:
            msg = _trim_to_bytes(msg, MAX_PACKET_BYTES)

        try:
            self.interface.sendText(
                msg,
                destinationId=destination,
                wantAck=True,
                channelIndex=self.config["channel"],
            )
        except Exception as e:
            logger.error("Send failed: %s", e)

    def _is_duplicate(self, packet_id: int, from_id: str) -> bool:
        """Check and record packet for deduplication."""
        key = (packet_id, from_id)
        now = time.time()

        # Evict stale entries
        while self._seen_packets:
            oldest_key, oldest_time = next(iter(self._seen_packets.items()))
            if now - oldest_time > DEDUP_TTL_SECONDS:
                self._seen_packets.pop(oldest_key)
            else:
                break

        if key in self._seen_packets:
            return True

        self._seen_packets[key] = now
        return False

    def _reconnect_loop(self) -> None:
        """Attempt to reconnect with exponential backoff."""
        for delay in RECONNECT_BACKOFF:
            logger.info("Reconnecting in %ds...", delay)
            time.sleep(delay)
            try:
                self.connect()
                logger.info("Reconnected successfully")
                return
            except Exception as e:
                logger.warning("Reconnect failed: %s", e)

        # Keep retrying at max backoff
        while self._running:
            delay = RECONNECT_BACKOFF[-1]
            logger.info("Reconnecting in %ds...", delay)
            time.sleep(delay)
            try:
                self.connect()
                logger.info("Reconnected successfully")
                return
            except Exception as e:
                logger.warning("Reconnect failed: %s", e)
