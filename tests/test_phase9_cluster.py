"""Phase 9: Cluster — Registry, Router, Escalation, Plugin Sync tests.

Covers:
- Registry CRUD: register / heartbeat / unregister / resolve_bot / pick_agent / TTL
- Router HTTP: cluster_secret auth, agent management endpoints
- Escalation (centralized): create / claim / unclaim / resolve
- Plugin sync: export_all / import_from
"""

import time
import os
import subprocess
import sys

import pytest
import requests


# ═══════════════════════════════════════════════════════════════════════════════
# Registry unit tests (in-memory, no process needed)
# ═══════════════════════════════════════════════════════════════════════════════

class TestRegistry:
    """Unit tests for the Registry (SQLite in-memory)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from agent.cluster.registry import Registry
        self.reg = Registry(":memory:")
        self.reg.start()
        # Reset TTL to a small value for testing
        self.reg.AGENT_TTL_SECONDS = 2

    def test_register_agent(self):
        agent = self.reg.register_agent("agent-1", "http://127.0.0.1:9001")
        assert agent["agent_id"] == "agent-1"
        assert agent["url"] == "http://127.0.0.1:9001"
        assert agent["status"] == "online"

    def test_register_is_idempotent(self):
        self.reg.register_agent("agent-1", "http://127.0.0.1:9001")
        self.reg.register_agent("agent-1", "http://127.0.0.1:9002")  # new URL
        agent = self.reg.get_agent("agent-1")
        assert agent["url"] == "http://127.0.0.1:9002"
        # Should still be only 1 agent
        assert len(self.reg.list_agents()) == 1

    def test_unregister_agent(self):
        self.reg.register_agent("agent-1", "http://127.0.0.1:9001")
        assert self.reg.unregister_agent("agent-1") is True
        assert self.reg.get_agent("agent-1") is None
        # Idempotent: second unregister returns False
        assert self.reg.unregister_agent("agent-1") is False

    def test_unregister_cascades_bot_routes(self):
        self.reg.register_agent("agent-1", "http://127.0.0.1:9001")
        self.reg.route_bot("bot-a", "agent-1")
        self.reg.route_bot("bot-b", "agent-1")
        self.reg.unregister_agent("agent-1")
        assert self.reg.resolve_bot("bot-a") is None
        assert self.reg.resolve_bot("bot-b") is None
        assert self.reg.list_bot_routes() == []

    def test_heartbeat(self):
        self.reg.register_agent("agent-1", "http://127.0.0.1:9001")
        assert self.reg.heartbeat("agent-1") is True
        assert self.reg.heartbeat("nonexistent") is False

    def test_resolve_bot(self):
        self.reg.register_agent("agent-1", "http://127.0.0.1:9001")
        self.reg.route_bot("bot-x", "agent-1")
        route = self.reg.resolve_bot("bot-x")
        assert route is not None
        assert route["agent_id"] == "agent-1"
        assert route["url"] == "http://127.0.0.1:9001"
        assert self.reg.resolve_bot("nonexistent") is None

    def test_pick_agent_least_bots(self):
        self.reg.register_agent("agent-1", "http://127.0.0.1:9001")
        self.reg.register_agent("agent-2", "http://127.0.0.1:9002")
        self.reg.route_bot("bot-a", "agent-1")
        self.reg.route_bot("bot-b", "agent-1")
        self.reg.route_bot("bot-c", "agent-2")
        picked = self.reg.pick_agent()
        assert picked is not None
        assert picked["agent_id"] == "agent-2"  # 1 bot vs 2 bots

    def test_pick_agent_excludes_offline(self):
        self.reg.register_agent("agent-1", "http://127.0.0.1:9001")
        self.reg.mark_offline("agent-1")
        assert self.reg.pick_agent() is None

    def test_ttl_expires_stale_agents(self):
        """Agent with heartbeat older than TTL is auto-marked offline on list."""
        self.reg.register_agent("agent-1", "http://127.0.0.1:9001")
        # Manually set last_heartbeat to TTL+1 seconds ago
        conn = self.reg._get_conn()
        conn.execute(
            "UPDATE agents SET last_heartbeat = ? WHERE agent_id = ?",
            (time.time() - 3, "agent-1"),  # TTL is 2
        )
        conn.commit()
        agents = self.reg.list_agents()
        assert agents[0]["status"] == "offline"
        # pick_agent also excludes it
        assert self.reg.pick_agent() is None

    def test_ttl_heartbeat_keeps_alive(self):
        """Fresh heartbeat prevents TTL expiry."""
        self.reg.register_agent("agent-1", "http://127.0.0.1:9001")
        self.reg.heartbeat("agent-1")  # refreshes timestamp
        agents = self.reg.list_agents()
        assert agents[0]["status"] == "online"

    def test_ttl_re_register_reactivates(self):
        """Re-registering a TTL-expired agent brings it back online."""
        self.reg.register_agent("agent-1", "http://127.0.0.1:9001")
        conn = self.reg._get_conn()
        conn.execute("UPDATE agents SET last_heartbeat = ? WHERE agent_id = ?", (time.time() - 3, "agent-1"))
        conn.commit()
        self.reg.list_agents()  # triggers expiry
        assert self.reg.get_agent("agent-1")["status"] == "offline"
        # Re-register
        self.reg.register_agent("agent-1", "http://127.0.0.1:9001")
        assert self.reg.get_agent("agent-1")["status"] == "online"

    def test_route_bot_overwrite(self):
        """Routing a bot to a new agent overwrites previous route."""
        self.reg.register_agent("agent-1", "http://127.0.0.1:9001")
        self.reg.register_agent("agent-2", "http://127.0.0.1:9002")
        self.reg.route_bot("bot-x", "agent-1")
        self.reg.route_bot("bot-x", "agent-2")
        assert self.reg.get_agent_for_bot("bot-x") == "agent-2"

    def test_list_bot_routes_filtered(self):
        self.reg.register_agent("agent-1", "http://127.0.0.1:9001")
        self.reg.register_agent("agent-2", "http://127.0.0.1:9002")
        self.reg.route_bot("bot-a", "agent-1")
        self.reg.route_bot("bot-b", "agent-2")
        assert len(self.reg.list_bot_routes("agent-1")) == 1
        assert len(self.reg.list_bot_routes()) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# Cluster HTTP integration tests
# ═══════════════════════════════════════════════════════════════════════════════

CLUSTER_PORT = 18998
CLUSTER_SECRET = "test-cluster-secret-phase9"


@pytest.fixture(scope="module")
def cluster():
    """Start the cluster process for the test module."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "agent.cluster",
         "--port", str(CLUSTER_PORT),
         "--cluster-secret", CLUSTER_SECRET],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    time.sleep(2)
    yield f"http://127.0.0.1:{CLUSTER_PORT}"
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def _h():
    """Auth headers for cluster requests."""
    return {"X-Cluster-Secret": CLUSTER_SECRET}


