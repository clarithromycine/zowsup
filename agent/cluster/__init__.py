"""Agent Cluster module.

Provides the Router (transparent proxy) and agent-side auto-registration.

Usage:
    python -m agent.cluster --host 0.0.0.0 --port 8000
"""


def get_registry():
    from agent.cluster.registry import registry
    return registry


def create_router_app():
    from agent.cluster.router import create_router_app as _create
    return _create()
