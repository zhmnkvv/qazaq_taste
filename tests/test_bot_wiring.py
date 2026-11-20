"""Bot wiring, security of logs and helpers — no Telegram token required."""

import logging

from bot.container import build_services
from bot.database.database import Database
from bot.handlers.ai_chat import split_message
from bot.handlers.common import BUTTON_TO_KEY
from bot.handlers.events import parse_amount, parse_event_guests
from bot.logging_setup import RedactingFilter
from bot.main import build_dispatcher
from bot.texts import TEXTS, normalize_lang
from tests.conftest import make_settings


def test_dispatcher_builds_without_token():
    services = build_services(make_settings(), Database("sqlite://"))
    dp = build_dispatcher(services)
    assert set(dp.resolve_used_update_types()) == {"message", "callback_query"}
    assert dp["services"] is services


def test_all_main_buttons_are_routed_in_every_language():
    for key in ("btn_menu", "btn_booking", "btn_ai", "btn_event", "btn_budget", "btn_contacts", "btn_about"):
        for text in TEXTS[key].values():
            assert BUTTON_TO_KEY[text] == key


def test_log_filter_redacts_token_and_phone():
    record = logging.LogRecord("x", logging.INFO, __file__, 1, "token %s phone %s",
                               ("123456789:" + "A" * 35, "+7 701 123 45 67"), None)
    RedactingFilter().filter(record)
    message = record.getMessage()
    assert "AAAA" not in message and "123 45 67" not in message
    assert "<redacted-token>" in message and "<redacted-phone>" in message


def test_parse_amount():
    assert parse_amount("150 000") == 150000
    assert parse_amount("150000 ₸") == 150000
    assert parse_amount("50k") == 50000
    assert parse_amount("abc") is None
    assert parse_amount("-5") is None
    assert parse_amount("0") is None


def test_parse_event_guests():
    assert parse_event_guests("25") == 25
    assert parse_event_guests("0") is None
    assert parse_event_guests("1000") is None


def test_split_message():
    parts = split_message("line\n" * 2000, limit=1000)
    assert all(len(p) <= 1000 for p in parts)
    assert "".join(parts).count("line") == 2000


def test_normalize_lang():
    assert normalize_lang("kk") == "kk"
    assert normalize_lang("ru-RU") == "ru"
    assert normalize_lang("de") == "en"
    assert normalize_lang(None) == "ru"