class TestClusterAuth:
    """Security: cluster secret enforcement on management endpoints."""

    def test_agents_without_secret_403(self, cluster):
        r = requests.get(f"{cluster}/api/cluster/agents")
        assert r.status_code == 403

    def test_agents_with_wrong_secret_403(self, cluster):
        r = requests.get(f"{cluster}/api/cluster/agents", headers={"X-Cluster-Secret": "wrong"})
        assert r.status_code == 403

    def test_agents_with_correct_secret_200(self, cluster):
        r = requests.get(f"{cluster}/api/cluster/agents", headers=_h())
        assert r.status_code == 200

    def test_register_without_secret_403(self, cluster):
        r = requests.post(f"{cluster}/api/cluster/agents", json={"agent_id": "evil", "url": "http://evil:666"})
        assert r.status_code == 403

    def test_health_no_auth_required(self, cluster):
        r = requests.get(f"{cluster}/api/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestClusterAgentMgmt:
    """Agent lifecycle: register → heartbeat → deregister."""

    def test_register_and_list(self, cluster):
        r = requests.post(f"{cluster}/api/cluster/agents", json={
            "agent_id": "test-agent", "url": "http://127.0.0.1:9001", "bots": ["bot-1"]
        }, headers=_h())
        assert r.status_code == 200
        agent = r.json()
        assert agent["agent_id"] == "test-agent"
        assert agent["status"] == "online"

        # Verify appears in list
        r2 = requests.get(f"{cluster}/api/cluster/agents", headers=_h())
        agents = r2.json()
        assert any(a["agent_id"] == "test-agent" for a in agents)

    def test_heartbeat_updates_timestamp(self, cluster):
        r = requests.post(f"{cluster}/api/cluster/agents/test-agent/heartbeat",
                          json={"bots": ["bot-1", "bot-2"]}, headers=_h())
        assert r.status_code == 200
        # Registered bots should appear in agent list
        r2 = requests.get(f"{cluster}/api/cluster/agents", headers=_h())
        for a in r2.json():
            if a["agent_id"] == "test-agent":
                assert "bot-1" in a["bots"]

    def test_register_is_idempotent(self, cluster):
        r = requests.post(f"{cluster}/api/cluster/agents", json={
            "agent_id": "test-agent", "url": "http://127.0.0.1:9002"
        }, headers=_h())
        assert r.status_code == 200
        assert r.json()["url"] == "http://127.0.0.1:9002"

    def test_deregister(self, cluster):
        r = requests.delete(f"{cluster}/api/cluster/agents/test-agent", headers=_h())
        assert r.status_code == 200
        # Should not appear anymore
        r2 = requests.get(f"{cluster}/api/cluster/agents", headers=_h())
        assert not any(a["agent_id"] == "test-agent" for a in r2.json())

    def test_deregister_nonexistent_404(self, cluster):
        r = requests.delete(f"{cluster}/api/cluster/agents/nonexistent", headers=_h())
        assert r.status_code == 404

    def test_heartbeat_nonexistent_404(self, cluster):
        r = requests.post(f"{cluster}/api/cluster/agents/nonexistent/heartbeat",
                          json={}, headers=_h())
        assert r.status_code == 404


class TestClusterMigrate:
    """Migration endpoint validation (not the actual migration flow)."""

    def test_migrate_missing_fields_400(self, cluster):
        r = requests.post(f"{cluster}/api/cluster/migrate", json={}, headers=_h())
        assert r.status_code == 400

    def test_migrate_nonexistent_bot_404(self, cluster):
        r = requests.post(f"{cluster}/api/cluster/migrate", json={
            "bot_id": "nonexistent", "target_agent": "any"
        }, headers=_h())
        assert r.status_code == 404

    def test_migrate_same_agent_400(self, cluster):
        # Register agent with a bot
        requests.post(f"{cluster}/api/cluster/agents", json={
            "agent_id": "mig-src", "url": "http://127.0.0.1:9001", "bots": ["mig-bot"]
        }, headers=_h())
        r = requests.post(f"{cluster}/api/cluster/migrate", json={
            "bot_id": "mig-bot", "target_agent": "mig-src"
        }, headers=_h())
        assert r.status_code == 400  # same agent

    def test_migrate_nonexistent_target_404(self, cluster):
        r = requests.post(f"{cluster}/api/cluster/migrate", json={
            "bot_id": "mig-bot", "target_agent": "nonexistent"
        }, headers=_h())
        assert r.status_code == 404

    def test_migrate_without_secret_403(self, cluster):
        r = requests.post(f"{cluster}/api/cluster/migrate", json={
            "bot_id": "x", "target_agent": "y"
        })
        assert r.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════════
# Escalation queue unit tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestEscalationQueue:
    """Unit tests for the centralized EscalationQueue."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from agent.manager.escalation_queue import EscalationQueue
        self.queue = EscalationQueue(":memory:")
        self.queue.start()

    def test_add_escalation(self):
        esc = self.queue.add(
            bot_id="bot-1", conversation_id="bot-1:user@s.whatsapp.net",
            reason="User needs help", priority="high",
        )
        assert esc["id"]  # UUID generated
        assert esc["bot_id"] == "bot-1"
        assert esc["status"] == "pending"
        assert esc["priority"] == "high"
        assert esc["reason"] == "User needs help"

    def test_add_is_idempotent_by_pending(self):
        """Adding same conversation_id+pending returns existing escalation."""
        e1 = self.queue.add(bot_id="bot-1", conversation_id="conv-1", reason="First")
        e2 = self.queue.add(bot_id="bot-1", conversation_id="conv-1", reason="Updated")
        assert e1["id"] == e2["id"]
        assert e2["reason"] == "Updated"

    def test_list_filters(self):
        self.queue.add(bot_id="bot-1", conversation_id="conv-1", reason="A")
        self.queue.add(bot_id="bot-2", conversation_id="conv-2", reason="B")
        # Default: all non-resolved
        assert len(self.queue.list()) == 2
        # By bot
        assert len(self.queue.list(bot_id="bot-1")) == 1
        assert len(self.queue.list(bot_id="bot-2")) == 1

    def test_claim_and_unclaim(self):
        esc = self.queue.add(bot_id="bot-1", conversation_id="conv-1")
        assert self.queue.claim(esc["id"], "operator-1") is True
        item = self.queue.get(esc["id"])
        assert item["status"] == "claimed"
        assert item["claimed_by"] == "operator-1"

        # Cannot claim again
        assert self.queue.claim(esc["id"], "operator-2") is False

        # Unclaim
        assert self.queue.unclaim(esc["id"]) is True
        item = self.queue.get(esc["id"])
        assert item["status"] == "pending"

    def test_resolve(self):
        esc = self.queue.add(bot_id="bot-1", conversation_id="conv-1")
        assert self.queue.resolve(esc["id"]) is True
        item = self.queue.get(esc["id"])
        assert item["status"] == "resolved"
        # Resolved escalations are excluded from default list()
        assert len(self.queue.list()) == 0

    def test_resolve_nonexistent(self):
        assert self.queue.resolve("nonexistent") is False

    def test_claim_nonexistent(self):
        assert self.queue.claim("nonexistent", "op") is False

    def test_unclaim_nonexistent(self):
        assert self.queue.unclaim("nonexistent") is False

    def test_is_claimed(self):
        esc = self.queue.add(bot_id="bot-1", conversation_id="conv-1")
        assert self.queue.is_claimed("conv-1") is False
        self.queue.claim(esc["id"], "op")
        assert self.queue.is_claimed("conv-1") is True

    def test_get_nonexistent(self):
        assert self.queue.get("nonexistent") is None


# ═══════════════════════════════════════════════════════════════════════════════
# Plugin sync unit tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestPluginSync:
    """Unit tests for PluginStore export/import (cluster sync)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from agent.plugin.store import PluginStore
        self.store = PluginStore(":memory:")
        self.store.start()

    def test_export_all_empty(self):
        rows = self.store.export_all()
        assert rows == []

    def test_export_all_after_config(self):
        self.store.set_config("translation", {"work_lang": "zh"})
        self.store.set_enabled("translation", True)
        rows = self.store.export_all()
        assert len(rows) == 1
        assert rows[0]["plugin_name"] == "translation"
        assert rows[0]["enabled"] == 1

    def test_import_from_merges(self):
        self.store.set_config("ai", {"model": "gpt-4"})
        # Import from "cluster"
        self.store.import_from([
            {"bot_id": "", "plugin_name": "ai", "enabled": 0, "config_json": '{"model":"gpt-5"}', "updated_at": 999},
            {"bot_id": "", "plugin_name": "translation", "enabled": 1, "config_json": '{"work_lang":"en"}', "updated_at": 888},
        ])
        # ai should be disabled now
        assert self.store.is_enabled("ai") is False
        # translation should be enabled
        assert self.store.is_enabled("translation") is True
        # ai config should be overridden
        assert self.store.get_config("ai")["model"] == "gpt-5"
