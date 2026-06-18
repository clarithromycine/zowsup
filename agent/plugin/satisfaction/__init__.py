"""
Satisfaction Survey Plugin — post-service quality rating (1-5).

Triggers when a customer-initiated conversation goes idle for a configurable
period.  Sends a rating prompt, collects the score, and replies with a
thank-you message.

Config keys (per bot or global):
  inactivity_minutes: int   — idle minutes before sending survey (default: 5)
  survey_message:     str   — rating prompt text
  thank_you_message:  str   — reply after receiving a valid rating
"""

from __future__ import annotations

import asyncio
import logging
import re
import threading
import time

from agent.plugin import Plugin, MessageContext, Action, NoAction, ReplyAction
from agent.plugin.store import plugin_store, inner_config
from agent.plugin.manager import plugin_manager
from agent.plugin.satisfaction.store import survey_store

logger = logging.getLogger(__name__)

# Regex to extract a standalone 1-5 digit from text
_RATING_RE = re.compile(r'(?<![0-9])([1-5])(?![0-9])')


class SatisfactionPlugin(Plugin):
    name = "satisfaction"
    version = "0.1.0"
    description = "Post-service satisfaction survey (1-5 rating)"
    priority = 200

    def __init__(self):
        self._timers: dict[str, threading.Timer] = {}  # conv_id → Timer

    # ── Plugin hooks ────────────────────────────────────────────────────────

    async def on_start(self, bot_id: str) -> list[Action]:
        return []

    async def on_stop(self, bot_id: str) -> list[Action]:
        prefix = f"{bot_id}:"
        to_cancel = [k for k in self._timers if k.startswith(prefix)]
        for k in to_cancel:
            self._timers[k].cancel()
            del self._timers[k]
        logger.info("Satisfaction: cancelled %d timers for bot '%s'", len(to_cancel), bot_id)
        return []

    async def on_message(self, ctx: MessageContext) -> list[Action]:
        """Incoming messages: session lifecycle.  Only cancels timer;
        the timer is restarted by outgoing messages (on_before_send)."""
        logger.debug("Satisfaction: on_message dir=%s conv=%s stage=%s",
                     ctx.direction, ctx.conversation_id, ctx.stage)
        if ctx.direction != "incoming":
            return [NoAction()]

        if not ctx.conversation_id or "@g.us" in ctx.conversation_id:
            return [NoAction()]

        conv_id = ctx.conversation_id
        cfg = self._get_config(ctx.bot_id)

        active = survey_store.get_active_session(conv_id)
        if active is None:
            # Only create a new session if the conversation has been quiet
            # for > session_gap_hours (default 24h).  Prevents treating
            # operator-initiated outreach replies as new service sessions.
            gap_hours = int(cfg.get("session_gap_hours", 24))
            if not self._is_new_conversation(conv_id, gap_hours):
                logger.debug("Satisfaction:   skip %s (last msg within %dh)", conv_id, gap_hours)
                return [NoAction()]
            survey_store.create_session(ctx.bot_id, conv_id)
            logger.info("Satisfaction: ▶ new session for %s", conv_id)
            return [NoAction()]

        if active["session_status"] == "active":
            survey_store.touch_session(active["id"])
            self._cancel_timer(conv_id)   # stop countdown, customer is still here
            logger.debug("Satisfaction:   ← %s (timer cleared)", conv_id)
            return [NoAction()]

        if active["session_status"] == "surveying":
            rating = self._parse_rating(ctx.content or "")
            if rating is not None:
                survey_store.complete_survey(active["id"], rating)
                plugin_manager.set_stage(conv_id, "normal")
                self._cancel_timer(conv_id)
                thank = cfg.get("thank_you_message", "Thank you for your feedback!")
                logger.info("Satisfaction: ★ %s rated %d — session complete", conv_id, rating)
                return [ReplyAction(conversation_id=conv_id, text=thank)]
            else:
                survey_store.expire_session(active["id"])
                plugin_manager.set_stage(conv_id, "normal")
                self._cancel_timer(conv_id)
                survey_store.create_session(ctx.bot_id, conv_id)
                logger.info("Satisfaction: ↻ %s non-rating in surveying, session reset", conv_id)
                return [NoAction()]

        return [NoAction()]

    async def on_before_send(self, ctx: MessageContext) -> list[Action]:
        """Outgoing message: reset the inactivity timer (operator just replied)."""
        if not ctx.conversation_id or "@g.us" in ctx.conversation_id:
            return []

        active = survey_store.get_active_session(ctx.conversation_id)
        if active and active["session_status"] in ("active", "surveying"):
            survey_store.touch_session(active["id"])
            self._reschedule_inactivity(ctx.conversation_id, ctx.bot_id, self._get_config(ctx.bot_id))
            logger.debug("Satisfaction:   heartbeat → %s", ctx.conversation_id)
        return []  # Never modify the outgoing message

    # ── Inactivity timer (threading.Timer, not asyncio — survives temp loops) ─

    def _schedule_inactivity(self, conv_id: str, bot_id: str, cfg: dict) -> None:
        minutes = int(cfg.get("inactivity_minutes", 5))
        self._cancel_timer(conv_id)
        t = threading.Timer(minutes * 60, self._on_timeout, args=[conv_id, bot_id])
        t.daemon = True
        self._timers[conv_id] = t
        t.start()
        logger.info("Satisfaction: ⏱ timer started for %s, timeout=%dmin", conv_id, minutes)

    def _reschedule_inactivity(self, conv_id: str, bot_id: str, cfg: dict) -> None:
        self._schedule_inactivity(conv_id, bot_id, cfg)

    def _cancel_timer(self, conv_id: str) -> None:
        t = self._timers.pop(conv_id, None)
        if t:
            t.cancel()

    def _on_timeout(self, conv_id: str, bot_id: str) -> None:
        """Called by threading.Timer in a worker thread when timeout expires."""
        try:
            active = survey_store.get_active_session(conv_id)
            if active is None or active["session_status"] != "active":
                logger.debug("Satisfaction: timeout ignored — %s no longer active", conv_id)
                return

            last = active.get("last_msg_at", 0)
            cfg = self._get_config(bot_id)
            timeout_sec = int(cfg.get("inactivity_minutes", 5)) * 60
            if time.time() - last < timeout_sec - 5:
                logger.debug("Satisfaction: timeout ignored — %s active %.0fs ago", conv_id, time.time() - last)
                return

            # Trigger survey
            survey_msg = cfg.get("survey_message", "Please rate our service (1-5, 5 being excellent)")
            survey_store.set_surveying(active["id"])
            plugin_manager.set_stage(conv_id, "surveying")
            logger.info("Satisfaction: survey triggered for %s — sending: %s", conv_id, survey_msg[:50])

            # Send via bot_manager (thread-safe: execute_cmd is synchronous)
            from agent.manager.bot_manager import bot_manager
            parts = conv_id.split(":", 1)
            if len(parts) == 2:
                b_id, jid = parts
                result, error = bot_manager.execute_cmd(
                    bot_id=b_id, cmd_name="msg.send", args=[jid, survey_msg],
                    options={"waitid": 15}, timeout=30,
                )
                if error:
                    logger.error("Satisfaction: send failed for %s: %s", conv_id, error)
                else:
                    from agent.manager.conversation_store import conv_store
                    conv_store.record_message(
                        conv_id=conv_id, bot_id=b_id, jid=jid,
                        direction="outgoing", content_type="TEXT",
                        content=survey_msg, status="EXECUTED",
                    )
        except Exception:
            logger.exception("Satisfaction: timeout handler failed for %s", conv_id)
        finally:
            self._timers.pop(conv_id, None)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _get_config(self, bot_id: str) -> dict:
        """Get config, always re-reading from store so hot-reload works."""
        cfg = inner_config(plugin_store.get_config(self.name, bot_id))
        return {
            "inactivity_minutes": int(cfg.get("inactivity_minutes", 5)),
            "session_gap_hours": int(cfg.get("session_gap_hours", 24)),
            "survey_message": cfg.get("survey_message",
                "Please rate our service (1-5, 5 being excellent)"),
            "thank_you_message": cfg.get("thank_you_message",
                "Thank you for your feedback! Feel free to reach out anytime."),
        }

    @staticmethod
    def _is_new_conversation(conv_id: str, gap_hours: int) -> bool:
        """Check if enough time has passed since the last message to treat
        this as a new service session.  Uses the conversations table's
        last_message_at timestamp."""
        from agent.manager.conversation_store import conv_store as _cs
        conv = _cs.get_conversation(conv_id)
        if conv is None:
            return True  # brand-new conversation
        last = conv.get("last_message_at") or conv.get("updated_at") or 0
        return time.time() - last > gap_hours * 3600

    @staticmethod
    def _parse_rating(text: str) -> int | None:
        """Extract a 1-5 integer rating from text.  Returns None if not found."""
        match = _RATING_RE.search(text)
        if match:
            return int(match.group(1))
        return None
