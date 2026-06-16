"""Phase 2: Bot lifecycle tests."""

import pytest
import requests


class TestBotListEmpty:
    """Tests that don't require any running bots."""

    @pytest.fixture(autouse=True)
    def setup(self, agent_noauth, test_bot_id):
        self.base = agent_noauth
        self.bot_id = test_bot_id
        # Ensure clean state
        requests.post(f"{self.base}/api/stopbot", json={"bot_ids": [self.bot_id], "mode": "force"})

    def test_list_shows_available_accounts(self):
        """List returns all managed accounts (from AccountStore)."""
        r = requests.get(f"{self.base}/api/listbot")
        assert r.status_code == 200
        bots = r.json()
        assert isinstance(bots, list)
        assert any(b["bot_id"] == self.bot_id for b in bots), \
            f"Expected {self.bot_id} in bot list, got {[b['bot_id'] for b in bots]}"
        for b in bots:
            assert "bot_id" in b
            assert "status" in b

    def test_get_nonexistent(self):
        """Get nonexistent bot → 404."""
        r = requests.get(f"{self.base}/api/bot/nonexistent_bot_12345")
        assert r.status_code == 404

    def test_stop_nonexistent(self):
        """Stop nonexistent bot → 200 with error result."""
        r = requests.post(
            f"{self.base}/api/stopbot",
            json={"bot_ids": ["nonexistent_bot_12345"]},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["error_count"] == 1


@pytest.mark.requires_connection
class TestBotLifecycle:
    """Tests that require a real WhatsApp account."""

    @pytest.fixture(autouse=True)
    def setup(self, agent_noauth, test_bot_id):
        self.base = agent_noauth
        self.bot_id = test_bot_id
        requests.post(f"{self.base}/api/stopbot", json={"bot_ids": [self.bot_id], "mode": "force"})
        yield
        requests.post(f"{self.base}/api/stopbot", json={"bot_ids": [self.bot_id], "mode": "force"})

    def test_start_bot(self):
        """Start a bot via batch API."""
        r = requests.post(
            f"{self.base}/api/startbot",
            json={"bots": [{"bot_id": self.bot_id, "auto_login": True}]},
        )
        assert r.status_code == 200, f"Start failed: {r.text}"
        data = r.json()
        assert data["success_count"] >= 1
        assert len(data["results"]) == 1
        assert data["results"][0]["bot_id"] == self.bot_id

    def test_list_after_start(self):
        """List shows the started bot."""
        requests.post(
            f"{self.base}/api/startbot",
            json={"bots": [{"bot_id": self.bot_id, "auto_login": True}]},
        )
        r = requests.get(f"{self.base}/api/listbot")
        assert r.status_code == 200
        bots = r.json()
        assert any(b["bot_id"] == self.bot_id for b in bots)

    def test_get_bot(self):
        """GET /api/bot/{id} returns info."""
        requests.post(
            f"{self.base}/api/startbot",
            json={"bots": [{"bot_id": self.bot_id, "auto_login": True}]},
        )
        r = requests.get(f"{self.base}/api/bot/{self.bot_id}")
        assert r.status_code == 200
        assert r.json()["bot_id"] == self.bot_id

    def test_duplicate_start(self):
        """Starting a still-running bot is safe."""
        requests.post(
            f"{self.base}/api/startbot",
            json={"bots": [{"bot_id": self.bot_id, "auto_login": True}]},
        )
        r = requests.post(
            f"{self.base}/api/startbot",
            json={"bots": [{"bot_id": self.bot_id, "auto_login": True}]},
        )
        assert r.status_code == 200

    def test_stop_bot(self):
        """Stop a bot via batch API."""
        requests.post(
            f"{self.base}/api/startbot",
            json={"bots": [{"bot_id": self.bot_id, "auto_login": True}]},
        )
        r = requests.post(f"{self.base}/api/stopbot", json={"bot_ids": [self.bot_id], "mode": "force"})
        assert r.status_code == 200
        assert r.json()["success_count"] >= 1
