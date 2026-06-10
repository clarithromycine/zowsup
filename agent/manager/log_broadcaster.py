"""
Log broadcaster: ring buffer + WebSocket fan-out + file persistence.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from pathlib import Path
from typing import Any

from conf.constants import SysVar

logger = logging.getLogger(__name__)


class BotLogHandler(logging.Handler):
    def __init__(self, broadcaster: "LogBroadcaster"):
        super().__init__()
        self._broadcaster = broadcaster
        self.setFormatter(logging.Formatter(
            "[%(asctime)s] %(levelname)-8s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))

    def emit(self, record: logging.LogRecord):
        try:
            if record.name.startswith("BOT-"):
                self._broadcaster.emit_log(record.name[4:], self.format(record))
        except Exception:
            self.handleError(record)


class _Subscription:
    def __init__(self, queue: asyncio.Queue):
        self.queue = queue


class LogBroadcaster:

    def __init__(self, max_lines: int = 1000):
        self._buffers: dict[str, deque[str]] = {}
        self._event_buffers: dict[str, deque[dict]] = {}
        self._subscribers: dict[str, list[_Subscription]] = {}
        self._event_subscribers: dict[str, list[_Subscription]] = {}
        self._max_lines = max_lines
        self._handler: BotLogHandler | None = None
        self._file_handles: dict[str, object] = {}
        self._shutting_down = False

    def _log_dir(self) -> Path:
        base = getattr(SysVar, 'LOG_PATH', None) or getattr(SysVar, 'ACCOUNT_PATH', None)
        return (Path(base) if base else Path("logs")) / "bot_logs"

    def _log_path(self, bot_id: str) -> Path:
        return self._log_dir() / f"{bot_id}.log"

    # ── Lifecycle ──────────────────────────────────────────────

    def start(self):
        self._handler = BotLogHandler(self)
        logging.getLogger().addHandler(self._handler)
        self._log_dir().mkdir(parents=True, exist_ok=True)
        loaded = 0
        for f in self._log_dir().glob("*.log"):
            bot_id = f.stem
            lines = self._read_tail(f, self._max_lines)
            if lines:
                self._buffers[bot_id] = deque(lines, maxlen=self._max_lines)
                loaded += 1
        logger.info(f"LogBroadcaster started — {loaded} persisted logs loaded")

    def stop(self):
        self._shutting_down = True
        if self._handler:
            logging.getLogger().removeHandler(self._handler)
            self._handler = None
        for fh in self._file_handles.values():
            try: fh.close()
            except Exception: pass
        self._file_handles.clear()
        # Signal all subscribers to exit
        for subs in [*self._subscribers.values(), *self._event_subscribers.values()]:
            for sub in subs:
                try: sub.queue.put_nowait(None)
                except asyncio.QueueFull: pass
        self._subscribers.clear()
        self._event_subscribers.clear()
        logger.info("LogBroadcaster stopped")

    # ── File I/O ───────────────────────────────────────────────

    @staticmethod
    def _read_tail(path: Path, n: int) -> list[str]:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return [l.rstrip('\n') for l in f.readlines()[-n:]]
        except FileNotFoundError:
            return []

    def _append_file(self, bot_id: str, line: str):
        try:
            fh = self._file_handles.get(bot_id)
            if fh is None:
                path = self._log_path(bot_id)
                path.parent.mkdir(parents=True, exist_ok=True)
                fh = open(path, 'a', encoding='utf-8')
                self._file_handles[bot_id] = fh
            fh.write(line + '\n')
            fh.flush()
        except Exception as e:
            logger.debug(f"Log persist failed for '{bot_id}': {e}")

    # ── Log capture ────────────────────────────────────────────

    def emit_log(self, bot_id: str, line: str):
        if bot_id not in self._buffers:
            self._buffers[bot_id] = deque(maxlen=self._max_lines)
        self._buffers[bot_id].append(line)
        self._append_file(bot_id, line)

        subs = self._subscribers.get(bot_id, [])
        dead = []
        for sub in subs:
            try:
                sub.queue.put_nowait(line)
            except asyncio.QueueFull:
                dead.append(sub)
        for d in dead:
            subs.remove(d)

    def emit_event(self, bot_id: str, event_type: str, data: dict[str, Any]):
        entry = {"type": event_type, "bot_id": bot_id, "timestamp": time.time(), "data": data}
        if bot_id not in self._event_buffers:
            self._event_buffers[bot_id] = deque(maxlen=self._max_lines // 2)
        self._event_buffers[bot_id].append(entry)
        payload = json.dumps(entry, ensure_ascii=False, default=str)
        subs = self._event_subscribers.get(bot_id, [])
        dead = []
        for sub in subs:
            try: sub.queue.put_nowait(payload)
            except asyncio.QueueFull: dead.append(sub)
        for d in dead: subs.remove(d)

    # ── Subscription ───────────────────────────────────────────

    def subscribe(self, bot_id: str, queue_size: int = 256) -> _Subscription:
        sub = _Subscription(asyncio.Queue(maxsize=queue_size))
        self._subscribers.setdefault(bot_id, []).append(sub)
        return sub

    def unsubscribe(self, bot_id: str, sub: _Subscription):
        subs = self._subscribers.get(bot_id, [])
        if sub in subs: subs.remove(sub)

    def subscribe_events(self, bot_id: str, queue_size: int = 256) -> _Subscription:
        sub = _Subscription(asyncio.Queue(maxsize=queue_size))
        self._event_subscribers.setdefault(bot_id, []).append(sub)
        return sub

    def unsubscribe_events(self, bot_id: str, sub: _Subscription):
        subs = self._event_subscribers.get(bot_id, [])
        if sub in subs: subs.remove(sub)

    # ── Query ──────────────────────────────────────────────────

    def get_recent(self, bot_id: str, lines: int = 50) -> list[str]:
        buf = self._buffers.get(bot_id)
        return (list(buf)[-lines:] if lines > 0 else list(buf)) if buf else []

    def get_recent_events(self, bot_id: str, count: int = 50) -> list[dict]:
        buf = self._event_buffers.get(bot_id)
        return (list(buf)[-count:] if count > 0 else list(buf)) if buf else []

    # ── Clear ──────────────────────────────────────────────────

    def clear_logs(self, bot_id: str):
        self._buffers.pop(bot_id, None)
        fh = self._file_handles.pop(bot_id, None)
        if fh:
            try: fh.close()
            except Exception: pass
        try:
            self._log_path(bot_id).unlink(missing_ok=True)
        except Exception as e:
            logger.debug(f"Failed to delete log file for '{bot_id}': {e}")


log_broadcaster = LogBroadcaster()
