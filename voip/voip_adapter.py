

from __future__ import annotations

import asyncio
import logging
from typing import Optional, Callable

from .call.call_manager import CallManager, CallError
from .call.call_state import CallInfo, CallState, EndReason
from .bridge import BrowserBridge

log = logging.getLogger(__name__)


class VoipAdapter:


    # ── Singleton ──────────────────────────────────────────────

    _instance: Optional["VoipAdapter"] = None

    @classmethod
    def get(cls) -> "VoipAdapter":
        if cls._instance is None:
            cls._instance = VoipAdapter()
        return cls._instance

    # ── Lifecycle ──────────────────────────────────────────────

    def __init__(self):
        self._managers: dict[str, CallManager] = {}   # bot_id → CallManager
        self._bridges: dict[str, BrowserBridge] = {}   # call_id → BrowserBridge
        self._bot_contexts: dict[str, dict] = {}       # bot_id → context dict (send_query, send_node, send_iq, own_jid, db, ...)
        self._started = False

        # Event bus for browser SSE/WebSocket notifications
        self._event_listeners: list[Callable[[str, dict], None]] = []

    def start(self):
        """Initialize the adapter."""
        self._started = True
        log.info("VoipAdapter started")

    def stop(self):
        """Shutdown all calls and cleanup."""
        self._started = False
        for mgr in self._managers.values():
            try:
                asyncio.ensure_future(mgr.close())
            except Exception:
                pass
        self._managers.clear()
        self._bridges.clear()
        log.info("VoipAdapter stopped")

    # ── Bot/Socket registration ────────────────────────────────

    def register_bot(self, bot_id: str, bot):
        """Register a bot with the VoIP adapter. Extracts signaling hooks from the bot."""
        self._bot_contexts[bot_id] = bot

        self._get_manager(bot_id,bot)  # ensure CallManager exists and is wired, 第一次进入才会把bot传进去，后面调用直接bot留空，通过botId获取manager对象，里面有保存bot上下文

    def unregister_bot(self, bot_id: str):
        """Unregister a bot and cleanup its CallManager."""
        self._bot_contexts.pop(bot_id, None)
        mgr = self._managers.pop(bot_id, None)
        if mgr:
            try:
                asyncio.ensure_future(mgr.close())
            except Exception:
                pass

    def _get_manager(self, bot_id: str, bot=None) -> CallManager:
        """Get or create a CallManager for a bot. Always updates socket hooks."""
        if bot_id not in self._managers:
            mgr = CallManager(bot)
            mgr.on_state_change = lambda session, info, bid=bot_id: self._on_call_state(bid, session, info)
            mgr.on_incoming = lambda session, info, bid=bot_id: self._on_incoming_call(bid, session, info)
            mgr.on_ended = lambda session, info, bid=bot_id: self._on_call_ended(bid, session, info)
            mgr.on_peer_audio = lambda session, pcm, bid=bot_id: self._on_peer_audio(bid, session, pcm)            
            self._managers[bot_id] = mgr

        return self._managers[bot_id]    
    # ── Call control API ───────────────────────────────────────
    
    async def start_call(self, bot_id: str, peer_jid: str, is_video: bool = False) -> dict:

        mgr = self._get_manager(bot_id)
        try:            
            call_id = await mgr.start_call(peer_jid, is_video)
            return {"call_id": call_id, "state": mgr.current_call.state.value}
        except CallError as e:
            return {"error": str(e)}

    async def accept_call(self, bot_id: str, call_id: str = None) -> dict:
        """
        Accept the current incoming call.

        Returns: {"call_id": "...", "state": "..."}
        """
        mgr = self._managers.get(bot_id)
        if not mgr:
            return {"error": "No CallManager for this bot"}
        try:
            await mgr.accept_call(call_id)
            call = mgr.get_call(call_id) if call_id else mgr.current_call
            if call:
                return {"call_id": call.call_id, "state": call.state.value}
            return {"call_id": call_id or "", "state": "unknown"}
        except CallError as e:
            return {"error": str(e)}

    async def end_call(self, bot_id: str) -> dict:
        """End the current call."""
        mgr = self._managers.get(bot_id)
        if not mgr or not mgr.current_call:
            return {"error": "No active call"}
        try:
            call_id = mgr.current_call.call_id
            await mgr.end_call(call_id)
            return {"call_id": call_id, "state": "ended"}
        except CallError as e:
            return {"error": str(e)}

    async def attach_bridge(self, bot_id: str, sdp_offer: str) -> dict:
        """
        Attach a browser WebRTC bridge to the current call.

        Returns: {"sdp": "<answer SDP>"}
        """
        mgr = self._managers.get(bot_id)
        if not mgr or not mgr.current_call:
            return {"error": "No active call"}

        call = mgr.current_call
        call_id = call.call_id

        # Create bridge
        bridge = BrowserBridge(sdp_offer)
        bridge.on_browser_pcm = lambda pcm: mgr.feed_audio(call_id, pcm)

        try:
            answer_sdp = await bridge.setup()
        except Exception as e:
            log.error("Bridge setup failed: %s", e)
            return {"error": str(e)}

        # Wire peer audio → browser (per-session callback override)
        session = mgr.get_session(call_id)
        if session:
            session.on_peer_audio = lambda sess, pcm: bridge.write_pcm(pcm)

        self._bridges[call_id] = bridge
        log.info("Bridge attached for call %s", call_id)

        return {"sdp": answer_sdp, "call_id": call_id}

    # ── Protocol layer hook ────────────────────────────────────

    def on_call_entity(self, bot_id: str, entity):

        if not self._started:
            self.start()

        mgr = self._get_manager(bot_id)
        # CallManager.on_call_entity routes by call_id internally
        mgr.on_call_entity(entity)

    # ── Event bus ──────────────────────────────────────────────

    def add_listener(self, callback: Callable[[str, dict], None]):

        self._event_listeners.append(callback)

    def remove_listener(self, callback: Callable[[str, dict], None]):
        self._event_listeners = [l for l in self._event_listeners if l != callback]

    def _emit(self, event_type: str, data: dict):
        for listener in self._event_listeners:
            try:
                listener(event_type, data)
            except Exception as e:
                log.error("VoipAdapter event listener error: %s", e)

    # ── Internal callbacks ─────────────────────────────────────

    def _on_call_state(self, bot_id: str, session, info: CallInfo):
        self._emit("state_change", {
            "bot_id": bot_id,
            "call_id": info.call_id,
            "state": info.state.value,
            "peer_jid": info.peer_jid,
            "direction": info.direction.value,
        })

    def _on_incoming_call(self, bot_id: str, session, info: CallInfo):
        self._emit("incoming", {
            "bot_id": bot_id,
            "call_id": info.call_id,
            "peer_jid": info.peer_jid,
            "call_creator": info.call_creator,
        })

    def _on_call_ended(self, bot_id: str, session, info: CallInfo):
        self._emit("ended", {
            "bot_id": bot_id,
            "call_id": info.call_id,
            "reason": info.end_reason.value if info.end_reason else "unknown",
        })
        # Cleanup bridge
        cid = info.call_id
        bridge = self._bridges.pop(cid, None)
        if bridge:
            try:
                asyncio.ensure_future(bridge.close())
            except Exception:
                pass

    def _on_peer_audio(self, bot_id: str, session, pcm: list[float]):
        """Peer audio → bridge (re-routed via per-session callback in attach_bridge)."""
        pass


# ── Module-level accessor ──────────────────────────────────────

_voip_adapter: Optional[VoipAdapter] = None


def get_voip_adapter() -> VoipAdapter:
    global _voip_adapter
    if _voip_adapter is None:
        _voip_adapter = VoipAdapter()
    return _voip_adapter
