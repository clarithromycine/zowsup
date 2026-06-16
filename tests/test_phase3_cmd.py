"""Phase 3: Command execution tests."""

import pytest
import requests


class TestCmdEdgeCases:
    """Tests that don't require a running bot."""

    @pytest.fixture(autouse=True)
    def setup(self, agent_noauth):
        self.base = agent_noauth

    def test_cmd_nonexistent_bot(self):
        """Execute on nonexistent bot → 404."""
        r = requests.post(
            f"{self.base}/api/botcmd",
            json={"bot_id": "nonexistent_bot", "command": "msg.send", "args": ["123", "hi"], "timeout": 5},
        )
        assert r.status_code == 404

    def test_cmd_missing_field(self):
        """Empty body → 422 (Pydantic validation)."""
        r = requests.post(f"{self.base}/api/botcmd", json={})
        assert r.status_code == 422


@pytest.mark.requires_connection
class TestCmdOnRunningBot:
    """Tests requiring a real running bot."""

    @pytest.fixture(autouse=True)
    def setup(self, agent_noauth, test_bot_id):
        self.base = agent_noauth
        self.bot_id = test_bot_id
        requests.post(
            f"{self.base}/api/startbot",
            json={"bots": [{"bot_id": self.bot_id, "auto_login": True}]},
        )
        yield
        requests.post(f"{self.base}/api/stopbot", json={"bot_ids": [self.bot_id], "mode": "force"})

    def test_execute_valid_command(self):
        """Execute a valid command and get result."""
        r = requests.post(
            f"{self.base}/api/botcmd",
            json={"bot_id": self.bot_id, "command": "misc.prekeycount", "timeout": 30},
        )
        assert r.status_code == 200
        data = r.json()
        assert "retcode" in data


class TestSendMsg:
    """Tests for /api/sendmsg endpoint."""

    @pytest.fixture(autouse=True)
    def setup(self, agent_noauth, test_bot_id):
        self.base = agent_noauth
        self.bot_id = test_bot_id

    def test_sendmsg_nonexistent_bot(self):
        """Send to nonexistent bot → 404."""
        r = requests.post(
            f"{self.base}/api/sendmsg",
            json={"bot_id": "nonexistent", "to": "123@s.whatsapp.net", "content": {"text": "hi"}},
        )
        assert r.status_code == 404

    def test_sendmsg_empty_content(self):
        """No text or ad → 422."""
        r = requests.post(
            f"{self.base}/api/sendmsg",
            json={"bot_id": self.bot_id, "to": "123@s.whatsapp.net", "content": {}},
        )
        assert r.status_code == 422

    def test_sendmsg_media_invalid_type(self):
        """Invalid media type → 422."""
        r = requests.post(
            f"{self.base}/api/sendmsg",
            json={"bot_id": self.bot_id, "to": "123@s.whatsapp.net",
                  "content": {"media": {"type": "invalid", "url": "http://x"}}},
        )
        assert r.status_code == 422

    def test_sendmsg_media_no_source(self):
        """Media with no url/base64/path → 422."""
        r = requests.post(
            f"{self.base}/api/sendmsg",
            json={"bot_id": self.bot_id, "to": "123@s.whatsapp.net",
                  "content": {"media": {"type": "image"}}},
        )
        assert r.status_code == 422

    def test_sendmsg_media_url_valid(self):
        """Media with URL is accepted (returns cmd error if bot not running)."""
        r = requests.post(
            f"{self.base}/api/sendmsg",
            json={"bot_id": self.bot_id, "to": "123@s.whatsapp.net",
                  "content": {"media": {"type": "image", "url": "https://example.com/img.jpg"}}},
        )
        assert r.status_code == 200
        assert r.json()["retcode"] != 0  # bot not running → cmd error
