"""
Bot command modules - auto-loaded by ZowBot

Two styles are supported:

  Functional (legacy)            Class-based (preferred)
  ─────────────────────────────  ─────────────────────────────────────────
  COMMAND   = "x.y"              class Command(BotCommand):
  DESCRIPTION = "..."                COMMAND = "x.y"
  async def execute(bot, p, o):      DESCRIPTION = "..."
      ...                            async def execute(self, bot, p, o):
                                         ...
"""

import importlib
import inspect
from pathlib import Path

from app.zowbot_cmd.base import BotCommand
from app.zowbot_cmd.base_send import BotSendCommand


def _find_command_class(module):
    """Return the first BotCommand subclass with a non-empty COMMAND, or None."""
    for _name, obj in inspect.getmembers(module, inspect.isclass):
        if (
            obj is not BotCommand
            and (issubclass(obj, BotCommand) )
            and getattr(obj, "COMMAND", "")
        ):
            return obj
    return None


def load_commands(bot):
    """
    Auto-discover and load all command modules from this directory recursively.
    Registers them in bot.cmdList.
    """
    cmd_dir = Path(__file__).parent
    bot.cmdList = {}
    bot.cmdMetadata = {}

    for file in sorted(cmd_dir.rglob("*.py")):        
        if file.name.startswith("_"):
            continue
        if "__pycache__" in file.parts:
            continue

        rel_parts = file.relative_to(cmd_dir).with_suffix("").parts
        module_name = ".".join(rel_parts)
        try:
            spec = importlib.util.spec_from_file_location(f"zowbot_cmd.{module_name}", file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # ── class-based command ──────────────────────────────────────────
            cmd_class = _find_command_class(module)
            if cmd_class:
                instance = cmd_class(bot)
                cmd_name = instance.COMMAND
                description = instance.DESCRIPTION
                execute_func = instance.execute          # bound method (bot, params, options)

            # ── functional command (legacy) ──────────────────────────────────
            elif hasattr(module, "COMMAND") and hasattr(module, "execute"):
                cmd_name = module.COMMAND
                description = getattr(module, "DESCRIPTION", "")
                execute_func = module.execute            # free function (bot, params, options)

            else:
                continue

            # ── register ────────────────────────────────────────────────────
            def make_cmd_func(execute_fn):
                async def cmd_wrapper(params, options):
                    return await execute_fn(params, options)
                return cmd_wrapper

            cmd_func = make_cmd_func(execute_func)
            cmd_func.cmd = cmd_name
            cmd_func.desc = description
            cmd_func.order = 0

            bot.cmdList[cmd_name] = cmd_func
            bot.cmdMetadata[cmd_name] = {"description": description, "order": 0}

        except Exception as e:
            print(f"[FAIL] Failed to load {module_name}: {e}")
            import traceback
            traceback.print_exc()
