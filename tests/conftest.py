"""
Shared pytest fixtures for agent integration tests.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

import pytest
import requests

# Ensure project root on path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# ── Markers ──────────────────────────────────────────────────────────────────

def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "requires_connection: test requires a live WhatsApp connection (skip in CI with -m 'not requires_connection')"
    )

# ── Configuration ────────────────────────────────────────────────────────────

AGENT_PORT = int(os.environ.get("AGENT_TEST_PORT", "18990"))
AGENT_HOST = os.environ.get("AGENT_TEST_HOST", "127.0.0.1")
BASE_URL = f"http://{AGENT_HOST}:{AGENT_PORT}"

# Real account for integration tests
# Priority: env var → auto-discover from AccountStore → hardcoded default
_TEST_BOT_ID_ENV = os.environ.get("AGENT_TEST_BOT_ID", "")


def _discover_test_bot_id() -> str:
    """Auto-discover a test bot ID from AccountStore if env var not set."""
    if _TEST_BOT_ID_ENV:
        return _TEST_BOT_ID_ENV

    # Try the hardcoded default first (fast path, no DB needed)
    default = "233541115312"
    try:
        from agent.manager.account_store import account_store
        account_store._ensure_init()
        conn = account_store._get_conn()
        rows = conn.execute("SELECT bot_id FROM accounts LIMIT 1").fetchall()
        if rows:
            return rows[0][0]
    except Exception:
        pass
    return default


TEST_BOT_ID = _discover_test_bot_id()


def _wait_for_agent(base_url: str, timeout: float = 15.0) -> bool:
    """Poll /api/health until it responds or timeout expires."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(f"{base_url}/api/health", timeout=2)
            if r.status_code in (200, 403):
                # 403 is also valid — means agent is up but requires auth
                return True
        except requests.ConnectionError:
            pass
        time.sleep(0.5)
    return False


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def agent_noauth():
    """Start the agent in no-auth mode for the test session."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "agent", "--port", str(AGENT_PORT)],
        cwd=_project_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if not _wait_for_agent(BASE_URL):
        proc.terminate()
        proc.wait()
        pytest.fail("Agent failed to start within timeout")

    yield BASE_URL

    # Teardown
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture(scope="session")
def agent_auth():
    """Start the agent in auth mode for the test session."""
    auth_port = AGENT_PORT + 1
    auth_url = f"http://{AGENT_HOST}:{auth_port}"
    proc = subprocess.Popen(
        [sys.executable, "-m", "agent",
         "--port", str(auth_port),
         "--accesskey", "test-secret-key"],
        cwd=_project_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    if not _wait_for_agent(auth_url):
        proc.terminate()
        proc.wait()
        pytest.fail("Agent (auth) failed to start within timeout")

    yield auth_url, "test-secret-key"

    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture(scope="session")
def test_bot_id():
    """Return the bot ID to use for integration tests."""
    if not TEST_BOT_ID:
        pytest.skip("AGENT_TEST_BOT_ID not set — skipping integration tests")
    return TEST_BOT_ID
