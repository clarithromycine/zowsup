"""Entry point for the Router process.

Usage:
    python -m agent.cluster --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Zowsup Cluster")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)

    # Ensure config is loaded so SysVar.ACCOUNT_PATH etc. are available
    import os, sys
    _project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)

    from conf.constants import SysVar
    SysVar.loadConfig()

    from agent.cluster.router import create_cluster_app
    import uvicorn

    app = create_cluster_app()
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main(sys.argv[1:])
