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
from bot.services.openrouter_client import OpenRouterClient
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
    llm: OllamaClient | OpenRouterClient  # the model client shared by the consultant and the extractor
    extractor: BookingExtractor
    bookings_csv: BookingsCsv

    @property
    def ollama(self) -> OllamaClient | OpenRouterClient:
        """Backward-compatible name used before the OpenRouter provider existed."""
        return self.llm


def build_llm(settings: Settings) -> OllamaClient | OpenRouterClient:
    if settings.ai_provider == "openrouter":
        return OpenRouterClient(
            settings.openrouter_api_key, settings.openrouter_model, timeout=settings.openrouter_timeout,
            temperature=settings.ollama_temperature, reasoning=settings.openrouter_reasoning,
            show_reasoning=settings.show_reasoning,
        )
    return OllamaClient(
        settings.ollama_url, settings.ollama_model, settings.ollama_timeout,
        settings.ollama_temperature, settings.ollama_num_ctx,
    )


def build_services(settings: Settings, db: Database | None = None) -> Services:
    db = db or Database(settings.database_url)
    db.create_all()
    menu = MenuService()
    llm = build_llm(settings)
    booking = BookingService(BookingRepository(db), settings.timezone)
    return Services(
        settings=settings,
        db=db,
        users=UserRepository(db),
        menu=menu,
        booking=booking,
        proposals=ProposalService(menu, EventRepository(db)),
        ai=AIService(llm, ChatHistoryRepository(db), menu, settings),
        llm=llm,
        # today's date is taken from the booking clock (Almaty time) on every call
        extractor=BookingExtractor(llm, today=booking.today),
        bookings_csv=BookingsCsv(settings.bookings_csv),
    )
