from __future__ import annotations

from datetime import datetime

import pytest

from bot.config import Settings
from bot.database.database import Database
from bot.database.repository import BookingRepository, ChatHistoryRepository, EventRepository
from bot.services.booking_service import BookingService
from bot.services.menu_service import MenuService
from bot.services.proposal_service import ProposalService

# Wednesday, 10 June 2026, 12:00 (Almaty local time)
FIXED_NOW = datetime(2026, 6, 10, 12, 0)


def make_settings(**overrides) -> Settings:
    values = dict(
        bot_token="",
        database_url="sqlite://",
        ollama_url="http://127.0.0.1:9",
        ollama_model="qwen2.5:3b",
        ollama_timeout=3.0,
        ollama_temperature=0.4,
        ollama_num_ctx=8192,
        ai_history_limit=4,
        ai_max_input_chars=1000,
        timezone="Asia/Almaty",
        admin_chat_id=None,
        log_level="INFO",
    )
    values.update(overrides)
    return Settings(**values)


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def db() -> Database:
    database = Database("sqlite://")
    database.create_all()
    yield database
    database.dispose()


@pytest.fixture
def menu() -> MenuService:
    return MenuService()


@pytest.fixture
def booking_service(db) -> BookingService:
    return BookingService(BookingRepository(db), clock=lambda: FIXED_NOW)


@pytest.fixture
def proposal_service(db, menu) -> ProposalService:
    return ProposalService(menu, EventRepository(db))


@pytest.fixture
def history(db) -> ChatHistoryRepository:
    return ChatHistoryRepository(db)
