"""
Multi-bot lifecycle manager.

Manages ZowBot instances running in separate threads via runAsThread().
Provides async-safe start/stop/list/get operations.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Optional

from app.zowbot import ZowBot
from app.zowbot_values import ZowBotType, ZowBotStatus as BotInternalStatus
from app.bot_env import BotEnv
from app.device_env import DeviceEnv
from app.network_env import NetworkEnv
from agent.manager.account_store import account_store
from agent.schemas import BotInfo, BotStatus
from conf.constants import SysVar
from proto import zowsup_pb2

logger = logging.getLogger(__name__)

def _internal_to_agent_status(internal: str) -> BotStatus:
    """Map internal ZowBotStatus string → agent BotStatus enum.

    All standard statuses share the same string value so direct conversion works.
    Only UNKNOWN (internal-only) needs a fallback to INITIAL.
    """
    try:
        return BotStatus(internal)
    except ValueError:
        return BotStatus.INITIAL


class BotManager:
    """Manages multiple ZowBot instances running in separate threads."""

    def __init__(self):
        self._lock = threading.Lock()
        self._bots: dict[str, ZowBot] = {}  # bot_id → ZowBot
        self._last_active: dict[str, float] = {}  # bot_id → last_active timestamp (runtime cache)

    # ── Public API ──────────────────────────────────────────────────────────

    def launch_bot(
        self,
        bot_id: str,
        env: str | None = None,
        proxy: Optional[str] = None,
        auto_login: bool = True,
    ) -> ZowBot:
        """Create and launch a bot thread. Returns immediately — does NOT wait for login.

        Raises ValueError if bot is already running.
        """
        with self._lock:
            if bot_id in self._bots:
                existing = self._bots[bot_id]
                if existing.thread and existing.thread.is_alive():
                    raise ValueError(f"Bot '{bot_id}' is already running")
                del self._bots[bot_id]

        if env is None:
            env = self._detect_env_from_config(bot_id)

        device_env = DeviceEnv(env)
        network_env = NetworkEnv("direct")
        bot_env = BotEnv(deviceEnv=device_env, networkEnv=network_env)

        if proxy and proxy.upper() != "DIRECT":
            network_env.updateProxyStr(proxy, rawProxyStr=proxy)

        logger.info(f"Launching bot '{bot_id}' env={env} proxy={proxy}")

        bot = ZowBot(
            bot_id=bot_id,
            env=bot_env,
            bot_type=ZowBotType.TYPE_RUN_IN_CLUSTER,
            auto=auto_login,
        )
        bot.setUpperCallback(self._on_bot_event)

        with self._lock:
            self._bots[bot_id] = bot

        bot.runAsThread(daemon=True)
        account_store.register(bot_id, env=env)
        return bot

    def wait_bot_login(self, bot: ZowBot, login_timeout: float = 30.0) -> BotInfo:
        """Wait for a launched bot to complete login. Returns BotInfo.

        Safe to call from any thread.
        """
        bot_id = next((bid for bid, b in self._bots.items() if b is bot), "unknown")
        login_completed = bot.wait_logged_in(timeout=login_timeout)

        if login_completed:
            status = bot.getStatus()
            # The LOGIN_FAIL callback fires asynchronously via executor;
            # briefly wait for _auth_fail_reason to arrive if login didn't succeed
            auth_fail = getattr(bot, "_auth_fail_reason", None)
            if status != BotInternalStatus.STATUS_RUNNING and auth_fail is None:
                for _ in range(10):
                    time.sleep(0.05)
                    auth_fail = getattr(bot, "_auth_fail_reason", None)
                    if auth_fail:
                        break

            if status == BotInternalStatus.STATUS_RUNNING:
                logger.info(f"Bot '{bot_id}' logged in successfully")
                raw_os = bot.env.deviceEnv.getOSName() if bot.env else ""
                os_env = SysVar.ENV_NAME_MAPPING.get(raw_os, raw_os) if raw_os else ""
                account_store.update_status(bot_id, "running", env=os_env or account_store.get(bot_id).get("env", ""))
            elif auth_fail:
                logger.warning(f"Bot '{bot_id}' login failed with auth error ({auth_fail})")
                account_store.update_status(bot_id, "auth_failed", auth_detail=auth_fail)
            else:
                logger.warning(f"Bot '{bot_id}' login failed (status={status})")
                account_store.update_status(bot_id, "stopped")
        else:
            logger.warning(f"Bot '{bot_id}' login did not complete within {login_timeout}s")

        return self._build_bot_info(bot_id, bot)

    def start_bot(
        self,
        bot_id: str,
        env: str | None = None,
        proxy: Optional[str] = None,
        auto_login: bool = True,
        login_timeout: float = 30.0,
    ) -> BotInfo:
        """Start a bot and wait for login. Convenience wrapper over launch + wait.

        Raises ValueError if bot is already running.
        """
        bot = self.launch_bot(bot_id, env=env, proxy=proxy, auto_login=auto_login)
        return self.wait_bot_login(bot, login_timeout=login_timeout)

    def stop_bot(self, bot_id: str, join_timeout: float = 10.0, force: bool = False) -> BotInfo | None:
        """Stop a running bot. Returns final BotInfo or None if not found.

        force=True: skip quit() and thread join, remove from dict immediately.
        """
        if force:
            with self._lock:
                bot = self._bots.pop(bot_id, None)
            if bot is None:
                logger.warning(f"Bot '{bot_id}' not found")
                return None
            logger.info(f"Stopping bot '{bot_id}' force=True")
            try: bot.quit()
            except Exception: pass
            info = self._build_bot_info(bot_id, bot)
            account_store.update_status(bot_id, "stopped",
                                        started_at=info.started_at)
            return info

        with self._lock:
            bot = self._bots.get(bot_id)

        if bot is None:
            logger.warning(f"Bot '{bot_id}' not found")
            return None

        logger.info(f"Stopping bot '{bot_id}'")

        # Attempt graceful disconnect — may fail if event loop already closed
        try:
            bot.quit()
        except RuntimeError as e:
            logger.debug(f"Bot '{bot_id}' disconnect skipped (loop closed): {e}")
        except Exception as e:
            logger.warning(f"Bot '{bot_id}' disconnect error: {e}")

        # Wait for thread to finish
        if bot.thread and bot.thread.is_alive():
            bot.thread.join(timeout=join_timeout)
            if bot.thread.is_alive():
                logger.warning(
                    f"Bot '{bot_id}' thread did not exit within {join_timeout}s"
                )

        info = self._build_bot_info(bot_id, bot)

        # Flush runtime last_active to DB before removing
        self._flush_last_active(bot_id)

        with self._lock:
            self._bots.pop(bot_id, None)

        # Record stopped status in account store — persist current started_at
        # so list_bots() won't show a stale timestamp for stopped bots.
        account_store.update_status(bot_id, "stopped",
                                    started_at=info.started_at)

        return info

    def list_bots(self) -> list[BotInfo]:
        """Return info for all managed accounts (from SQLite store)."""
        with self._lock:
            bot_items = list(self._bots.items())  # snapshot under lock
        # Build BotInfo outside the lock — _build_bot_info → get_last_active
        # also acquires _lock, and threading.Lock is not re-entrant.
        running = {bid: self._build_bot_info(bid, b) for bid, b in bot_items}

        result = []
        for row in account_store.list_all():
            bid = row["bot_id"]
            if bid in running:
                result.append(running[bid])
            else:
                db_status = row.get("status", "")
                agent_status = BotStatus.AUTH_FAILED if db_status == "auth_failed" else BotStatus.STOPPED
                last_seen = row.get("last_seen")
                result.append(BotInfo(
                    bot_id=bid,
                    status=agent_status,
                    env=row.get("env", ""),
                    started_at=row.get("started_at"),
                    last_active=int(last_seen) if last_seen else None,
                ))
        # Sort: RUNNING first, then by started_at descending (most recent on top)
        def _sort_key(info: BotInfo) -> tuple:
            running = 0 if info.status == BotStatus.RUNNING else 1
            started = info.started_at or 0
            return (running, -started)
        result.sort(key=_sort_key)
        return result

    def get_bot(self, bot_id: str) -> BotInfo | None:
        """Return info for a single bot.

        Returns running info if active, stored metadata if known, None if unknown.
        """
        with self._lock:
            bot = self._bots.get(bot_id)
        if bot is not None:
            return self._build_bot_info(bot_id, bot)

        row = account_store.get(bot_id)
        if row:
            db_status = row.get("status", "")
            agent_status = BotStatus.AUTH_FAILED if db_status == "auth_failed" else BotStatus.STOPPED
            last_seen = row.get("last_seen")
            return BotInfo(
                bot_id=bot_id,
                status=agent_status,
                env=row.get("env", ""),
                started_at=row.get("started_at"),
                last_active=int(last_seen) if last_seen else None,
            )
        return None

    def get_bot_instance(self, bot_id: str) -> ZowBot | None:
        """Return the raw ZowBot instance (for internal use, e.g. command execution)."""
        with self._lock:
            return self._bots.get(bot_id)

    async def shutdown(self):
        """Stop all running bots gracefully."""
        logger.info("Shutting down all bots...")
        with self._lock:
            bot_ids = list(self._bots.keys())

        for bot_id in bot_ids:
            try:
                self.stop_bot(bot_id, join_timeout=5.0)
            except Exception as e:
                logger.error(f"Error stopping bot '{bot_id}': {e}")

        logger.info("All bots stopped.")

    # ── Internals ────────────────────────────────────────────────────────────

    def _build_bot_info(self, bot_id: str, bot: ZowBot) -> BotInfo:
        """Build a BotInfo from a ZowBot instance.

        Uses the independently-tracked bot_id rather than bot.botId, because
        the connection layer may set bot.botId=None on login failure (403/401/405).
        """
        # Check for auth failure first (tracked via LOGIN_FAIL event in _on_bot_event)
        auth_fail = getattr(bot, "_auth_fail_reason", None)
        if auth_fail:
            return BotInfo(
                bot_id=bot_id,
                status=BotStatus.AUTH_FAILED,
                env=self._resolve_env(bot),
                fail_reason=auth_fail,
            )

        internal_status = bot.getStatus()
        agent_status = _internal_to_agent_status(internal_status)

        uptime = None
        if bot.startts and agent_status == BotStatus.RUNNING:
            uptime = time.time() - bot.startts

        # Map OS name (e.g. "SMBA") back to env_name (e.g. "smb_android")
        raw_os = bot.env.deviceEnv.getOSName() if bot.env and bot.env.deviceEnv else ""
        env = SysVar.ENV_NAME_MAPPING.get(raw_os, raw_os) if raw_os else ""

        last_active_ts = self.get_last_active(bot_id)
        return BotInfo(
            bot_id=bot_id,
            status=agent_status,
            env=env,
            started_at=int(bot.startts) if bot.startts else None,
            uptime_seconds=int(uptime) if uptime else None,
            last_active=int(last_active_ts) if last_active_ts else None,
        )

    def _resolve_env(self, bot: ZowBot) -> str:
        """Resolve env string from a bot instance."""
        raw_os = bot.env.deviceEnv.getOSName() if bot.env and bot.env.deviceEnv else ""
        return SysVar.ENV_NAME_MAPPING.get(raw_os, raw_os) if raw_os else ""

    def _detect_env_from_config(self, bot_id: str) -> str:
        """Read account config.json to determine the correct device environment.

        Returns 'android' if detection fails (safe default).
        """
        try:
            from core.profile.profile import YowProfile
            from conf.constants import SysVar
            profile = YowProfile(SysVar.ACCOUNT_PATH + bot_id)
            os_name = profile.config.os_name
            if os_name:
                return SysVar.ENV_NAME_MAPPING.get(os_name, "android")
        except Exception as e:
            logger.debug(f"Could not detect env for '{bot_id}': {e}")
        return "android"

    def touch_active(self, bot_id: str) -> None:
        """Record the bot as active at the current time (runtime cache only, no DB write).

        Called on every event / message / IQ to keep the in-memory timestamp fresh.
        Persisted to DB only on bot stop or periodic flush.
        """
        now = time.time()
        with self._lock:
            self._last_active[bot_id] = now

    def get_last_active(self, bot_id: str) -> float | None:
        """Return the runtime last_active timestamp, or fall back to DB last_seen."""
        with self._lock:
            ts = self._last_active.get(bot_id)
            if ts is not None:
                return ts
        row = account_store.get(bot_id)
        if row:
            return row.get("last_seen")
        return None

    def _flush_last_active(self, bot_id: str) -> None:
        """Persist the runtime last_active timestamp to DB."""
        with self._lock:
            ts = self._last_active.pop(bot_id, None)
        if ts is not None:
            account_store.update_last_seen(bot_id, ts)

    # ── Periodic flush ──────────────────────────────────────────────────────

    async def _periodic_flush_loop(self, interval: float = 600.0) -> None:
        """Background task: write all cached last_active timestamps to DB every *interval* seconds.

        Does NOT pop from cache — only persists current values so they survive a
        process kill. Individual bot stop still calls _flush_last_active (with pop).
        """
        try:
            while True:
                await asyncio.sleep(interval)
                self._periodic_flush_all()
        except asyncio.CancelledError:
            logger.debug("Periodic last_active flush cancelled")
        except Exception as e:
            logger.error(f"Periodic last_active flush error: {e}", exc_info=True)

    def _periodic_flush_all(self) -> None:
        """Write all cached last_active timestamps to DB without removing from cache."""
        with self._lock:
            snapshot = dict(self._last_active)
        if not snapshot:
            return
        for bot_id, ts in snapshot.items():
            try:
                account_store.update_last_seen(bot_id, ts)
            except Exception:
                logger.debug(f"Failed to flush last_active for '{bot_id}'", exc_info=True)

    def start_periodic_flush(self, interval: float = 600.0) -> None:
        """Start the background periodic flush task (called from agent lifespan)."""
        try:
            loop = asyncio.get_running_loop()
            self._flush_task = asyncio.ensure_future(self._periodic_flush_loop(interval))
            logger.debug(f"Periodic last_active flush started (interval={interval}s)")
        except RuntimeError:
            logger.warning("No running event loop; periodic flush not started")

    def stop_periodic_flush(self) -> None:
        """Stop the periodic flush task and do one final flush."""
        task = getattr(self, '_flush_task', None)
        if task and not task.done():
            task.cancel()
        # Final flush — use the non-pop version so stop_bot's pop-flush still works
        self._periodic_flush_all()
        logger.info("Periodic last_active flush stopped")

    def _on_bot_event(self, event=None, message=None, messageStatus=None,
                       cmdResult=None, modeResult=None, cbId=None):
        """Upper callback registered on each bot. Forwards structured events."""
        from agent.manager.log_broadcaster import log_broadcaster
        bot_id = cbId or "unknown"

        # Any event, message, or status update signals that the bot is alive
        if event or message or messageStatus:
            self.touch_active(bot_id)

        # Track auth failure (401/403/405) on the bot instance
        if event and isinstance(event, dict) and event.get("event") == zowsup_pb2.BotEvent.Event.LOGIN_FAIL:
            detail = event.get("detail", "")
            reason = detail.split(":")[0] if ":" in detail else detail
            with self._lock:
                bot = self._bots.get(bot_id)
                if bot:
                    bot._auth_fail_reason = reason

        if event:
            log_broadcaster.emit_event(bot_id, "event", event)
        if message:
            db_id = self._capture_incoming_message(bot_id, message)
            log_broadcaster.emit_event(bot_id, "message", message)
            self._dispatch_to_plugins(bot_id, message, db_id)
        if messageStatus:
            log_broadcaster.emit_event(bot_id, "message_status", messageStatus)
            self._capture_message_status(bot_id, messageStatus)
        if cmdResult:
            log_broadcaster.emit_event(bot_id, "cmd_result", cmdResult)

    # ── Conversation Capture ─────────────────────────────────────────────────

    def _capture_incoming_message(self, bot_id: str, message: dict) -> None:
        try:
            from agent.manager.conversation_store import conv_store
            from proto.zowsup_pb2 import MessageType
            sender_jid = message.get("lid") or message.get("from_full") or message.get("from", "")
            if not sender_jid: return
            conv_id = f"{bot_id}:{sender_jid}"
            raw_type = message.get("type", 0)
            if isinstance(raw_type, int):
                content_type = MessageType.Name(raw_type) if raw_type in MessageType.values() else str(raw_type)
            else: content_type = str(raw_type)
            if content_type in ("TEXT","URL","AD"): content = str(message.get("text",""))
            else: content = str(message.get("text","")) or f"[{content_type}]"
            row = conv_store.record_message(
                conv_id=conv_id, bot_id=bot_id, jid=sender_jid,
                direction="incoming", content_type=content_type, content=content,
                msg_id=str(message.get("msgId","")) or None,
                participant_jid=message.get("participant"),
                pn_jid=message.get("pn_jid"), status="", raw=str(message),
                media_url=message.get("media_url"),
                media_key=message.get("media_key"),
                media_mimetype=message.get("media_mimetype"),
                media_file_name=message.get("media_file_name"),
                media_file_length=message.get("media_file_length"),
                media_caption=message.get("media_caption"),
            )
            # Update notify_name (contact display name) if present
            notify = message.get("notify")
            if notify and "@" not in str(notify):
                from agent.manager.conversation_store import conv_store
                conv_store.update_notify_name(conv_id, str(notify))
            if row: message["db_id"] = row["id"]; return row["id"]
            return None
        except Exception: pass
        return None

    def _capture_message_status(self, bot_id: str, status: dict) -> None:
        try:
            from agent.manager.conversation_store import conv_store
            from proto.zowsup_pb2 import MessageStatus
            msg_id = status.get("msgId")
            if msg_id:
                raw_status = status.get("status", 0)
                if isinstance(raw_status, int) and raw_status in MessageStatus.values():
                    status_val = MessageStatus.Name(raw_status)
                else: status_val = str(raw_status)
                conv_store.update_message_status(str(msg_id), status_val)
                target_full = status.get("target_full")
                if target_full and not target_full.endswith("@s.whatsapp.net"):
                    conv_store.upgrade_conversation_jid(bot_id, str(msg_id), target_full)
        except Exception: pass

    def _dispatch_to_plugins(self, bot_id: str, message: dict, db_id=None) -> None:
        try:
            from agent.plugin import MessageContext
            from agent.plugin.manager import plugin_manager
            ctx = MessageContext(
                bot_id=bot_id,
                jid=message.get("lid") or message.get("from_full", ""),
                pn_jid=message.get("pn_jid"),
                direction="incoming",
                content_type=str(message.get("type", "TEXT")),
                content=message.get("text"),
                message_id=message.get("msgId"),
                conversation_id=f"{bot_id}:{message.get('lid') or message.get('from_full', '')}",
                participant_jid=message.get("participant"),
                raw=message,
                db_id=db_id,
            )
            import asyncio
            async def _run():
                try:
                    actions = await plugin_manager.dispatch_on_message(ctx)
                    if actions: await plugin_manager.execute_actions(actions)
                except Exception:
                    logger.exception("Plugin dispatch failed")
            try:
                loop = asyncio.get_running_loop()
                asyncio.run_coroutine_threadsafe(_run(), loop)
            except RuntimeError:
                asyncio.run(_run())
        except Exception:
            logger.exception("_dispatch_to_plugins failed")

    # ── Command Execution ────────────────────────────────────────────────────

    def execute_cmd(
        self,
        bot_id: str,
        cmd_name: str,
        args: list[str] | None = None,
        options: dict | None = None,
        timeout: float = 30.0,
    ) -> tuple[object | None, dict | None]:
        """Execute a command on a running bot and return (result, error).

        Uses ZowBot.callDirectCompat() for cross-thread safe execution.
        This is a BLOCKING call — wrap with asyncio.to_thread() in async endpoints.

        Returns:
            (result, error) tuple. Exactly one is None.
            error dict has keys: "code" (int), "msg" (str).
        """
        if args is None:
            args = []
        if options is None:
            options = {}

        bot = self.get_bot_instance(bot_id)
        if bot is None:
            return None, {"code": -404, "msg": f"Bot '{bot_id}' not found"}

        return bot.callDirectCompat(cmd_name, args, options, timeout=int(timeout))

    # ── Account Cleanup ─────────────────────────────────────────────────────

    def purge_accounts(self, mode: str = "list", bot_ids: list[str] | None = None) -> dict[str, dict]:
        """Purge auth-failed / orphaned accounts.

        mode="auto": purge ALL accounts that are either:
          - status=auth_failed in the DB, OR
          - in the DB but missing a local data directory (orphaned entries).
          (bot_ids is ignored in auto mode.)
        mode="list": purge only the specified bot_ids that have status=auth_failed.

        Returns a dict mapping bot_id → {"success": bool, "error": str | None}.
        """
        from pathlib import Path
        import shutil

        # Resolve which bot_ids to purge
        if mode == "auto":
            rows = account_store.list_all()
            target_ids = []
            for row in rows:
                bid = row["bot_id"]
                acct_dir = Path(SysVar.ACCOUNT_PATH) / bid
                if row.get("status") == "auth_failed" or not acct_dir.exists():
                    target_ids.append(bid)
            if not target_ids:
                logger.info("purge_accounts(auto): nothing to purge")
                return {}
        else:
            if not bot_ids:
                return {}
            # Only purge bots that have status=auth_failed in the DB
            target_ids = [
                bid for bid in bot_ids
                if account_store.get(bid) and account_store.get(bid).get("status") == "auth_failed"
            ]
            skipped = set(bot_ids) - set(target_ids)
            if skipped:
                logger.info(f"purge_accounts(list): skipped {skipped} (not auth_failed or not in DB)")

        if not target_ids:
            return {}

        results: dict[str, dict] = {}
        for bot_id in target_ids:
            try:
                errors: list[str] = []

                # 1. Stop bot if running
                try:
                    self.stop_bot(bot_id, join_timeout=5.0)
                except Exception as e:
                    errors.append(f"stop: {e}")

                # 2. Remove from account store DB
                account_store.remove(bot_id)

                # 3. Delete local data directory
                acct_dir = Path(SysVar.ACCOUNT_PATH) / bot_id
                if acct_dir.exists():
                    shutil.rmtree(acct_dir)
                    logger.info(f"Purged account data directory: {acct_dir}")

                results[bot_id] = {
                    "success": True,
                    "error": "; ".join(errors) if errors else None,
                }
            except Exception as e:
                logger.error(f"Failed to purge account '{bot_id}': {e}")
                results[bot_id] = {"success": False, "error": str(e)}

        return results


# Singleton instance
bot_manager = BotManager()
