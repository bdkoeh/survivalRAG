#!/usr/bin/env python3
"""SurvivalRAG Meshtastic Bridge -- mesh radio interface for the survival knowledge base.

Listens for text messages on a Meshtastic mesh network and responds with
RAG-generated answers split across multiple radio messages. Designed for
headless operation on a Raspberry Pi or similar device connected to a
Meshtastic radio via USB.

Usage:
    # Ensure meshtastic package is installed:
    pip install meshtastic>=2.7.0

    # Start with defaults (serial auto-detect, channel 0, trigger '?'):
    python meshtastic_main.py

    # Or configure via environment variables:
    MESHTASTIC_CONNECTION=serial:/dev/ttyACM0 python meshtastic_main.py
    MESHTASTIC_CONNECTION=tcp://192.168.1.100 python meshtastic_main.py

Configuration:
    All settings via MESHTASTIC_* environment variables.
    See .env.example for the full list.
"""

import logging
import signal
import sys

import pipeline.retrieve as retrieve
import pipeline.generate as gen
from pipeline.meshtastic_bridge import MeshtasticBridge, load_config

logger = logging.getLogger(__name__)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    config = load_config()
    if not config["enabled"]:
        logger.error(
            "Meshtastic bridge is disabled. Set MESHTASTIC_ENABLED=true to start."
        )
        sys.exit(1)

    # Initialize RAG pipeline
    logger.info("Initializing retrieval engine...")
    try:
        retrieve.init(chroma_path="./data/chroma")
        gen.init()
    except ConnectionError:
        logger.error("Ollama is not running. Start with: ollama serve")
        sys.exit(1)
    except RuntimeError as e:
        logger.error("Pipeline initialization failed: %s", e)
        sys.exit(1)

    logger.info("Pipeline ready. Connecting to Meshtastic radio...")

    bridge = MeshtasticBridge(config)

    # Handle SIGTERM for clean Docker shutdown
    def _shutdown(signum, frame):
        logger.info("Received signal %d, shutting down...", signum)
        bridge.disconnect()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    try:
        bridge.connect()
        bridge.run()
    except ImportError as e:
        logger.error("%s", e)
        sys.exit(1)
    except Exception as e:
        logger.error("Fatal error: %s", e, exc_info=True)
        bridge.disconnect()
        sys.exit(1)


if __name__ == "__main__":
    main()
