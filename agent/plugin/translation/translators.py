"""
Translation providers — Google (free) and LLM (OpenAI-compatible).

Google Translate uses the translate-pa.googleapis.com JSON API with
fallback to async HTML scrape.  No API key required.
"""

from __future__ import annotations

import html
import json
import logging
import re
import time
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

# ── Google Translate (free, no API key) ─────────────────────────────────────

_GT_PA_URL = "https://translate-pa.googleapis.com/v1/translateHtml"
_GT_PA_KEY = "AIzaSyATBXajvzQLTDHEQbcpq0Ihe0vWDHmO520"
_GT_ASYNC_BASE = "https://www.google.com/async/translate?"
_GT_TEXT_RE = re.compile(r'id="tw-answ-target-text">([^<]+)</span>')
_GT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/144.0.0.0 Safari/537.36"
)

# Normalise language codes for Google
_GL_MAP = {"zh": "zh-CN", "zh-tw": "zh-TW", "auto": "auto"}


def google_translate(text: str, to_lang: str, from_lang: str = "auto") -> str | None:
    """Translate text via Google (free). Returns None on failure."""
    g_to = _GL_MAP.get(to_lang.lower(), to_lang)
    g_from = _GL_MAP.get(from_lang.lower(), from_lang) if from_lang not in ("auto", "") else "auto"

    result = _google_pa(text, g_from, g_to)
    if result is not None:
        return result
    return _google_async(text, g_from, g_to)


def _google_pa(text: str, from_lang: str, to_lang: str) -> str | None:
    """translate-pa.googleapis.com — JSON+protobuf payload."""
    try:
        payload = json.dumps([[[text], from_lang, to_lang], "wt_lib"]).encode()
        req = urllib.request.Request(
            _GT_PA_URL,
            data=payload,
            headers={
                "Content-Type": "application/json+protobuf",
                "X-Goog-Api-Key": _GT_PA_KEY,
                "User-Agent": _GT_UA,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as resp:  # noqa: S310
            body = json.loads(resp.read())
        if isinstance(body, list) and len(body) >= 1 and body[0]:
            return html.unescape(body[0][0])
    except Exception as exc:  # noqa: BLE001
        logger.debug("Google PA API failed: %s", exc)
    return None


def _google_async(text: str, from_lang: str, to_lang: str) -> str | None:
    """Fallback: Google async HTML translate endpoint."""
    try:
        async_val = (
            f"sl:{from_lang},tl:{to_lang},st:{urllib.parse.quote(text)},"
            f"id:{int(time.time() * 1000)},qc:true,ac:true,"
            "_id:tw-async-translate,_pms:s,_fmt:pc"
        )
        params = urllib.parse.urlencode({"async": async_val})
        req = urllib.request.Request(
            _GT_ASYNC_BASE + params,
            headers={"Accept-Charset": "utf-8", "User-Agent": _GT_UA},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
            body = resp.read().decode("utf-8", errors="replace")
        m = _GT_TEXT_RE.search(body)
        return html.unescape(m.group(1)) if m else None
    except Exception as exc:  # noqa: BLE001
        logger.debug("Google async scrape failed: %s", exc)
    return None


# ── LLM Translation (OpenAI-compatible) ──────────────────────────────────────

def llm_translate(
    text: str,
    to_lang: str,
    from_lang: str = "auto",
    *,
    api_key: str,
    api_url: str = "https://api.openai.com/v1",
    model: str = "gpt-4o-mini",
    timeout: int = 30,
) -> str | None:
    """Translate via any OpenAI-compatible LLM endpoint."""
    if from_lang == "auto":
        instruction = f"Translate the following text to {to_lang}. Only output the translation, nothing else."
    else:
        instruction = f"Translate the following text from {from_lang} to {to_lang}. Only output the translation, nothing else."

    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": instruction},
            {"role": "user", "content": text},
        ],
        "temperature": 0.2,
        "max_tokens": 1024,
    }).encode()

    api_url = api_url.rstrip("/") + "/chat/completions"
    try:
        req = urllib.request.Request(
            api_url,
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
        logger.warning("LLM translate failed: %s", exc)
    return None


# ── Anthropic Translation ────────────────────────────────────────────────────

def anthropic_translate(
    text: str,
    to_lang: str,
    from_lang: str = "auto",
    *,
    api_key: str,
    model: str = "claude-3-haiku-20240307",
    timeout: int = 30,
) -> str | None:
    """Translate via Anthropic Messages API.

    Anthropic uses a different wire format than OpenAI:
      - Endpoint: POST /v1/messages
      - Auth: x-api-key header (not Bearer)
      - System prompt: top-level "system" field
      - max_tokens is REQUIRED
      - Response: content[0].text
    """
    if from_lang == "auto":
        instruction = f"Translate the following text to {to_lang}. Only output the translation, nothing else."
    else:
        instruction = f"Translate the following text from {from_lang} to {to_lang}. Only output the translation, nothing else."

    payload = json.dumps({
        "model": model,
        "system": instruction,
        "messages": [
            {"role": "user", "content": text},
        ],
        "max_tokens": 1024,
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
        logger.warning("Anthropic translate failed: %s", exc)
    return None
