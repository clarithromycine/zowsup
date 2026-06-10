"""WebSocket log viewer with auto-reconnect.

Usage:
    python tools/wslog.py <bot_id> [--host HOST] [--port PORT] [--tail N]
    python tools/wslog.py 263783604300
    python tools/wslog.py 263783604300 --host 192.168.1.100 --port 8000 --tail 50
"""

import asyncio
import sys
import os

# Ensure project root on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import websockets


async def connect_loop(url: str, retry_delay: float = 3.0):
    """Connect to WebSocket and keep reconnecting on failure."""
    while True:
        try:
            async with websockets.connect(url, ping_interval=20) as ws:
                print(f"[connected] {url}")
                async for msg in ws:
                    print(msg)
        except (websockets.ConnectionClosed, OSError, asyncio.TimeoutError) as e:
            print(f"[disconnected] {e}")
        except KeyboardInterrupt:
            print("\n[exit]")
            return
        print(f"[reconnecting in {retry_delay}s...]")
        await asyncio.sleep(retry_delay)


def main():
    parser = argparse.ArgumentParser(description="WebSocket log viewer with auto-reconnect")
    parser.add_argument("bot_id", help="Bot ID to watch")
    parser.add_argument("--host", default="localhost", help="Agent host (default: localhost)")
    parser.add_argument("--port", type=int, default=8000, help="Agent port (default: 8000)")
    parser.add_argument("--tail", type=int, default=50, help="Recent lines to fetch on connect")
    parser.add_argument("--events", action="store_true", help="Watch events instead of logs")
    parser.add_argument("--accesskey", default=None, help="Access key for auth")
    args = parser.parse_args()

    ws_path = "events" if args.events else "logs"
    url = f"ws://{args.host}:{args.port}/api/bots/{args.bot_id}/{ws_path}?tail={args.tail}"
    if args.accesskey:
        url += f"&access_key={args.accesskey}"

    print(f"[wslog] connecting to {url}")
    asyncio.run(connect_loop(url))


if __name__ == "__main__":
    main()
