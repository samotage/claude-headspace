#!/usr/bin/env python3
"""Entry point for running Claude Headspace Flask server.

Reads configuration from config.yaml and starts the server with the
configured host, port, and debug settings.
"""

import sys
from pathlib import Path

# Add src to path so we can import without installing
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from claude_headspace.app import create_app
from claude_headspace.config import load_config, get_value


def main():
    # Load configuration
    config_path = Path(__file__).parent / "config.yaml"
    config = load_config(config_path)

    # Get server settings
    host = get_value(config, "server", "host", default="127.0.0.1")
    port = get_value(config, "server", "port", default=5050)
    debug = get_value(config, "server", "debug", default=False)

    # Create and run the app
    app = create_app(str(config_path))
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main()
