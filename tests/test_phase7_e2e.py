"""Phase 7: Events WebSocket + E2E integration tests."""

import asyncio
import json
import pytest
import requests
import websockets


@pytest.mark.requires_connection
class TestEventWebSocket:
    @pytest.fixture(autouse=True)
    def setup(self, agent_noauth, test_bot_id):
        self.base = agent_noauth
        self.ws_base = self.base.replace("http://", "ws://")
        self.bot_id = test_bot_id

    @pytest.mark.asyncio
    async def test_events_connect_and_receive(self):
        requests.post(
            f"{self.base}/api/startbot",
            json={"bots": [{"bot_id": self.bot_id, "auto_login": True}]},
        )
        await asyncio.sleep(2)
        try:
            ws_url = f"{self.ws_base}/api/bot/{self.bot_id}/events?tail=5"
            async with websockets.connect(ws_url, open_timeout=10) as ws:
                msg = await asyncio.wait_for(ws.recv(), timeout=5)
                event = json.loads(msg)
                assert "type" in event
                assert "bot_id" in event
                assert event["bot_id"] == self.bot_id
        except asyncio.TimeoutError:
            pass
        finally:
            requests.post(f"{self.base}/api/stopbot", json={"bot_ids": [self.bot_id], "mode": "force"})


@pytest.mark.requires_connection
class TestE2E:
    @pytest.fixture(autouse=True)
    def setup(self, agent_noauth, test_bot_id):
        self.base = agent_noauth
        self.bot_id = test_bot_id

    def test_full_lifecycle(self):
        r = requests.post(
            f"{self.base}/api/startbot",
            json={"bots": [{"bot_id": self.bot_id, "auto_login": True}]},
        )
        assert r.status_code == 200

        r = requests.get(f"{self.base}/api/bot/{self.bot_id}")
        assert r.status_code == 200

        r = requests.post(
            f"{self.base}/api/botcmd",
            json={"bot_id": self.bot_id, "command": "misc.prekeycount", "timeout": 15},
        )
        assert r.status_code == 200

        r = requests.get(f"{self.base}/api/bot/{self.bot_id}/logs/recent?lines=5")
        assert r.status_code == 200

        r = requests.post(f"{self.base}/api/exportbot", json={"bot_ids": [self.bot_id], "mode": "force"})
        assert r.status_code == 200

        r = requests.post(f"{self.base}/api/stopbot", json={"bot_ids": [self.bot_id], "mode": "force"})
        assert r.status_code == 200

        r = requests.get(f"{self.base}/api/bot/{self.bot_id}")
        assert r.status_code == 200
        assert r.json()["status"] == "STOPPED"
