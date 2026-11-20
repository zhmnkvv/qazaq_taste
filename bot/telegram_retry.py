"""Retry Telegram API calls on network errors (slow / unstable connection)."""

from __future__ import annotations

import asyncio
import logging

from aiogram.client.session.middlewares.base import BaseRequestMiddleware, NextRequestMiddlewareType
from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import GetUpdates, TelegramMethod
from aiogram.methods.base import Response, TelegramType

logger = logging.getLogger(__name__)


class RetryMiddleware(BaseRequestMiddleware):
    """Repeats a failed request a few times with a growing pause.

    getUpdates is skipped: the polling loop already has its own back-off.
    """

    def __init__(self, attempts: int = 3, base_delay: float = 1.0) -> None:
        self.attempts = attempts
        self.base_delay = base_delay

    async def __call__(self, make_request: NextRequestMiddlewareType[TelegramType], bot,
                       method: TelegramMethod[TelegramType]) -> Response[TelegramType]:
        if isinstance(method, GetUpdates):
            return await make_request(bot, method)
        for attempt in range(1, self.attempts + 1):
            try:
                return await make_request(bot, method)
            except TelegramNetworkError:
                if attempt == self.attempts:
                    raise
                delay = self.base_delay * attempt
                logger.warning("Telegram network error on %s, retry %s/%s in %.0fs",
                               type(method).__name__, attempt, self.attempts - 1, delay)
                await asyncio.sleep(delay)
        raise RuntimeError("unreachable")  # pragma: no cover
