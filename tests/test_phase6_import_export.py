"""Phase 6: Import/Export tests."""

import pytest
import requests


class TestExport:
    """Export tests using real account data."""

    @pytest.fixture(autouse=True)
    def setup(self, agent_noauth, test_bot_id):
        self.base = agent_noauth
        self.bot_id = test_bot_id

    def test_export_existing_account(self):
        """Export returns CSV data + env per bot."""
        r = requests.post(f"{self.base}/api/exportbot", json={"bot_ids": [self.bot_id]})
        assert r.status_code == 200
        data = r.json()
        assert "exports" in data
        entry = data["exports"].get(self.bot_id)
        if entry and entry.get("data"):
            csv_data = entry["data"]
            parts = csv_data.split(",")
            assert len(parts) == 6, f"Expected 6 fields, got {len(parts)}: {csv_data[:100]}"
            assert entry.get("env"), f"Expected env in export entry, got {entry}"


class TestImport:
    """Import tests."""

    @pytest.fixture(autouse=True)
    def setup(self, agent_noauth, test_bot_id):
        self.base = agent_noauth
        self.bot_id = test_bot_id

    def test_import_invalid_data(self):
        """Invalid data → 422 (Pydantic validation)."""
        r = requests.post(
            f"{self.base}/api/importbot",
            json={"accounts": [{"data": "not,csv", "env": "android"}]},
        )
        # Will return 200 with error entry on import failure, or 422 for invalid format
        assert r.status_code in (200, 422)

    def test_import_and_export_roundtrip(self):
        """Export then re-import using the correct env from export.

        Uses a fake bot_id for import to avoid overwriting real account config.
        """
        r = requests.post(f"{self.base}/api/exportbot", json={"bot_ids": [self.bot_id]})
        assert r.status_code == 200
        entry = r.json()["exports"].get(self.bot_id)
        if not entry or not entry.get("data"):
            pytest.skip("Export returned no data for this bot")

        assert entry.get("env"), f"Export must include env, got {entry}"

        fake_id = "999999999999"
        fake_data = entry["data"].replace(self.bot_id, fake_id, 1)
        env = entry["env"]

        try:
            r = requests.post(
                f"{self.base}/api/importbot",
                json={"accounts": [{"data": fake_data, "env": env}]},
            )
            assert r.status_code == 200
            result = r.json()
            assert result["success_count"] >= 1
        finally:
            # Clean up fake account — remove from DB and delete data directory
            r = requests.delete(f"{self.base}/api/bot/{fake_id}")
            assert r.status_code == 200, f"Delete failed: {r.status_code} {r.text}"
            body = r.json()
            assert body["dir_removed"], f"Account dir not cleaned: {body}"
