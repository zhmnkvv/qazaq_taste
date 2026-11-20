"""Repositories: the only place that talks to the database.

All queries go through the SQLAlchemy ORM / expression API with bound
parameters, so user input is never concatenated into SQL (no SQL injection).
"""

from __future__ import annotations

from sqlalchemy import delete, func, select

from bot.database.database import Database
from bot.database.models import Booking, ChatMessage, EventRequest, User

SUPPORTED_LANGUAGES = ("ru", "kk", "en")


class UserRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def get_language(self, telegram_id: int) -> str | None:
        with self.db.session() as s:
            user = s.get(User, telegram_id)
            return user.language if user else None

    def set_language(self, telegram_id: int, language: str) -> None:
        if language not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported language: {language}")
        with self.db.session() as s:
            user = s.get(User, telegram_id)
            if user is None:
                s.add(User(telegram_id=telegram_id, language=language))
            else:
                user.language = language


class BookingRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, booking: Booking) -> Booking:
        with self.db.session() as s:
            s.add(booking)
            s.flush()
            s.refresh(booking)
            return booking

    def code_exists(self, code: str) -> bool:
        with self.db.session() as s:
            return s.scalar(select(func.count()).select_from(Booking).where(Booking.code == code)) > 0

    def get_by_code(self, code: str) -> Booking | None:
        with self.db.session() as s:
            return s.scalar(select(Booking).where(Booking.code == code))

    def list_for_user(self, telegram_id: int, limit: int = 5) -> list[Booking]:
        with self.db.session() as s:
            rows = s.scalars(
                select(Booking)
                .where(Booking.telegram_id == telegram_id)
                .order_by(Booking.created_at.desc())
                .limit(limit)
            )
            return list(rows)


class EventRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, request: EventRequest) -> EventRequest:
        with self.db.session() as s:
            s.add(request)
            s.flush()
            s.refresh(request)
            return request

    def code_exists(self, code: str) -> bool:
        with self.db.session() as s:
            return (
                s.scalar(select(func.count()).select_from(EventRequest).where(EventRequest.code == code)) > 0
            )

    def get_by_code(self, code: str) -> EventRequest | None:
        with self.db.session() as s:
            return s.scalar(select(EventRequest).where(EventRequest.code == code))


class ChatHistoryRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, telegram_id: int, role: str, content: str) -> None:
        if role not in {"user", "assistant"}:
            raise ValueError("role must be 'user' or 'assistant'")
        with self.db.session() as s:
            s.add(ChatMessage(telegram_id=telegram_id, role=role, content=content))

    def last(self, telegram_id: int, limit: int) -> list[dict[str, str]]:
        """Return the last ``limit`` messages in chronological order."""
        if limit <= 0:
            return []
        with self.db.session() as s:
            rows = list(
                s.scalars(
                    select(ChatMessage)
                    .where(ChatMessage.telegram_id == telegram_id)
                    .order_by(ChatMessage.id.desc())
                    .limit(limit)
                )
            )
        rows.reverse()
        return [{"role": r.role, "content": r.content} for r in rows]

    def clear(self, telegram_id: int) -> None:
        with self.db.session() as s:
            s.execute(delete(ChatMessage).where(ChatMessage.telegram_id == telegram_id))

    def prune(self, telegram_id: int, keep: int) -> None:
        """Keep only the newest ``keep`` messages of a user."""
        with self.db.session() as s:
            ids = list(
                s.scalars(
                    select(ChatMessage.id)
                    .where(ChatMessage.telegram_id == telegram_id)
                    .order_by(ChatMessage.id.desc())
                    .offset(keep)
                )
            )
            if ids:
                s.execute(delete(ChatMessage).where(ChatMessage.id.in_(ids)))
