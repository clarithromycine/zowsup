"""
Multi-bot lifecycle manager.

Manages ZowBot instances running in separate threads via runAsThread().
Provides async-safe start/stop/list/get operations.
"""

from __future__ import annotations

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

logger = logging.getLogger(__name__)

# Mapping from internal ZowBotStatus string → agent BotStatus enum
_STATUS_MAP: dict[str, BotStatus] = {
    BotInternalStatus.STATUS_INITIAL: BotStatus.INITIAL,
    BotInternalStatus.STATUS_RUNNING: BotStatus.RUNNING,
    BotInternalStatus.STATUS_STOPPING: BotStatus.STOPPING,
    BotInternalStatus.STATUS_STOPPED: BotStatus.STOPPED,
    BotInternalStatus.STATUS_ERROR: BotStatus.ERROR,
    BotInternalStatus.STATUS_UNKNOWN: BotStatus.INITIAL,
}


def _internal_to_agent_status(internal: str) -> BotStatus:
    return _STATUS_MAP.get(internal, BotStatus.INITIAL)


class BotManager:
    """Manages multiple ZowBot instances running in separate threads."""

    def __init__(self):
        self._lock = threading.Lock()
        self._bots: dict[str, ZowBot] = {}  # bot_id → ZowBot

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
            if status == BotInternalStatus.STATUS_RUNNING:
                logger.info(f"Bot '{bot_id}' logged in successfully")
                raw_os = bot.env.deviceEnv.getOSName() if bot.env else ""
                os_env = SysVar.ENV_NAME_MAPPING.get(raw_os, raw_os) if raw_os else ""
                account_store.update_status(bot_id, "running", env=os_env or account_store.get(bot_id).get("env", ""))
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

    def stop_bot(self, bot_id: str, join_timeout: float = 10.0) -> BotInfo | None:
        """Stop a running bot. Returns final BotInfo or None if not found."""
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

        with self._lock:
            self._bots.pop(bot_id, None)

        # Record stopped status in account store
        account_store.update_status(bot_id, "stopped")

        return info

    def list_bots(self) -> list[BotInfo]:
        """Return info for all managed accounts (from SQLite store)."""
        with self._lock:
            running = {bid: self._build_bot_info(bid, b) for bid, b in self._bots.items()}

        result = []
        for row in account_store.list_all():
            bid = row["bot_id"]
            if bid in running:
                result.append(running[bid])
            else:
                result.append(BotInfo(
                    bot_id=bid,
                    status=BotStatus.STOPPED,
                    env=row.get("env", ""),
                    started_at=row.get("started_at"),
                ))
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
            return BotInfo(
                bot_id=bot_id,
                status=BotStatus.STOPPED,
                env=row.get("env", ""),
                started_at=row.get("started_at"),
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
        internal_status = bot.getStatus()
        agent_status = _internal_to_agent_status(internal_status)

        uptime = None
        if bot.startts and agent_status == BotStatus.RUNNING:
            uptime = time.time() - bot.startts

        # Map OS name (e.g. "SMBA") back to env_name (e.g. "smb_android")
        raw_os = bot.env.deviceEnv.getOSName() if bot.env and bot.env.deviceEnv else ""
        env = SysVar.ENV_NAME_MAPPING.get(raw_os, raw_os) if raw_os else ""

        return BotInfo(
            bot_id=bot_id,
            status=agent_status,
            env=env,
            started_at=int(bot.startts) if bot.startts else None,
            uptime_seconds=int(uptime) if uptime else None,
        )

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

    def _on_bot_event(self, event=None, message=None, messageStatus=None,
                       cmdResult=None, modeResult=None, cbId=None):
        """Upper callback registered on each bot. Forwards structured events."""
        from agent.manager.log_broadcaster import log_broadcaster
        bot_id = cbId or "unknown"

        if event:
            log_broadcaster.emit_event(bot_id, "event", event)
        if message:
            log_broadcaster.emit_event(bot_id, "message", message)
        if messageStatus:
            log_broadcaster.emit_event(bot_id, "message_status", messageStatus)
        if cmdResult:
            log_broadcaster.emit_event(bot_id, "cmd_result", cmdResult)

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


# Singleton instance
bot_manager = BotManager()
