"""Wires settings, database, repositories and services together."""

from __future__ import annotations

from dataclasses import dataclass

from bot.config import Settings
from bot.database.database import Database
from bot.database.repository import BookingRepository, ChatHistoryRepository, EventRepository, UserRepository
from bot.services.ai_service import AIService, OllamaClient
from bot.services.booking_service import BookingService
from bot.services.menu_service import MenuService
from bot.services.proposal_service import ProposalService


@dataclass
class Services:
    settings: Settings
    db: Database
    users: UserRepository
    menu: MenuService
    booking: BookingService
    proposals: ProposalService
    ai: AIService
    ollama: OllamaClient


def build_services(settings: Settings, db: Database | None = None) -> Services:
    db = db or Database(settings.database_url)
    db.create_all()
    menu = MenuService()
    ollama = OllamaClient(
        settings.ollama_url, settings.ollama_model, settings.ollama_timeout,
        settings.ollama_temperature, settings.ollama_num_ctx,
    )
    return Services(
        settings=settings,
        db=db,
        users=UserRepository(db),
        menu=menu,
        booking=BookingService(BookingRepository(db), settings.timezone),
        proposals=ProposalService(menu, EventRepository(db)),
        ai=AIService(ollama, ChatHistoryRepository(db), menu, settings),
        ollama=ollama,
    )
