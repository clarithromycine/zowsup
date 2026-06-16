"""Entry point for the Router process.

Usage:
    python -m agent.cluster --host 0.0.0.0 --port 8000 [--cluster-secret SECRET]
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Zowsup Cluster")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--cluster-secret", default=None, help="Shared secret for agent authentication")
    parser.add_argument("--console-token", default=None, help="Optional bearer token for web console access")
    args = parser.parse_args(argv)

    # Ensure config is loaded so SysVar.ACCOUNT_PATH etc. are available
    import os, sys
    _project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)

    from conf.constants import SysVar
    SysVar.loadConfig()

    from agent.cluster.router import create_cluster_app, set_cluster_secret, set_console_token
    import uvicorn

    if args.cluster_secret:
        set_cluster_secret(args.cluster_secret)
    if args.console_token:
        set_console_token(args.console_token)

    app = create_cluster_app()
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main(sys.argv[1:])
