"""
Entry point for the Zowsup Agent.

Usage:
    python -m agent [--accesskey KEY] [--host HOST] [--port PORT]

Examples:
    python -m agent                              # No auth, port 8000
    python -m agent --accesskey my-secret-key    # Auth required
    python -m agent --host 127.0.0.1 --port 9090
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

# Ensure project root is on path *before* any config loading
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Zowsup Agent — Multi-bot WhatsApp protocol management service",
    )
    parser.add_argument(
        "--accesskey",
        type=str,
        default=None,
        help="Access key for API authentication (omit for no-auth debug mode)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind (default: 8000)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    # Load system config first
    from conf.constants import SysVar
    SysVar.loadConfig()

    # Initialize logging (same path as script/main.py)
    from common.utils import Utils
    Utils.init_log(logging.INFO, "agent.log")

    # Configure agent access key
    from agent.server import set_access_key, create_app
    set_access_key(args.accesskey)

    if args.accesskey:
        print(f"[Agent] Access key configured: {'*' * len(args.accesskey)}")
    else:
        print("[Agent] ⚠️  No access key set — API is open (debug mode)")

    app = create_app()

    import uvicorn
    import asyncio
    import signal
    
    config = uvicorn.Config(app, host=args.host, port=args.port, log_level="info")
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None

    async def _async_shutdown():
        from agent.manager.bot_manager import bot_manager
        from agent.manager.log_broadcaster import log_broadcaster

        for info in bot_manager.list_bots():
            bot = bot_manager.get_bot_instance(info.bot_id)
            if bot:
                try: bot.quit()
                except Exception: pass

        print("[Agent] Waiting for bots to shut down...")
        await asyncio.sleep(3)

        bot_manager.stop_periodic_flush()
        log_broadcaster._shutting_down = True
        log_broadcaster.stop()
        server.should_exit = True
    _shutting_down = False

    def _on_signal(signum, frame):
        nonlocal _shutting_down
        if _shutting_down:
            return
        _shutting_down = True
        asyncio.get_event_loop().create_task(_async_shutdown())

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    asyncio.run(server.serve())


if __name__ == "__main__":
    main()
