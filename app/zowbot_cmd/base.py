"""BotCommand base class — shared foundation for all command modules."""

import logging

from app.param_not_enough_exception import ParamsNotEnoughException


class BotCommand:
    """
    Base class for bot command modules.

    Subclass this and override:
      - COMMAND      : command name string, e.g. "account.getavatar"
      - DESCRIPTION  : one-line description string
      - execute(params, options) : async command handler

    Helper methods cover the four recurring patterns:
      params   → require_params / get_param / jid_param
      IQ flow  → send_iq / expect_result / send_iq_expect
      response → ok(**fields)
      logging  → self.logger (module-scoped)
    """

    COMMAND: str = ""
    DESCRIPTION: str = ""

    def __init__(self,bot):
        self.bot = bot

    # ── Entry point ───────────────────────────────────────────────────────────

    async def execute(self, params, options):
        raise NotImplementedError(f"{self.__class__.__name__} must implement execute()")

    # ── Parameter helpers ─────────────────────────────────────────────────────

    def require_params(self, params, count: int):
        """Raise ParamsNotEnoughException if fewer than *count* params are given."""
        if len(params) < count:
            raise ParamsNotEnoughException()

    def get_param(self, params, index: int, default=None):
        """Return params[index] if present, else *default*."""
        return params[index] if index < len(params) else default

    # ── IQ helpers ────────────────────────────────────────────────────────────

    async def send_iq(self, entity):
        """Send an IQ entity and return the unwrapped result object."""
        result_dict = await self.bot.botLayer._sendIqAsync(entity)
        return result_dict.get("result")

    def expect_result(self, result, expected_type):
        """Assert *result* is an instance of *expected_type*; raise otherwise."""
        if not isinstance(result, expected_type):
            raise Exception(
                f"Unexpected response type: {type(result).__name__}, "
                f"expected {expected_type.__name__}"
            )
        return result

    async def send_iq_expect(self, entity, expected_type):
        """Convenience: send IQ and assert result type in a single call."""
        result = await self.send_iq(entity)
        return self.expect_result(result, expected_type)

    # ── Response helpers ──────────────────────────────────────────────────────

    def success(self, **kwargs):
        """Build a success response dict (retcode=0 plus any extra fields)."""
        fields = {key: value for key, value in kwargs.items() if value is not None}
        return {"retcode": 0, **fields}
    
    def fail(self, retcode = -1, error = "error", **kwargs):
        fields = {key: value for key, value in kwargs.items() if value is not None}
        return {"retcode": retcode, "msg": error, **fields}

    # ── Logging ───────────────────────────────────────────────────────────────

    @property
    def logger(self):
        """Logger scoped to the concrete command's module."""
        return self.bot.logger
