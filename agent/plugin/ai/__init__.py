"""
AI Plugin — LLM-powered auto-reply with human escalation.

When enabled, each incoming message is classified by an LLM:
  REPLY:    auto-reply immediately with the LLM's response
  ESCALATE: escalate to human operator with a reason
  IGNORE:   no action (spam, system messages, etc.)

Config keys (per bot or global):
  provider:     str   ("openai" | "anthropic") — default "openai"
  api_key:      str   — LLM API key (required)
  api_url:      str   — OpenAI-compatible endpoint (default: https://api.openai.com/v1)
  model:        str   — model name (default: gpt-4o-mini)
  system_prompt: str  — custom system prompt (overrides built-in)
  escalate_keywords: list[str] — if message contains any, escalate immediately
                               (skips LLM call, saves cost)
"""

from __future__ import annotations

import asyncio
import logging

from agent.plugin import Plugin, MessageContext, Action, NoAction, ReplyAction, EscalateAction
from agent.plugin.store import plugin_store, inner_config

logger = logging.getLogger(__name__)

# Default system prompt for the LLM
DEFAULT_SYSTEM_PROMPT = """You are a helpful WhatsApp customer service assistant.

Your task: read the user's message and choose ONE action:

1. REPLY: <your reply text>
   Use this for questions you can answer, greetings, FAQs, or simple requests.
   Keep replies concise (1-3 sentences).  Be friendly and professional.

2. ESCALATE: <short reason>
   Use this when:
   - The user is angry, threatening, or demands to speak to a manager
   - The request involves refunds, payments, or sensitive personal data
   - You are unsure and a human should handle it
   - The message contains complex legal, medical, or financial questions

3. IGNORE
   Use this for: spam, empty messages, system notifications, "ok", "thanks" (conversation enders)

Respond with exactly one of the three formats above.  No extra text."""


class AIPlugin(Plugin):
    name = "ai"
    version = "0.2.0"
    description = "LLM-powered auto-reply with human escalation"
    priority = 100   # run after translation (10)

    async def on_message(self, ctx: MessageContext) -> list[Action]:
        """Classify incoming message and act."""
        if ctx.direction != "incoming":
            return [NoAction()]

        cfg = plugin_store.get_config(self.name, ctx.bot_id)
        icfg = inner_config(cfg)   # unwrap wrapper format
        text = (ctx.content or "").strip()
        logger.debug("AI on_message: bot=%s text=%s dir=%s stage=%s enabled=%s",
                     ctx.bot_id, text[:40], ctx.direction, ctx.stage,
                     plugin_store.is_enabled(self.name, ctx.bot_id))
        if not text:
            return [NoAction()]

        # ── Stage gating: back off when conversation is in certain stages ──
        skip_stages = icfg.get("skip_stages", None)
        if skip_stages is None:
            skip_stages = ["surveying", "escalated"]
        if isinstance(skip_stages, list) and ctx.stage in skip_stages:
            logger.debug("AI skipped: stage '%s' in skip_stages", ctx.stage)
            return [NoAction()]

        # ── Human takeover: skip AI when operator has claimed this conversation ──
        import os
        cluster_url = os.environ.get("CLUSTER_URL", "")
        if cluster_url:
            import httpx, asyncio
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(5)) as c:
                    resp = await c.get(f"{cluster_url}/api/escalation?status=claimed")
                    if resp.status_code == 200:
                        items = resp.json()
                        if isinstance(items, list):
                            for item in items:
                                if item.get("conversation_id") == ctx.conversation_id:
                                    logger.debug("AI skipped: %s is claimed (router)", ctx.conversation_id)
                                    return [NoAction()]
            except Exception:
                pass
        else:
            from agent.manager.escalation_queue import escalation_queue
            if escalation_queue.is_claimed(ctx.conversation_id):
                logger.debug("AI skipped: %s is claimed by human operator", ctx.conversation_id)
                return [NoAction()]

        # ── Fast path: keyword-based escalation (no API key needed) ──
        escalate_keywords = icfg.get("escalate_keywords", [])
        if isinstance(escalate_keywords, list):
            lower_text = text.lower()
            for kw in escalate_keywords:
                if str(kw).lower() in lower_text:
                    logger.info("Keyword escalation: '%s' matched '%s'", kw, text[:50])
                    return [EscalateAction(
                        conversation_id=ctx.conversation_id,
                        reason=f"Keyword match: {kw}",
                    )]

        api_key = icfg.get("api_key", "")
        if not api_key:
            return [NoAction()]

        # ── LLM classification ──
        provider = icfg.get("provider", "openai")
        model = icfg.get("model", "gpt-4o-mini")
        api_url = icfg.get("api_url", "https://api.openai.com/v1")
        system_prompt = icfg.get("system_prompt", "") or DEFAULT_SYSTEM_PROMPT

        from agent.plugin.llm_client import llm_chat

        result = await llm_chat(
            provider=provider,
            messages=[{"role": "user", "content": text}],
            system=system_prompt,
            api_key=api_key,
            model=model,
            api_url=api_url,
            max_tokens=256,
            timeout=20,
        )

        if result is None:
            logger.warning("LLM call failed for bot '%s', escalating", ctx.bot_id)
            return [EscalateAction(
                conversation_id=ctx.conversation_id,
                reason="LLM call failed",
            )]

        return self._parse_llm_response(result, ctx)

    # ── Response parser ─────────────────────────────────────────────────────

    def _parse_llm_response(self, raw: str, ctx: MessageContext) -> list[Action]:
        """Parse the LLM's structured response into Actions."""
        text = raw.strip()

        # REPLY: ...
        if text.upper().startswith("REPLY:"):
            reply_text = text[6:].strip()
            if reply_text:
                return [ReplyAction(
                    conversation_id=ctx.conversation_id,
                    text=reply_text,
                )]
            return [NoAction()]

        # ESCALATE: ...
        if text.upper().startswith("ESCALATE:"):
            reason = text[9:].strip() or "LLM escalation"
            return [EscalateAction(
                conversation_id=ctx.conversation_id,
                reason=reason,
            )]

        # IGNORE (explicit or fallthrough)
        if text.upper().startswith("IGNORE"):
            return [NoAction()]

        # LLM didn't follow the format — escalate to be safe
        logger.warning("LLM returned unparseable response: %s", text[:100])
        return [EscalateAction(
            conversation_id=ctx.conversation_id,
            reason=f"Unparseable LLM response",
        )]
        return [NoAction()]
