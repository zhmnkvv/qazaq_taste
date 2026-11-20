"""Bot entry point."""

from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError, TelegramUnauthorizedError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from bot.config import ConfigError, load_settings
from bot.container import Services, build_services
from bot.handlers import build_root_router
from bot.handlers.common import on_error
from bot.logging_setup import setup_logging
from bot.middlewares import LanguageMiddleware
from bot.telegram_retry import RetryMiddleware

logger = logging.getLogger("qazaq_taste")

COMMANDS = {
    "ru": [("start", "Главное меню"), ("menu", "Меню ресторана"), ("booking", "Забронировать столик"),
           ("ai", "AI-консультант"), ("event", "Организовать мероприятие"), ("budget", "Рассчитать бюджет"),
           ("help", "Помощь"), ("cancel", "Отменить действие"), ("language", "Сменить язык")],
    "kk": [("start", "Басты мәзір"), ("menu", "Мейрамхана мәзірі"), ("booking", "Үстел брондау"),
           ("ai", "AI-кеңесші"), ("event", "Іс-шара ұйымдастыру"), ("budget", "Бюджетті есептеу"),
           ("help", "Анықтама"), ("cancel", "Әрекетті болдырмау"), ("language", "Тілді ауыстыру")],
    "en": [("start", "Main menu"), ("menu", "Restaurant menu"), ("booking", "Book a table"),
           ("ai", "AI consultant"), ("event", "Organize an event"), ("budget", "Budget calculator"),
           ("help", "Help"), ("cancel", "Cancel current action"), ("language", "Change language")],
}


def build_dispatcher(services: Services) -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    dp["services"] = services
    dp.message.outer_middleware(LanguageMiddleware())
    dp.callback_query.outer_middleware(LanguageMiddleware())
    dp.include_router(build_root_router())
    dp.errors.register(on_error)
    return dp


async def set_commands(bot: Bot) -> None:
    for lang, commands in COMMANDS.items():
        cmds = [BotCommand(command=c, description=d) for c, d in commands]
        try:
            await bot.set_my_commands(cmds, language_code=None if lang == "ru" else lang)
        except TelegramAPIError as exc:
            logger.warning("Could not set commands for %s: %s", lang, type(exc).__name__)


async def main() -> int:
    try:
        settings = load_settings()
    except ConfigError as exc:
        setup_logging()
        logger.error("Configuration error: %s", exc)
        return 1
    setup_logging(settings.log_level)

    try:
        token = settings.require_token()
    except ConfigError as exc:
        logger.error("%s", exc)
        logger.error("See README.md -> 'Create a Telegram bot with BotFather'.")
        return 1

    services = build_services(settings)
    if await services.ollama.is_available():
        logger.info("Ollama is available, model: %s", settings.ollama_model)
    else:
        logger.warning(
            "Ollama or model '%s' is not available at %s. The bot will run with the rule-based fallback. "
            "Install Ollama and run: ollama pull %s", settings.ollama_model, settings.ollama_url,
            settings.ollama_model,
        )

    # Shorter per-request timeout + retries: on a slow connection a message is re-sent
    # instead of waiting 60 s and failing (polling uses its own, longer timeout).
    session = AiohttpSession(timeout=20)
    session.middleware(RetryMiddleware())
    bot = Bot(token=token, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = build_dispatcher(services)
    try:
        me = await bot.get_me()
        logger.info("Bot @%s started. Press Ctrl+C to stop.", me.username)
        await set_commands(bot)
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except TelegramUnauthorizedError:
        logger.error("Telegram rejected the token (Unauthorized). Check BOT_TOKEN in .env.")
        return 1
    finally:
        await services.ollama.close()
        await bot.session.close()
        services.db.dispose()
    return 0


def run() -> None:
    try:
        code = asyncio.run(main())
    except KeyboardInterrupt:
        code = 0
    sys.exit(code)


if __name__ == "__main__":
    run()
