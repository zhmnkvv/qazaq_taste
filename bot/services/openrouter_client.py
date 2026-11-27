"""OpenRouter chat client with the same interface as OllamaClient.

Used by the Telegram bot when AI_PROVIDER=openrouter (or when OPENROUTER_API_KEY is set
and AI_PROVIDER is not given). AIService and BookingExtractor call it exactly like the
local model: ``await client.chat(messages, json_mode=..., temperature=...) -> str``.

Reasoning:
* the consultant call asks for the model's reasoning mode ({"enabled": true});
* if the API returns reasoning in a separate field (``message.reasoning``,
  ``reasoning_content`` or ``reasoning_details``), it is wrapped as ``<think>…</think>``
  in front of the content. bot/services/reasoning.py treats <think> as reasoning:
  it is printed to the console and NEVER sent to Telegram;
* the JSON booking-extraction call switches reasoning off and requests a JSON object,
  so its output stays pure JSON.

Errors: 429 / 5xx / timeout / network -> AIUnavailableError, any other problem ->
AIServiceError. The bot then answers with the rule-based fallback; the guest never sees
technical details. There are no automatic retries (the free tier is small).

The API key is only sent in the Authorization header; it is never logged or returned.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re

import aiohttp

from bot.services.ai_service import AIServiceError, AIUnavailableError

logger = logging.getLogger(__name__)

API_BASE = "https://openrouter.ai/api/v1"
# Any of our format tags inside the API reasoning (models often draft the reply there, e.g.
# "I need to follow the format: <ответ>...</ответ>") must be neutralised, otherwise the parser
# could take a draft from the reasoning as the guest's answer.
_FORMAT_TAGS = re.compile(r"<\s*(/?)\s*(think|thinking|reasoning|размышление|answer|ответ)\s*>", re.IGNORECASE)


class OpenRouterClient:
    def __init__(self, api_key: str, model: str, timeout: float = 60.0, temperature: float = 0.4,
                 reasoning: bool = True, max_tokens: int = 4096, base_url: str = API_BASE) -> None:
        if not api_key:
            raise ValueError("OpenRouter API key is empty")
        self._api_key = api_key
        self.model = model
        self.timeout = timeout
        self.temperature = temperature
        self.reasoning = reasoning
        self.max_tokens = max_tokens
        self.base_url = base_url.rstrip("/")
        self._session: aiohttp.ClientSession | None = None

    def __repr__(self) -> str:  # never show the key
        return f"OpenRouterClient(model={self.model!r}, reasoning={self.reasoning})"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json",
                "X-Title": "Qazaq Taste Telegram bot"}

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def is_available(self) -> bool:
        """One cheap request to /key: checks that the key is accepted. No model call, no quota used."""
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/key", headers=self._headers(),
                                   timeout=aiohttp.ClientTimeout(total=10)) as resp:
                return resp.status == 200
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
            return False

    async def chat(self, messages: list[dict[str, str]], json_mode: bool = False,
                   temperature: float | None = None) -> str:
        body: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature if temperature is None else temperature,
            "max_tokens": self.max_tokens,
            # the JSON extraction call must return pure JSON, so reasoning is off there
            "reasoning": {"enabled": bool(self.reasoning and not json_mode)},
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        try:
            session = await self._get_session()
            async with session.post(f"{self.base_url}/chat/completions", json=body, headers=self._headers(),
                                    timeout=aiohttp.ClientTimeout(total=self.timeout)) as resp:
                status = resp.status
                text = await resp.text()
        except asyncio.TimeoutError as exc:
            raise AIUnavailableError(f"OpenRouter timeout after {self.timeout:.0f}s") from exc
        except (aiohttp.ClientError, OSError) as exc:
            raise AIUnavailableError(f"OpenRouter request failed: {type(exc).__name__}") from exc

        if status == 429:
            raise AIUnavailableError(f"OpenRouter rate limit (HTTP 429): {_error_message(text)}")
        if status in (401, 403):
            raise AIServiceError(f"OpenRouter rejected the API key (HTTP {status})")
        if status >= 500:
            raise AIUnavailableError(f"OpenRouter server error (HTTP {status}): {_error_message(text)}")
        if status != 200:
            raise AIServiceError(f"OpenRouter returned HTTP {status}: {_error_message(text)}")

        try:
            payload = json.loads(text)
        except ValueError as exc:
            raise AIServiceError("Invalid JSON from OpenRouter") from exc
        if isinstance(payload, dict) and payload.get("error"):  # some errors come with HTTP 200
            raise AIUnavailableError(f"OpenRouter error: {_error_message(text)}")
        choices = payload.get("choices") if isinstance(payload, dict) else None
        if not choices:
            raise AIServiceError("Empty response from OpenRouter (no choices)")
        message = choices[0].get("message") or {}
        content = message.get("content") or ""
        if not isinstance(content, str) or not content.strip():
            raise AIServiceError(f"Empty answer from OpenRouter (finish_reason={choices[0].get('finish_reason')})")

        usage = payload.get("usage") or {}
        logger.info("OpenRouter reply: model=%s, completion_tokens=%s, reasoning_tokens=%s",
                    payload.get("model", self.model), usage.get("completion_tokens"),
                    (usage.get("completion_tokens_details") or {}).get("reasoning_tokens"))

        api_reasoning = "" if json_mode else extract_api_reasoning(message)
        if api_reasoning:
            # console-only: the reasoning parser treats <think> as reasoning and never sends it to the guest
            return f"<think>\n{api_reasoning}\n</think>\n{content}"
        return content


def extract_api_reasoning(message: dict) -> str:
    """Reasoning returned by the API in a separate field (format differs between models)."""
    text = message.get("reasoning") or message.get("reasoning_content") or ""
    if not text and isinstance(message.get("reasoning_details"), list):
        text = "\n".join(str(d.get("text") or d.get("summary") or "")
                         for d in message["reasoning_details"] if isinstance(d, dict))
    return _FORMAT_TAGS.sub(lambda m: f"[{m.group(1)}{m.group(2)}]", str(text)).strip()


def _error_message(text: str) -> str:
    """Short, key-free description of an API error for the log."""
    try:
        err = json.loads(text).get("error") or {}
        message = err.get("message") or ""
        raw = (err.get("metadata") or {}).get("raw") or ""
        return f"{message} {raw}".strip()[:300]
    except (ValueError, AttributeError):
        return text[:200]
