"""Wires settings, database, repositories and services together."""

from __future__ import annotations

from dataclasses import dataclass

from bot.config import Settings
from bot.database.csv_store import BookingsCsv
from bot.database.database import Database
from bot.database.repository import BookingRepository, ChatHistoryRepository, EventRepository, UserRepository
from bot.services.ai_service import AIService, OllamaClient
from bot.services.booking_extraction import BookingExtractor
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
    extractor: BookingExtractor
    bookings_csv: BookingsCsv


def build_services(settings: Settings, db: Database | None = None) -> Services:
    db = db or Database(settings.database_url)
    db.create_all()
    menu = MenuService()
    ollama = OllamaClient(
        settings.ollama_url, settings.ollama_model, settings.ollama_timeout,
        settings.ollama_temperature, settings.ollama_num_ctx,
    )
    booking = BookingService(BookingRepository(db), settings.timezone)
    return Services(
        settings=settings,
        db=db,
        users=UserRepository(db),
        menu=menu,
        booking=booking,
        proposals=ProposalService(menu, EventRepository(db)),
        ai=AIService(ollama, ChatHistoryRepository(db), menu, settings),
        ollama=ollama,
        # today's date is taken from the booking clock (Almaty time) on every call
        extractor=BookingExtractor(ollama, today=booking.today),
        bookings_csv=BookingsCsv(settings.bookings_csv),
    )
