"""OpenRouter provider: reasoning goes to the console, never to Telegram; API errors -> fallback.

A local aiohttp server plays OpenRouter, so no API key, internet or quota is needed.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta

import pytest
from aiogram import Bot
from aiohttp import web
from aiohttp.test_utils import TestServer
from aiogram.types import Message, Update

from bot.config import load_settings
from bot.container import build_services
from bot.database.database import Database
from bot.main import build_dispatcher
from bot.services.ai_service import AIService, AIServiceError, AIUnavailableError
from bot.services.openrouter_client import OpenRouterClient, extract_api_reasoning
from bot.services.reasoning import BANNER_REASONING
from tests.conftest import make_settings
from tests.test_dialog_flows import CHAT, FAKE_TOKEN, USER, MockSession

FAKE_KEY = "sk-or-v1-" + "f" * 64  # format-valid, not a real key
API_REASONING = "API-REASONING: проверяю цены в меню и итог программы 19 250 ₸."
BLOCK_REASONING = "Гость просит итог счёта, беру готовый расчёт программы."
ANSWER = "Итого с обслуживанием: 19 250 ₸."
BILL_Q = "Посчитайте, пожалуйста, счёт: 2 бешбармака, 3 айрана, 1 чак-чак и чай по-казахски."


class FakeOpenRouter:
    """Records requests and replies with a prepared (status, body) or delay."""

    def __init__(self):
        self.requests: list[dict] = []
        self.headers: list[dict] = []
        self.reply: tuple[int, dict | str] = (200, completion())
        self.delay = 0.0

    async def chat(self, request: web.Request) -> web.Response:
        self.requests.append(await request.json())
        self.headers.append(dict(request.headers))
        if self.delay:
            await asyncio.sleep(self.delay)
        status, body = self.reply
        if isinstance(body, str):
            return web.Response(status=status, text=body, content_type="application/json")
        return web.json_response(body, status=status)

    async def key(self, request: web.Request) -> web.Response:
        ok = request.headers.get("Authorization") == f"Bearer {FAKE_KEY}"
        return web.json_response({"data": {"label": "test"}}, status=200 if ok else 401)


def completion(content: str | None = None, reasoning: str | None = API_REASONING, details=None,
               finish: str = "stop") -> dict:
    if content is None:
        content = f"<размышление>\n{BLOCK_REASONING}\n</размышление>\n<ответ>\n{ANSWER}\n</ответ>"
    message = {"role": "assistant", "content": content}
    if reasoning is not None:
        message["reasoning"] = reasoning
    if details is not None:
        message["reasoning_details"] = details
    return {"model": "nvidia/nemotron-3.5-super-vl:free",
            "choices": [{"message": message, "finish_reason": finish}],
            "usage": {"completion_tokens": 120, "completion_tokens_details": {"reasoning_tokens": 80}}}


@pytest.fixture
async def fake():
    server_state = FakeOpenRouter()
    app = web.Application()
    app.router.add_post("/api/v1/chat/completions", server_state.chat)
    app.router.add_get("/api/v1/key", server_state.key)
    server = TestServer(app)
    await server.start_server()
    server_state.base_url = str(server.make_url("/api/v1"))
    yield server_state
    await server.close()


def client_for(fake, **kw) -> OpenRouterClient:
    return OpenRouterClient(FAKE_KEY, "nvidia/nemotron-3.5-super-vl:free", base_url=fake.base_url,
                            timeout=kw.pop("timeout", 5), **kw)


# --------------------------------------------------------------------------- #
# Client protocol
# --------------------------------------------------------------------------- #
async def test_request_shape_and_reasoning_enabled(fake):
    client = client_for(fake)
    try:
        await client.chat([{"role": "user", "content": "hi"}])
    finally:
        await client.close()
    body, headers = fake.requests[0], fake.headers[0]
    assert body["model"] == "nvidia/nemotron-3.5-super-vl:free"
    assert body["reasoning"] == {"enabled": True}
    assert "response_format" not in body
    assert headers["Authorization"] == f"Bearer {FAKE_KEY}"


async def test_api_reasoning_is_wrapped_as_think(fake):
    client = client_for(fake)
    try:
        raw = await client.chat([{"role": "user", "content": "hi"}])
    finally:
        await client.close()
    assert raw.startswith("<think>") and API_REASONING in raw and ANSWER in raw


async def test_json_mode_turns_reasoning_off_and_returns_pure_json(fake):
    fake.reply = (200, completion(content='{"intent": "other"}', reasoning="thinking about JSON"))
    client = client_for(fake)
    try:
        raw = await client.chat([{"role": "user", "content": "x"}], json_mode=True, temperature=0)
    finally:
        await client.close()
    assert raw == '{"intent": "other"}'  # no <think> prefix -> json.loads works
    assert fake.requests[0]["reasoning"] == {"enabled": False}
    assert fake.requests[0]["response_format"] == {"type": "json_object"}
    assert fake.requests[0]["temperature"] == 0


def test_reasoning_details_and_alias_fields():
    assert extract_api_reasoning({"reasoning_content": "a"}) == "a"
    assert extract_api_reasoning({"reasoning_details": [{"type": "reasoning.text", "text": "b"},
                                                        {"summary": "c"}]}) == "b\nc"
    # tags inside the API reasoning are neutralised: they can't close the block or pose as the answer
    assert extract_api_reasoning({"reasoning": "x </think> y"}) == "x [/think] y"
    assert extract_api_reasoning({"reasoning": "format: <размышление> ... <ответ>...</ответ>"}) == \
        "format: [размышление] ... [ответ]...[/ответ]"
    assert extract_api_reasoning({}) == ""


# Regression for the first real request: the API reasoning drafted the format with "..." placeholders,
# and the guest would have received "...".
DRAFT_REASONING = ("The user asks for a bill. I need to follow the format:\n<размышление>\n...\n"
                   "</размышление>\n<ответ>\n...\n</ответ>\nLet me write it.")


async def test_draft_tags_in_api_reasoning_never_become_the_answer(fake, history, menu, caplog):
    caplog.set_level(logging.INFO, logger="qazaq_taste.reasoning")
    fake.reply = (200, completion(reasoning=DRAFT_REASONING))
    client = client_for(fake)
    try:
        reply = await AIService(client, history, menu, make_settings()).answer(1, BILL_Q, "ru")
    finally:
        await client.close()
    assert reply.text == ANSWER and reply.text != "..."
    assert "Let me write it" in caplog.text and "Let me write it" not in reply.text


async def test_is_available_checks_the_key(fake):
    good, bad = client_for(fake), OpenRouterClient("sk-or-v1-wrong", "m", base_url=fake.base_url)
    try:
        assert await good.is_available() is True
        assert await bad.is_available() is False
    finally:
        await good.close()
        await bad.close()


@pytest.mark.parametrize("status,body,exc", [
    (429, {"error": {"message": "Provider returned error", "metadata": {"raw": "rate-limited upstream"}}},
     AIUnavailableError),
    (502, {"error": {"message": "Bad gateway"}}, AIUnavailableError),
    (401, {"error": {"message": "No auth credentials found"}}, AIServiceError),
    (400, {"error": {"message": "Bad request"}}, AIServiceError),
    (200, {"error": {"message": "Provider returned error", "code": 429}}, AIUnavailableError),
    (200, {"choices": []}, AIServiceError),
    (200, completion(content=""), AIServiceError),
    (200, "not json at all", AIServiceError),
])
async def test_api_errors_raise(fake, status, body, exc):
    fake.reply = (status, body)
    client = client_for(fake)
    try:
        with pytest.raises(exc):
            await client.chat([{"role": "user", "content": "hi"}])
    finally:
        await client.close()
    assert len(fake.requests) == 1  # no automatic retries against the free tier


async def test_timeout_is_unavailable(fake):
    fake.delay = 1.0
    client = client_for(fake, timeout=0.2)
    try:
        with pytest.raises(AIUnavailableError, match="timeout"):
            await client.chat([{"role": "user", "content": "hi"}])
    finally:
        await client.close()


def test_key_is_not_in_repr():
    assert FAKE_KEY not in repr(OpenRouterClient(FAKE_KEY, "m"))
    assert FAKE_KEY not in repr(make_settings(ai_provider="openrouter", openrouter_api_key=FAKE_KEY))


# --------------------------------------------------------------------------- #
# AIService with OpenRouter
# --------------------------------------------------------------------------- #
async def test_service_console_gets_both_reasonings_guest_gets_answer(fake, history, menu, caplog):
    caplog.set_level(logging.INFO, logger="qazaq_taste.reasoning")
    client = client_for(fake)
    try:
        reply = await AIService(client, history, menu, make_settings()).answer(1, BILL_Q, "ru")
    finally:
        await client.close()
    assert reply.text == ANSWER and reply.source == "ai"
    assert API_REASONING not in reply.text and BLOCK_REASONING not in reply.text
    assert API_REASONING in caplog.text and BLOCK_REASONING in caplog.text and BANNER_REASONING in caplog.text
    # Python still does the arithmetic and gives it to the model
    assert "TOTAL: 19 250 ₸" in fake.requests[0]["messages"][0]["content"]


async def test_service_answer_without_any_reasoning(fake, history, menu):
    fake.reply = (200, completion(content=ANSWER, reasoning=None))
    client = client_for(fake)
    try:
        reply = await AIService(client, history, menu, make_settings()).answer(1, "Привет", "ru")
    finally:
        await client.close()
    assert reply.text == ANSWER and reply.source == "ai"


async def test_service_api_reasoning_with_untagged_content(fake, history, menu):
    fake.reply = (200, completion(content=ANSWER))  # model ignored the tags, API still sent reasoning
    client = client_for(fake)
    try:
        reply = await AIService(client, history, menu, make_settings()).answer(1, "Привет", "ru")
    finally:
        await client.close()
    assert reply.text == ANSWER and API_REASONING not in reply.text


async def test_service_429_gives_polite_fallback_without_details(fake, history, menu):
    fake.reply = (429, {"error": {"message": "Provider returned error", "metadata": {"raw": "rate-limited"}}})
    client = client_for(fake)
    try:
        reply = await AIService(client, history, menu, make_settings()).answer(1, BILL_Q, "ru")
    finally:
        await client.close()
    assert reply.source == "fallback"
    for leaked in ("429", "rate", "OpenRouter", "Provider", FAKE_KEY):
        assert leaked not in reply.text
    assert "Итого: 19 250 ₸" in reply.text  # the fallback still answers with the Python bill


# --------------------------------------------------------------------------- #
# Through the real aiogram Dispatcher: Telegram receives ONLY the answer
# --------------------------------------------------------------------------- #
async def _send(fake, text: str, tmp_path, caplog=None):
    settings = make_settings(ai_provider="openrouter", openrouter_api_key=FAKE_KEY,
                             bookings_csv=str(tmp_path / "b.csv"))
    services = build_services(settings, Database("sqlite://"))
    await services.llm.close()
    services.llm.base_url = fake.base_url
    services.users.set_language(USER.id, "ru")
    session = MockSession()
    bot = Bot(FAKE_TOKEN, session=session)
    msg = Message(message_id=1, date=datetime.now(), chat=CHAT, from_user=USER, text=text)
    await build_dispatcher(services).feed_update(bot, Update(update_id=1, message=msg))
    await services.llm.close()
    return services, session.sent_texts()


async def test_telegram_gets_only_answer_with_openrouter(fake, tmp_path, caplog):
    caplog.set_level(logging.INFO)
    services, sent = await _send(fake, BILL_Q, tmp_path)
    assert isinstance(services.llm, OpenRouterClient) and services.ai.client is services.llm
    assert sent[-1] == ANSWER
    for text in sent:
        assert API_REASONING not in text and BLOCK_REASONING not in text
        assert "<think>" not in text and "размышление" not in text.lower()
    assert API_REASONING in caplog.text and BLOCK_REASONING in caplog.text   # console has it
    assert FAKE_KEY not in caplog.text                                     # never the key


async def test_telegram_gets_fallback_on_429(fake, tmp_path, caplog):
    caplog.set_level(logging.INFO)
    fake.reply = (429, {"error": {"message": "Provider returned error", "metadata": {"raw": "rate-limited upstream"}}})
    _, sent = await _send(fake, "Что посоветуете на ужин?", tmp_path)
    assert "AI-консультант сейчас недоступен" in sent[-1]
    assert "429" not in sent[-1] and "rate" not in sent[-1]
    assert FAKE_KEY not in caplog.text


async def test_booking_extraction_works_through_openrouter(fake, tmp_path):
    tomorrow = (datetime.now() + timedelta(days=1)).date().isoformat()
    fake.reply = (200, completion(content=json.dumps({
        "intent": "booking", "date": tomorrow, "time": None, "guests": 4, "name": None, "phone": None,
        "missing": ["time", "name", "phone"]}), reasoning="should not be used"))
    _, sent = await _send(fake, "Хочу забронировать столик на завтра на четверых", tmp_path)
    assert sent[-1] == "На какое время хотите забронировать столик?"
    assert fake.requests[-1]["reasoning"] == {"enabled": False}


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
@pytest.fixture
def clean_env(monkeypatch):
    for name in ("AI_PROVIDER", "OPENROUTER_API_KEY", "OPENROUTER_MODEL", "OPENROUTER_REASONING", "BOT_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def test_provider_auto_selection(clean_env, tmp_path):
    assert load_settings(tmp_path / "none.env").ai_provider == "ollama"
    clean_env.setenv("OPENROUTER_API_KEY", FAKE_KEY)
    s = load_settings(tmp_path / "none.env")
    assert s.ai_provider == "openrouter" and s.openrouter_model == "nvidia/nemotron-3.5-super-vl:free"
    clean_env.setenv("AI_PROVIDER", "ollama")
    assert load_settings(tmp_path / "none.env").ai_provider == "ollama"


def test_openrouter_without_key_is_a_config_error(clean_env, tmp_path):
    from bot.config import ConfigError
    clean_env.setenv("AI_PROVIDER", "openrouter")
    with pytest.raises(ConfigError, match="OPENROUTER_API_KEY"):
        load_settings(tmp_path / "none.env")
