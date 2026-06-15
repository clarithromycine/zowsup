"""
Translation Plugin — auto-translate messages between working language
and customer-facing language.

Config keys (per bot or global):
  work_lang:   str   (e.g. "zh")   — operator's working language
  target_lang: str   (e.g. "es")   — customer-facing language
  provider:    str   ("google" | "llm") — default "google"
  llm_api_key: str   — LLM API key (only when provider == "llm")
  llm_api_url: str   — LLM endpoint (only when provider == "llm")
  llm_model:   str   — LLM model name
"""

from __future__ import annotations

import asyncio
import logging
import threading

from agent.plugin import Plugin, MessageContext, Action, NoAction, ReplyAction, ConfigAction
from agent.plugin.store import plugin_store
from agent.plugin.translation.translators import google_translate, llm_translate, anthropic_translate

logger = logging.getLogger(__name__)


class TranslationPlugin(Plugin):
    name = "translation"
    version = "0.1.0"
    description = "Auto-translate messages between work_lang & target_lang via Google or LLM"
    priority = 10    # run early — translate before other plugins process content

    # ── Plugin hooks ────────────────────────────────────────────────────────

    async def on_message(self, ctx: MessageContext) -> list[Action]:
        """Incoming message: if it's in the target language, translate to work language.

        The translation is stored as an additional message in the conversation
        so the operator always sees content in their working language.
        """
        if ctx.direction != "incoming":
            return [NoAction()]

        cfg = plugin_store.get_config(self.name, ctx.bot_id)
        work_lang = cfg.get("work_lang", "")
        target_lang = cfg.get("target_lang", "")
        if not work_lang or not target_lang or work_lang == target_lang:
            return [NoAction()]

        text = (ctx.content or "").strip()
        if not text or len(text) < 2:
            return [NoAction()]

        translated = await self._translate(text, target_lang, work_lang, cfg)
        if translated is None or translated == text:
            return [NoAction()]

        # Store translation as a note in the conversation
        from agent.manager.conversation_store import conv_store
        parent_id = ctx.db_id  # directly from the incoming message

        note = conv_store.record_message(
            conv_id=ctx.conversation_id,
            bot_id=ctx.bot_id,
            jid=ctx.jid,
            direction="note",
            content_type="TRANSLATION",
            content=f"[{work_lang}] {translated}",
            status="",
        )

        # Push note to WebSocket clients in real time (with parent_id for matching)
        from agent.manager.log_broadcaster import log_broadcaster
        note_data = dict(note)
        note_data["parent_id"] = parent_id
        log_broadcaster.emit_event(ctx.bot_id, "note", note_data)

        logger.debug("Translated incoming: %s → %s", target_lang, work_lang)
        return [NoAction()]

    async def on_before_send(self, ctx: MessageContext) -> list[Action]:
        """Outgoing message: if it's in the working language, translate to target language.

        Returns a ReplyAction with both original and translated text,
        so the bot sends a bilingual message.
        """
        if ctx.direction != "outgoing":
            return [NoAction()]

        cfg = plugin_store.get_config(self.name, ctx.bot_id)
        work_lang = cfg.get("work_lang", "")
        target_lang = cfg.get("target_lang", "")
        if not work_lang or not target_lang or work_lang == target_lang:
            return [NoAction()]

        text = (ctx.content or "").strip()
        if not text or len(text) < 2:
            return [NoAction()]

        translated = await self._translate(text, work_lang, target_lang, cfg)
        if translated is None or translated == text:
            return [NoAction()]

        # Send translated text with language tag
        logger.debug("Translated outgoing: %s → %s", work_lang, target_lang)
        return [ReplyAction(conversation_id=ctx.conversation_id, text=translated, target_lang=target_lang)]

    # ── Internal ─────────────────────────────────────────────────────────────

    async def _translate(
        self, text: str, from_lang: str, to_lang: str, cfg: dict,
    ) -> str | None:
        """Translate text using the configured provider (or none)."""
        provider = cfg.get("provider", "google")

        if provider == "llm":
            api_key = cfg.get("llm_api_key", "")
            if not api_key:
                logger.warning("LLM provider configured but no llm_api_key set")
                return None
            api_url = cfg.get("llm_api_url", "https://api.openai.com/v1")
            model = cfg.get("llm_model", "gpt-4o-mini")
            return await asyncio.to_thread(
                llm_translate, text, to_lang, from_lang,
                api_key=api_key, api_url=api_url, model=model,
            )

        if provider == "anthropic":
            api_key = cfg.get("llm_api_key", "")
            if not api_key:
                logger.warning("Anthropic provider configured but no llm_api_key set")
                return None
            model = cfg.get("llm_model", "claude-3-haiku-20240307")
            return await asyncio.to_thread(
                anthropic_translate, text, to_lang, from_lang,
                api_key=api_key, model=model,
            )

        # Default: Google free
        return await asyncio.to_thread(google_translate, text, to_lang, from_lang)

    async def on_start(self, bot_id: str) -> list[Action]:
        """Auto-enable if work_lang != target_lang."""
        cfg = plugin_store.get_config(self.name, bot_id)
        wl = cfg.get("work_lang", "")
        tl = cfg.get("target_lang", "")
        if wl and tl and wl != tl:
            plugin_store.set_enabled(self.name, True, bot_id)
            logger.info("Translation auto-enabled for bot '%s': %s→%s", bot_id, wl, tl)
        return []
