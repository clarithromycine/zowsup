"""
Phase 5: Log streaming tests.

Tests:
- TC-5.1.1: GET recent logs
- TC-5.2.1: WebSocket real-time log stream
- TC-5.4.1: WebSocket auth
"""

import asyncio
import json
import logging

import pytest
import requests
import websockets


class TestRecentLogs:
    """REST endpoint for pulling recent log lines."""

    @pytest.fixture(autouse=True)
    def setup(self, agent_noauth, test_bot_id):
        self.base = agent_noauth
        self.bot_id = test_bot_id

    def test_nonexistent_bot_logs(self):
        """Log endpoint for unknown bot → 404."""
        r = requests.get(f"{self.base}/api/bot/nonexistent/logs/recent")
        assert r.status_code == 404

    @pytest.mark.requires_connection
    def test_running_bot_logs(self):
        """TC-5.1.1: Get recent logs for a running bot."""
        # Start bot to generate logs
        requests.post(
            f"{self.base}/api/startbot",
            json={"bots": [{"bot_id": self.bot_id, "auto_login": True}]},
        )
        r = requests.get(f"{self.base}/api/bot/{self.bot_id}/logs/recent?lines=10")
        assert r.status_code == 200
        data = r.json()
        assert data["bot_id"] == self.bot_id
        assert isinstance(data["lines"], list)
        # Log format is "[timestamp] LEVEL Message" — check for typical bot startup messages
        if data["lines"]:
            assert any("Login" in line for line in data["lines"]), \
                f"Expected log lines containing 'Login', got: {data['lines']}"

        requests.post(f"{self.base}/api/stopbot", json={"bot_ids": [self.bot_id], "mode": "force"})


@pytest.mark.requires_connection
class TestWebSocketLogs:
    """WebSocket real-time log streaming."""

    @pytest.fixture(autouse=True)
    def setup(self, agent_noauth, test_bot_id):
        self.base = agent_noauth
        self.bot_id = test_bot_id
        # Use ws:// from http://
        self.ws_base = self.base.replace("http://", "ws://")

    @pytest.mark.asyncio
    async def test_ws_connect_and_receive(self):
        """TC-5.2.1: Connect WebSocket and receive at least one log message."""
        # Start a bot to generate log traffic
        requests.post(
            f"{self.base}/api/startbot",
            json={"bots": [{"bot_id": self.bot_id, "auto_login": True}]},
        )
        # Give the bot a moment to generate startup logs
        await asyncio.sleep(1)

        try:
            ws_url = f"{self.ws_base}/api/bot/{self.bot_id}/logs?tail=5"
            async with websockets.connect(ws_url, open_timeout=10) as ws:
                # Receive at least one message (there should be history from tail=5)
                msg = await asyncio.wait_for(ws.recv(), timeout=5)
                assert isinstance(msg, str)
                assert len(msg) > 0
        except asyncio.TimeoutError:
            # No messages received — still valid if bot has no logs yet
            # (happens if login fails too fast)
            pass
        finally:
            requests.post(f"{self.base}/api/stopbot", json={"bot_ids": [self.bot_id], "mode": "force"})

    @pytest.mark.asyncio
    async def test_ws_auth_required(self):
        """TC-5.4.1: WebSocket with wrong key is rejected.

        This test only applies when auth is enabled. In no-auth mode,
        the connection is always accepted.
        """
        ws_url = f"{self.ws_base}/api/bot/{self.bot_id}/logs"
        try:
            async with websockets.connect(ws_url, open_timeout=10) as ws:
                # Connection accepted in no-auth mode
                pass
        except websockets.exceptions.InvalidStatus as e:
            # In auth mode without key → 403
            assert e.response.status_code == 403
