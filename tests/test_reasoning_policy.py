"""HW11: reasoning is decided per request — ON for booking and calculations, OFF for simple questions.

No real API is called: a fake model records the `reasoning` flag, and a local aiohttp server plays
OpenRouter to check what is actually sent in the request body.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta

import pytest
from aiogram import Bot
from aiogram.types import Message, Update
from aiohttp import web
from aiohttp.test_utils import TestServer

from bot.container import build_services
from bot.database.database import Database
from bot.main import build_dispatcher
from bot.services.ai_service import AIService, load_system_prompt, without_reasoning_format
from bot.services.booking_extraction import BookingExtractor
from bot.services.calculations import calculate
from bot.services.menu_service import MenuService
from bot.services.openrouter_client import OpenRouterClient
from bot.services.reasoning_policy import BOOKING_EXTRACTION, decide_reasoning
from tests.conftest import make_settings
from tests.test_dialog_flows import CHAT, FAKE_TOKEN, USER, MockSession

SAT = date(2026, 11, 28)
MENU = MenuService()
NEW_RULE = "Never say a manager will prepare the proposal"
FAKE_KEY = "sk-or-v1-" + "a" * 64  # format-valid, not a real key

SIMPLE = ["Привет", "Спасибо!", "Салем", "Hello", "Кто вы?"]
MENU_Q = ["Что такое бешбармак?", "Сколько стоит плов?", "Есть ли вегетарианские блюда?",
          "Что входит в куырдак?", "Расскажите про кумыс"]
HOURS_Q = ["До скольки вы работаете в субботу?", "Во сколько вы открываетесь?", "Где вы находитесь?"]
BOOKING_Q = ["Хочу забронировать столик на завтра", "Как забронировать столик?", "Вы принимаете бронирования?",
             "У меня бронь на 19:00, я опоздаю минут на 40"]
CALC_Q = ["Посчитайте счёт: 2 бешбармака, 3 айрана и чай", "Нас будет 35 человек, поместимся в VIP-зал?",
          "Что взять на ужин, чтобы уложиться в 6000 тенге?"]


def decide(text):
    return decide_reasoning(text, calculate(text, MENU, SAT))


# --------------------------------------------------------------------------- #
# 1-4. The policy itself
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("text", SIMPLE)
def test_simple_question_reasoning_off(text):
    assert decide(text).enabled is False


@pytest.mark.parametrize("text", MENU_Q + HOURS_Q)
def test_menu_and_hours_questions_reasoning_off(text):
    assert decide(text).enabled is False


@pytest.mark.parametrize("text", BOOKING_Q)
def test_booking_reasoning_on(text):
    decision = decide(text)
    assert decision.enabled is True
    assert decision.reason in {"booking question", "late arrival computed by Python"}


def test_bill_calculation_reasoning_on():
    decision = decide("Посчитайте счёт: 2 бешбармака, 3 айрана и чай")
    assert decision.enabled is True and decision.reason == "bill calculated by Python"


@pytest.mark.parametrize("text,reason", [
    ("Нас будет 35 человек, поместимся в VIP-зал?", "guest count checked by Python"),
    ("Что взять на ужин, чтобы уложиться в 6000 тенге?", "money / budget question"),
])
def test_other_calculations_reasoning_on(text, reason):
    assert decide(text) == decide_reasoning(text, calculate(text, MENU, SAT))
    assert decide(text).enabled is True and decide(text).reason == reason


def test_booking_extraction_is_always_on():
    assert BOOKING_EXTRACTION.enabled is True


# --------------------------------------------------------------------------- #
# AIService: the decision reaches the model call and the prompt
# --------------------------------------------------------------------------- #
class RecordingModel:
    def __init__(self, reply="Ответ."):
        self.reply = reply
        self.calls: list[dict] = []

    async def chat(self, messages, json_mode=False, temperature=None, reasoning=None):
        self.calls.append({"messages": messages, "reasoning": reasoning, "json_mode": json_mode})
        return self.reply


@pytest.mark.parametrize("text", SIMPLE[:2] + MENU_Q[:2] + HOURS_Q[:1])
async def test_service_simple_and_menu_questions_off(history, menu, text):
    model = RecordingModel()
    reply = await AIService(model, history, menu, make_settings()).answer(1, text, "ru")
    call = model.calls[0]
    assert call["reasoning"] is False and reply.reasoning_enabled is False
    assert "18. REASONING FORMAT" not in call["messages"][0]["content"]      # prompt without section 18
    assert "<размышление>" not in call["messages"][-1]["content"]            # no format in the reminder


@pytest.mark.parametrize("text", BOOKING_Q[1:3] + CALC_Q)
async def test_service_booking_and_calculations_on(history, menu, text):
    model = RecordingModel("<размышление>анализ</размышление><ответ>Ответ.</ответ>")
    reply = await AIService(model, history, menu, make_settings()).answer(1, text, "ru")
    call = model.calls[0]
    assert call["reasoning"] is True and reply.reasoning_enabled is True
    assert "18. REASONING FORMAT" in call["messages"][0]["content"]
    assert reply.text == "Ответ."


async def test_bill_numbers_still_come_from_python(history, menu):
    model = RecordingModel("<ответ>Итого 19 250 ₸.</ответ>")
    await AIService(model, history, menu, make_settings()).answer(
        1, "Посчитайте счёт: 2 бешбармака, 3 айрана, 1 чак-чак и чай по-казахски", "ru")
    assert "TOTAL: 19 250 ₸" in model.calls[0]["messages"][0]["content"]


async def test_booking_extractor_asks_for_reasoning():
    model = RecordingModel(json.dumps({"intent": "booking", "date": None, "time": None, "guests": None,
                                       "name": None, "phone": None, "missing": []}))
    result = await BookingExtractor(model, today=lambda: SAT).extract("Хочу забронировать столик")
    assert result.status == "ok"
    assert model.calls[0]["reasoning"] is True and model.calls[0]["json_mode"] is True


# --------------------------------------------------------------------------- #
# 6. System prompt: the HW11 rule
# --------------------------------------------------------------------------- #
def test_system_prompt_has_the_immediate_proposal_rule():
    prompt = load_system_prompt()
    assert "The bot shows the calculated proposal to the guest immediately in the chat" in prompt
    assert NEW_RULE in prompt
    section8 = prompt[prompt.index("8. EVENT MANAGEMENT"):prompt.index("9. COMMERCIAL PROPOSALS")]
    assert NEW_RULE in section8                                   # in the event section
    assert NEW_RULE in without_reasoning_format(prompt)           # also when reasoning is OFF


# --------------------------------------------------------------------------- #
# OpenRouter body + Telegram: reasoning flag sent correctly, never shown to the guest
# --------------------------------------------------------------------------- #
class FakeOpenRouter:
    def __init__(self):
        self.bodies: list[dict] = []
        self.replies: list[dict] = []

    async def chat(self, request):
        body = await request.json()
        self.bodies.append(body)
        if body.get("response_format"):  # JSON booking extraction
            content = json.dumps({"intent": "booking", "date": (datetime.now() + timedelta(days=1)).date().isoformat(),
                                  "time": None, "guests": 4, "name": None, "phone": None,
                                  "missing": ["time", "name", "phone"]})
            message = {"content": content, "reasoning": "EXTRACTION-REASONING: guest wants tomorrow, 4 people."}
        elif body["reasoning"]["enabled"]:
            message = {"content": "<размышление>АНАЛИЗ-СЧЁТА</размышление><ответ>Итого: 19 250 ₸.</ответ>",
                       "reasoning": "API-REASONING-ON"}
        else:
            message = {"content": "Бешбармак стоит 5 900 ₸."}
        return web.json_response({"choices": [{"message": message, "finish_reason": "stop"}],
                                  "usage": {"completion_tokens": 10}})


@pytest.fixture
async def openrouter():
    state = FakeOpenRouter()
    app = web.Application()
    app.router.add_post("/api/v1/chat/completions", state.chat)
    server = TestServer(app)
    await server.start_server()
    state.base_url = str(server.make_url("/api/v1"))
    yield state
    await server.close()


async def send(openrouter, text, tmp_path):
    settings = make_settings(ai_provider="openrouter", openrouter_api_key=FAKE_KEY, bookings_csv=str(tmp_path / "b.csv"))
    services = build_services(settings, Database("sqlite://"))
    services.llm.base_url = openrouter.base_url
    services.users.set_language(USER.id, "ru")
    session = MockSession()
    msg = Message(message_id=1, date=datetime.now(), chat=CHAT, from_user=USER, text=text)
    await build_dispatcher(services).feed_update(Bot(FAKE_TOKEN, session=session), Update(update_id=1, message=msg))
    await services.llm.close()
    return session.sent_texts()


async def test_openrouter_simple_question_sends_reasoning_off(openrouter, tmp_path):
    sent = await send(openrouter, "Сколько стоит бешбармак?", tmp_path)
    assert openrouter.bodies[-1]["reasoning"] == {"enabled": False}
    assert sent[-1] == "Бешбармак стоит 5 900 ₸."


async def test_openrouter_bill_sends_reasoning_on_and_telegram_gets_only_answer(openrouter, tmp_path, caplog):
    caplog.set_level(logging.INFO)
    sent = await send(openrouter, "Посчитайте счёт: 2 бешбармака, 3 айрана, 1 чак-чак и чай по-казахски", tmp_path)
    assert openrouter.bodies[-1]["reasoning"] == {"enabled": True}
    assert sent[-1] == "Итого: 19 250 ₸."
    for text in sent:  # 5. Telegram never receives reasoning
        assert "АНАЛИЗ-СЧЁТА" not in text and "API-REASONING-ON" not in text and "<" not in text
    assert "АНАЛИЗ-СЧЁТА" in caplog.text and "API-REASONING-ON" in caplog.text   # console has it


async def test_openrouter_booking_extraction_reasoning_on_json_stays_pure(openrouter, tmp_path, caplog):
    caplog.set_level(logging.INFO)
    sent = await send(openrouter, "Хочу забронировать столик на завтра на четверых", tmp_path)
    body = openrouter.bodies[-1]
    assert body["response_format"] == {"type": "json_object"} and body["reasoning"] == {"enabled": True}
    assert sent[-1] == "На какое время хотите забронировать столик?"   # JSON parsed fine -> one question
    assert all("EXTRACTION-REASONING" not in t for t in sent)         # not in Telegram
    assert "EXTRACTION-REASONING" in caplog.text                       # but visible in the console


async def test_global_switch_turns_reasoning_off_everywhere(openrouter):
    client = OpenRouterClient(FAKE_KEY, "m", base_url=openrouter.base_url, reasoning=False)
    try:
        await client.chat([{"role": "user", "content": "x"}], reasoning=True)
    finally:
        await client.close()
    assert openrouter.bodies[-1]["reasoning"] == {"enabled": False}
