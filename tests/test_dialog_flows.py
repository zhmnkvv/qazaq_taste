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
async def env():
    db = Database("sqlite://")
    services = build_services(make_settings(), db)
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
