"""Middleware that resolves the user's interface language."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User

from bot.texts import normalize_lang

logger = logging.getLogger(__name__)


class LanguageMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("event_from_user")
        services = data.get("services")
        lang = normalize_lang(user.language_code if user else None)
        if user and services:
            try:
                stored = services.users.get_language(user.id)
                if stored:
                    lang = stored
            except Exception:  # database problems must not break the update
                logger.exception("Could not load user language")
        data["lang"] = lang
        return await handler(event, data)
