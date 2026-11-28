"""End-to-end dialog tests: real aiogram Dispatcher + routers + FSM, with a mocked
Telegram session (no network, no real token)."""

from __future__ import annotations

from datetime import datetime, timedelta
from itertools import count

import pytest
from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.methods import AnswerCallbackQuery, EditMessageReplyMarkup, EditMessageText, SendMessage
from aiogram.types import CallbackQuery, Chat, Message, Update, User

from bot.container import build_services
from bot.database.database import Database
from bot.database.models import Booking, EventRequest
from bot.main import build_dispatcher
from tests.conftest import make_settings

FAKE_TOKEN = "123456789:" + "T" * 35
USER = User(id=777, is_bot=False, first_name="Aigerim", language_code="ru")
CHAT = Chat(id=777, type="private")
_ids = count(1)


class MockSession(BaseSession):
    def __init__(self) -> None:
        super().__init__()
        self.requests: list = []

    async def make_request(self, bot, method, timeout=None):
        self.requests.append(method)
        if isinstance(method, SendMessage):
            return Message(message_id=next(_ids), date=datetime.now(), chat=CHAT, text=method.text)
        if isinstance(method, (EditMessageText, EditMessageReplyMarkup, AnswerCallbackQuery)):
            return True
        return True

    async def close(self):
        pass

    async def stream_content(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError
        yield b""

    def sent_texts(self) -> list[str]:
        return [m.text for m in self.requests if isinstance(m, SendMessage)]


@pytest.fixture
async def env(tmp_path):
    db = Database("sqlite://")
    services = build_services(make_settings(bookings_csv=str(tmp_path / "bookings.csv")), db)
    session = MockSession()
    bot = Bot(FAKE_TOKEN, session=session)
    dp = build_dispatcher(services)

    async def send(text: str):
        msg = Message(message_id=next(_ids), date=datetime.now(), chat=CHAT, from_user=USER, text=text)
        await dp.feed_update(bot, Update(update_id=next(_ids), message=msg))

    async def press(data: str):
        msg = Message(message_id=next(_ids), date=datetime.now(), chat=CHAT, text="…")
        cb = CallbackQuery(id=str(next(_ids)), from_user=USER, chat_instance="ci", message=msg, data=data)
        await dp.feed_update(bot, Update(update_id=next(_ids), callback_query=cb))

    yield services, session, send, press
    await services.ollama.close()
    db.dispose()


async def test_start_language_and_main_menu(env):
    services, session, send, press = env
    await send("/start")
    assert "Выберите язык" in session.sent_texts()[-1]
    await press("lang:kk")
    assert services.users.get_language(USER.id) == "kk"
    assert "Qazaq Taste" in session.sent_texts()[-1]
    keyboard = session.requests[-1].reply_markup.keyboard
    assert keyboard[0][0].text == "🍽 Мейрамхана мәзірі"


async def test_full_booking_flow_saves_request(env):
    services, session, send, press = env
    services.users.set_language(USER.id, "ru")
    visit = (datetime.now() + timedelta(days=3)).strftime("%d.%m.%Y")
    for text in ["📅 Забронировать столик", "1", "Айгерим", "+7 701 123 45 67", "01.01.2020", visit, "03:00",
                 "19:00", "50", "4", "➡️ Пропустить"]:
        await send(text)
    texts = session.sent_texts()
    assert any("только буквы" in t for t in texts)          # invalid name rejected
    assert any("уже прошла" in t for t in texts)            # past date rejected
    assert any("Укажите другое время" in t for t in texts)  # time outside opening hours
    assert any("Максимум 20" in t for t in texts)           # too many guests
    assert "Проверьте данные" in texts[-1]
    await press("book:confirm")
    final = session.sent_texts()[-1]
    assert "Заявка на бронирование принята" in final and "не подтверждённая бронь" in final
    with services.db.session() as s:
        booking = s.query(Booking).one()
        assert booking.phone == "+77011234567" and booking.guests == 4 and booking.status == "pending"
        assert booking.code in final


async def test_text_at_confirm_step_points_to_inline_buttons(env):
    """Regression: pressing the leftover "Skip" button at the confirmation step must not leave the flow."""
    services, session, send, press = env
    services.users.set_language(USER.id, "ru")
    visit = (datetime.now() + timedelta(days=2)).strftime("%d.%m.%Y")
    for text in ["📅 Забронировать столик", "Жомарт", "+7 701 000 00 00", visit, "17:00", "2", "➡️ Пропустить"]:
        await send(text)
    keyboard = session.requests[-2].reply_markup.keyboard  # "almost done" message replaces the Skip keyboard
    assert all(btn.text != "➡️ Пропустить" for row in keyboard for btn in row)
    await send("➡️ Пропустить")
    assert "«✅ Подтвердить»" in session.sent_texts()[-1]
    await press("book:confirm")
    assert "Заявка на бронирование принята" in session.sent_texts()[-1]


async def test_stale_skip_outside_flow_shows_main_menu(env):
    services, session, send, press = env
    services.users.set_language(USER.id, "ru")
    await send("➡️ Пропустить")
    assert session.sent_texts()[-1] == "Главное меню 👇"


async def test_cancel_in_the_middle_of_booking(env):
    services, session, send, press = env
    services.users.set_language(USER.id, "en")
    await send("📅 Book a table")
    await send("John")
    await send("❌ Cancel")
    assert session.sent_texts()[-1] == "Cancelled."
    with services.db.session() as s:
        assert s.query(Booking).count() == 0


async def test_main_button_interrupts_flow(env):
    services, session, send, press = env
    services.users.set_language(USER.id, "ru")
    await send("/booking")
    await send("📍 Контакты")
    assert "+7 (727) 000-00-00" in session.sent_texts()[-1]
    await send("Айгерим")  # no longer inside the booking flow -> goes to AI (fallback)
    assert "AI-консультант сейчас недоступен" in session.sent_texts()[-1]


async def test_event_flow_creates_proposal(env):
    services, session, send, press = env
    services.users.set_language(USER.id, "ru")
    event_date = (datetime.now() + timedelta(days=20)).strftime("%d.%m.%Y")
    await send("🎉 Организовать мероприятие")
    await press("evtype:corporate")
    await send("25")
    await send(event_date)
    await press("evbudget:total")
    await send("400 000")
    await send("нужна домбра")
    await send("➡️ Пропустить")
    texts = session.sent_texts()
    proposal = texts[-2]
    assert "КОММЕРЧЕСКОЕ ПРЕДЛОЖЕНИЕ" in proposal and "Корпоратив" in proposal and "домбра" in proposal.lower()
    assert "Заявка на мероприятие сохранена" in texts[-1]
    with services.db.session() as s:
        req = s.query(EventRequest).one()
        assert req.guests == 25 and req.budget_per_person == 16000
        assert f"{req.total_price:,}".replace(",", " ") in proposal


async def test_budget_flow(env):
    services, session, send, press = env
    services.users.set_language(USER.id, "en")
    await send("💰 Budget calculator")
    await send("4")
    await send("40000")
    result = session.sent_texts()[-1]
    assert "Budget estimate" in result and "Total" in result


async def test_menu_browsing(env):
    services, session, send, press = env
    services.users.set_language(USER.id, "ru")
    await send("/menu")
    assert "Меню Qazaq Taste" in session.sent_texts()[-1]
    await press("cat:national")
    edit = [r for r in session.requests if isinstance(r, EditMessageText)][-1]
    assert "Бешбармак" in edit.text
    await press("dish:beshbarmak")
    edit = [r for r in session.requests if isinstance(r, EditMessageText)][-1]
    assert "5 900 ₸" in edit.text and "Состав" in edit.text


async def test_ai_mode_uses_fallback_when_ollama_down(env):
    services, session, send, press = env
    services.users.set_language(USER.id, "ru")
    await send("🤖 AI-консультант")
    assert "AI-консультант Qazaq Taste" in session.sent_texts()[-1]
    await send("Сколько стоит бешбармак?")
    reply = session.requests[-1]
    assert reply.parse_mode is None  # model/fallback output is never parsed as HTML
    assert "5 900 ₸" in reply.text


# --------------------------------------------------------------------------- #
# HW9: booking from free text via JSON extraction
# --------------------------------------------------------------------------- #
import json  # noqa: E402

from bot.database.csv_store import BookingsCsv  # noqa: E402


class ScriptedLLM:
    """Plays the role of Ollama for the extraction call: returns prepared answers in order."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = 0

    async def chat(self, messages, json_mode=False, temperature=None, reasoning=None):
        self.calls += 1
        return self.answers.pop(0)


def j(**fields) -> str:
    base = {"intent": "booking", "date": None, "time": None, "guests": None, "name": None, "phone": None}
    base.update(fields)
    base["missing"] = [k for k in ("date", "time", "guests", "name", "phone") if base[k] is None]
    return json.dumps(base, ensure_ascii=False)


def csv_rows(services) -> list[dict]:
    return BookingsCsv(services.settings.bookings_csv).read_all()


async def test_json_booking_full_flow_with_llm(env):
    services, session, send, press = env
    services.users.set_language(USER.id, "ru")
    tomorrow = (services.booking.today() + timedelta(days=1)).isoformat()
    services.extractor.client = ScriptedLLM(
        "Конечно! Вот JSON: {...}",                 # invalid -> one retry
        j(date=tomorrow, guests=4),                 # time, name, phone missing
        j(time="19:00"),
        j(name="Жомарт"),
        j(phone="+77011234567"),
    )
    await send("Хочу забронировать столик на завтра на четверых")
    assert services.extractor.client.calls == 2      # first answer invalid -> exactly one retry
    assert session.sent_texts()[-1] == "На какое время хотите забронировать столик?"  # ONE question
    await send("19:00")
    assert session.sent_texts()[-1] == "Как к вам обращаться?"
    await send("Жомарт")
    assert session.sent_texts()[-1].startswith("Укажите, пожалуйста, номер телефона")
    await send("+7 701 123 45 67")
    summary = session.sent_texts()[-1]
    for part in ("Бронирование:", "Время: 19:00", "Гостей: 4", "Имя: Жомарт", "Телефон: +77011234567",
                 "Подтверждаете?"):
        assert part in summary
    assert csv_rows(services) == []                  # nothing saved before confirmation
    await send("Подтверждаю бронь")
    assert "Заявка на бронирование принята" in session.sent_texts()[-1]
    rows = csv_rows(services)
    assert len(rows) == 1
    assert {k: rows[0][k] for k in ("intent", "date", "time", "guests", "name", "phone")} == {
        "intent": "booking", "date": tomorrow, "time": "19:00", "guests": "4", "name": "Жомарт",
        "phone": "+77011234567"}
    with services.db.session() as s:
        assert s.query(Booking).count() == 1


async def test_json_booking_two_invalid_answers_ask_to_repeat(env):
    services, session, send, press = env
    services.users.set_language(USER.id, "ru")
    services.extractor.client = ScriptedLLM("oops", "still not json")
    await send("Забронируйте столик на завтра")
    assert "Не удалось разобрать заявку" in session.sent_texts()[-1]
    assert services.extractor.client.calls == 2


async def test_json_booking_without_ollama_validation_and_rejection(env):
    """Ollama is down in tests (closed port) -> the rule-based extractor is used."""
    services, session, send, press = env
    services.users.set_language(USER.id, "ru")
    await send("Хочу забронировать столик на 01.01.2020 в 03:00 на 4 человек")
    assert "Эта дата уже прошла" in session.sent_texts()[-1]     # past date rejected, asked again
    day = (services.booking.today() + timedelta(days=3)).strftime("%d.%m.%Y")
    await send(day)
    assert "Укажите другое время" in session.sent_texts()[-1]    # 03:00 outside opening hours
    await send("19:00")
    assert session.sent_texts()[-1] == "Как к вам обращаться?"
    await send("Жомарт")
    await send("12345")
    assert "11 цифр" in session.sent_texts()[-1]                 # bad phone rejected
    await send("8 701 123 45 67")
    assert "Подтверждаете?" in session.sent_texts()[-1]
    await send("время 20:00")                                    # correction at the confirm step
    assert "Время: 20:00" in session.sent_texts()[-1]
    await send("нет")
    assert "не отправлена" in session.sent_texts()[-1]
    assert csv_rows(services) == []                              # rejected -> nothing saved


async def test_non_booking_question_still_goes_to_ai(env):
    services, session, send, press = env
    services.users.set_language(USER.id, "ru")
    await send("Сколько стоит бешбармак?")
    assert "5 900 ₸" in session.sent_texts()[-1]


# ---- regression: booking inquiry goes to the AI consultant, request starts the flow ---------
@pytest.mark.parametrize("text", [
    "Как забронировать столик?",
    "Вы принимаете бронирования?",
    "До скольки можно забронировать?",
    "Как забронировать столик на пятницу вечером и до скольки вы работаете?",
])
async def test_booking_inquiry_goes_to_ai_consultant(env, text):
    services, session, send, press = env
    services.users.set_language(USER.id, "ru")
    services.extractor.client = ScriptedLLM()  # would fail if called: no prepared answers
    await send(text)
    reply = session.sent_texts()[-1]
    assert "На какую дату" not in reply                         # booking flow NOT started
    assert "AI-консультант сейчас недоступен" in reply          # answered by the consultant (fallback)
    assert services.extractor.client.calls == 0                 # no extraction call for an inquiry
    with services.db.session() as s:
        assert s.query(Booking).count() == 0


async def test_booking_hours_question_gets_hours_in_fallback(env):
    services, session, send, press = env
    services.users.set_language(USER.id, "ru")
    await send("Как забронировать столик на пятницу вечером и до скольки вы работаете?")
    reply = session.sent_texts()[-1]
    assert "Пт–Сб: 11:00–00:00" in reply and "Забронировать столик" in reply


@pytest.mark.parametrize("text,first_question", [
    ("Хочу забронировать столик", "На какую дату хотите забронировать столик?"),
    ("Забронируйте столик на завтра на 4 человек", "На какое время хотите забронировать столик?"),
])
async def test_booking_request_starts_the_flow(env, text, first_question):
    services, session, send, press = env
    services.users.set_language(USER.id, "ru")
    await send(text)
    assert session.sent_texts()[-1].startswith(first_question)


async def test_inquiry_inside_ai_mode_also_goes_to_ai(env):
    services, session, send, press = env
    services.users.set_language(USER.id, "ru")
    await send("🤖 AI-консультант")
    await send("Вы принимаете бронирования?")
    assert "На какую дату" not in session.sent_texts()[-1]
    await send("Хочу забронировать столик на завтра")
    assert session.sent_texts()[-1] == "На какое время хотите забронировать столик?"


# --------------------------------------------------------------------------- #
# HW10: Telegram receives ONLY <ответ>; <размышление> stays in the console
# --------------------------------------------------------------------------- #
import logging  # noqa: E402

HW10_REASONING = "Гость спрашивает, как забронировать. Это информационный вопрос, бронирование не запускаю."
HW10_ANSWER = "Оставить заявку можно кнопкой «📅 Забронировать столик». В пятницу мы работаем с 11:00 до 00:00."


class TaggedLLM:
    def __init__(self, reply):
        self.reply = reply
        self.calls = 0

    async def chat(self, messages, json_mode=False, temperature=None, reasoning=None):
        self.calls += 1
        return self.reply


def tagged(reasoning=HW10_REASONING, answer=HW10_ANSWER) -> str:
    return f"<размышление>\n{reasoning}\n</размышление>\n<ответ>\n{answer}\n</ответ>"


async def test_telegram_gets_only_the_answer_and_console_gets_reasoning(env, caplog):
    services, session, send, press = env
    caplog.set_level(logging.INFO, logger="qazaq_taste.reasoning")
    services.users.set_language(USER.id, "ru")
    services.ai.client = TaggedLLM(tagged())
    await send("Как забронировать столик на пятницу вечером и до скольки вы работаете?")
    sent = session.sent_texts()
    assert sent[-1] == HW10_ANSWER                                  # exactly the <ответ> block
    assert all(HW10_REASONING not in t and "размышление" not in t.lower() and "<ответ>" not in t for t in sent)
    assert "========== REASONING ==========" in caplog.text and HW10_REASONING in caplog.text


async def test_ai_mode_also_sends_only_the_answer(env):
    services, session, send, press = env
    services.users.set_language(USER.id, "ru")
    services.ai.client = TaggedLLM(tagged(reasoning="секретный анализ", answer="Бешбармак стоит 5 900 ₸."))
    await send("🤖 AI-консультант")
    await send("Сколько стоит бешбармак?")
    assert session.sent_texts()[-1] == "Бешбармак стоит 5 900 ₸."
    assert not any("секретный анализ" in t for t in session.sent_texts())


async def test_empty_answer_block_sends_fallback_not_reasoning(env):
    services, session, send, press = env
    services.users.set_language(USER.id, "ru")
    services.ai.client = TaggedLLM("<размышление>секретный анализ</размышление><ответ></ответ>")
    await send("Что посоветуете?")
    assert "секретный анализ" not in session.sent_texts()[-1]
    assert "AI-консультант сейчас недоступен" in session.sent_texts()[-1]


async def test_booking_request_still_uses_json_flow_with_reasoning_enabled(env):
    """HW9 booking flow is untouched: the extraction call returns JSON, not the reasoning format."""
    services, session, send, press = env
    services.users.set_language(USER.id, "ru")
    tomorrow = (services.booking.today() + timedelta(days=1)).isoformat()
    services.extractor.client = ScriptedLLM(j(date=tomorrow, guests=4))
    services.ai.client = TaggedLLM(tagged())  # must NOT be used for a booking request
    await send("Хочу забронировать столик на завтра на четверых")
    assert session.sent_texts()[-1] == "На какое время хотите забронировать столик?"
    assert services.ai.client.calls == 0


async def test_late_arrival_question_goes_to_ai_with_python_calculation(env):
    services, session, send, press = env
    services.users.set_language(USER.id, "ru")
    llm = TaggedLLM(tagged(answer="Вы придёте примерно в 19:40 — предупредите ресторан по телефону."))
    services.ai.client = llm
    seen = {}

    async def spy(messages, json_mode=False, temperature=None, reasoning=None):
        seen["system"] = messages[0]["content"]
        return await TaggedLLM.chat(llm, messages)

    llm.chat = spy
    await send("У меня бронь сегодня на 19:00, но я опоздаю минут на 40. Столик за мной сохранится?")
    assert "На какую дату" not in session.sent_texts()[-1]          # not a new booking request
    assert "expected arrival 19:40" in seen["system"]                 # computed by Python, given to the model
    assert session.sent_texts()[-1].startswith("Вы придёте примерно в 19:40")
