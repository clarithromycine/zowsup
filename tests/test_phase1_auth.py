"""
Phase 1: Authentication tests.

Tests:
- TC-1.3.1: No-auth mode → health endpoint returns 200
- TC-1.3.2: Auth mode → agent starts normally
- TC-1.3.3: Auth mode → no key → 403
- TC-1.3.4: Auth mode → correct key → 200
- TC-1.3.5: Auth mode → wrong key → 403
"""

import pytest
import requests


class TestNoAuthMode:
    """Tests when agent is started without --accesskey."""

    @pytest.fixture(autouse=True)
    def setup(self, agent_noauth):
        self.base = agent_noauth

    def test_health_noauth(self):
        """TC-1.3.1: Health endpoint accessible without auth."""
        r = requests.get(f"{self.base}/api/health")
        assert r.status_code == 200
        assert r.json() ["status"] == "ok"

    def test_bots_list_noauth(self):
        """Bots list accessible without auth."""
        r = requests.get(f"{self.base}/api/listbot")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


class TestAuthMode:
    """Tests when agent is started with --accesskey."""

    @pytest.fixture(autouse=True)
    def setup(self, agent_auth):
        self.base, self.key = agent_auth

    def test_health_no_key_denied(self):
        """TC-1.3.3: No key → 403."""
        r = requests.get(f"{self.base}/api/health")
        assert r.status_code == 403

    def test_health_correct_key(self):
        """TC-1.3.4: Correct key → 200."""
        r = requests.get(
            f"{self.base}/api/health",
            headers={"X-Access-Key": self.key},
        )
        assert r.status_code == 200
        assert r.json() ["status"] == "ok"

    def test_health_wrong_key_denied(self):
        """TC-1.3.5: Wrong key → 403."""
        r = requests.get(
            f"{self.base}/api/health",
            headers={"X-Access-Key": "wrong-key"},
        )
        assert r.status_code == 403
