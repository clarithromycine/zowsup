"""
Shared LLM client — unified interface for OpenAI-compatible and Anthropic APIs.

Supports:
  - OpenAI /chat/completions (GPT, DeepSeek, GLM, Qwen, etc.)
  - Anthropic /v1/messages (Claude)
  - Async via asyncio.to_thread()

Usage:
    from agent.plugin.llm_client import llm_chat

    reply = await llm_chat(
        provider="openai",
        messages=[{"role":"user","content":"Hello"}],
        api_key="sk-xxx",
        model="gpt-4o-mini",
    )
"""

from __future__ import annotations

import asyncio
import json
import logging
import urllib.request

logger = logging.getLogger(__name__)

# ── Public API ───────────────────────────────────────────────────────────────

async def llm_chat(
    provider: str,
    messages: list[dict],
    *,
    api_key: str,
    model: str = "gpt-4o-mini",
    api_url: str = "",
    system: str = "",
    temperature: float = 0.2,
    max_tokens: int = 1024,
    timeout: int = 30,
) -> str | None:
    """Send a chat completion request.  Returns the assistant's text, or None on failure.

    provider: "openai" | "anthropic"
    messages: [{"role":"user","content":"..."}, ...]
    system:   system prompt (handled per-provider)
    api_url:  base URL for OpenAI-compatible endpoints (ignored for Anthropic)
    """
    if provider == "anthropic":
        return await asyncio.to_thread(
            _anthropic_chat,
            messages=messages, system=system, api_key=api_key,
            model=model, temperature=temperature, max_tokens=max_tokens,
            timeout=timeout,
        )
    else:
        return await asyncio.to_thread(
            _openai_chat,
            messages=messages, system=system, api_key=api_key,
            api_url=api_url, model=model, temperature=temperature,
            max_tokens=max_tokens, timeout=timeout,
        )


# ── OpenAI-compatible ───────────────────────────────────────────────────────

def _openai_chat(
    messages: list[dict],
    *,
    api_key: str,
    api_url: str = "https://api.openai.com/v1",
    model: str = "gpt-4o-mini",
    system: str = "",
    temperature: float = 0.2,
    max_tokens: int = 1024,
    timeout: int = 30,
) -> str | None:
    """OpenAI /chat/completions compatible endpoint."""
    url = api_url.rstrip("/") + "/chat/completions"

    # Build message list with system prompt
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.extend(messages)

    payload = json.dumps({
        "model": model,
        "messages": msgs,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }).encode()

    try:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            result = json.loads(resp.read())
        return result["choices"][0]["message"]["content"].strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("OpenAI chat failed: %s", exc)
    return None


# ── Anthropic ────────────────────────────────────────────────────────────────

def _anthropic_chat(
    messages: list[dict],
    *,
    api_key: str,
    model: str = "claude-3-haiku-20240307",
    system: str = "",
    temperature: float = 0.2,
    max_tokens: int = 1024,
    timeout: int = 30,
) -> str | None:
    """Anthropic Messages API."""
    payload = json.dumps({
        "model": model,
        "system": system,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }).encode()

    try:
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            result = json.loads(resp.read())
        return result["content"][0]["text"].strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Anthropic chat failed: %s", exc)
    return None
