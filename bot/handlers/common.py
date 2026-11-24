"""Global navigation, /cancel, catch-all and error handling.

``nav_router`` is registered FIRST so that main-menu buttons and commands work
from any FSM state; ``fallback_router`` is registered LAST.
"""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import ErrorEvent, Message

from bot.container import Services
from bot.handlers.ai_chat import ask_ai, start_ai
from bot.handlers.booking import start_booking
from bot.handlers.booking_chat import try_start_booking_chat
from bot.handlers.events import start_budget, start_event
from bot.handlers.menu import show_menu
from bot.handlers.start import show_about, show_contacts
from bot.keyboards.keyboards import main_menu
from bot.texts import TEXTS, all_variants, normalize_lang, tr

logger = logging.getLogger(__name__)

nav_router = Router(name="nav")
fallback_router = Router(name="fallback")

BUTTON_KEYS = ["btn_menu", "btn_booking", "btn_ai", "btn_event", "btn_budget", "btn_contacts", "btn_about",
               "btn_exit_ai"]
BUTTON_TO_KEY = {text: key for key in BUTTON_KEYS for text in TEXTS[key].values()}
CANCEL_TEXTS = all_variants("btn_cancel")


@nav_router.message(Command("cancel"))
@nav_router.message(F.text.func(lambda t: t in CANCEL_TEXTS))
async def cmd_cancel(message: Message, state: FSMContext, lang: str) -> None:
    current = await state.get_state()
    await state.clear()
    key = "cancelled" if current else "nothing_to_cancel"
    await message.answer(tr(key, lang), reply_markup=main_menu(lang))


@nav_router.message(F.text.func(lambda t: t in BUTTON_TO_KEY))
async def on_main_button(message: Message, state: FSMContext, lang: str) -> None:
    await open_section(BUTTON_TO_KEY[message.text], message, state, lang)


@nav_router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext, lang: str) -> None:
    await open_section("btn_menu", message, state, lang)


@nav_router.message(Command("booking"))
async def cmd_booking(message: Message, state: FSMContext, lang: str) -> None:
    await open_section("btn_booking", message, state, lang)


@nav_router.message(Command("event"))
async def cmd_event(message: Message, state: FSMContext, lang: str) -> None:
    await open_section("btn_event", message, state, lang)


@nav_router.message(Command("budget"))
async def cmd_budget(message: Message, state: FSMContext, lang: str) -> None:
    await open_section("btn_budget", message, state, lang)


@nav_router.message(Command("ai"))
async def cmd_ai(message: Message, state: FSMContext, lang: str) -> None:
    await open_section("btn_ai", message, state, lang)


@nav_router.message(Command("reset"))
async def cmd_reset(message: Message, services: Services, lang: str) -> None:
    services.ai.reset(message.from_user.id)
    await message.answer(tr("ai_reset_done", lang))


async def open_section(key: str, message: Message, state: FSMContext, lang: str) -> None:
    if key == "btn_booking":
        await start_booking(message, state, lang)
        return
    if key == "btn_event":
        await start_event(message, state, lang)
        return
    if key == "btn_budget":
        await start_budget(message, state, lang)
        return
    if key == "btn_ai":
        await start_ai(message, state, lang)
        return
    await state.clear()
    if key == "btn_menu":
        await show_menu(message, lang)
    elif key == "btn_contacts":
        await show_contacts(message, lang)
    elif key == "btn_about":
        await show_about(message, lang)
    else:  # btn_exit_ai
        await message.answer(tr("main_menu", lang), reply_markup=main_menu(lang))


SKIP_TEXTS = all_variants("btn_skip")


@fallback_router.message(StateFilter(None), F.text.func(lambda t: t in SKIP_TEXTS))
async def stale_skip(message: Message, lang: str) -> None:
    """A leftover "Skip" button pressed outside of a flow: just show the main menu."""
    await message.answer(tr("main_menu", lang), reply_markup=main_menu(lang))


@fallback_router.message(StateFilter(None), F.text & ~F.text.startswith("/"))
async def free_text(message: Message, state: FSMContext, bot: Bot, services: Services, lang: str) -> None:
    """Free text outside of a flow: a booking request goes to JSON extraction, anything else to the AI."""
    if await try_start_booking_chat(message, state, bot, services, lang):
        return
    await ask_ai(message, bot, services, message.from_user.id, message.text, lang)


@fallback_router.message()
async def unknown(message: Message, lang: str) -> None:
    await message.answer(tr("use_buttons", lang), reply_markup=main_menu(lang))


@fallback_router.callback_query()
async def unknown_callback(callback) -> None:
    await callback.answer()


async def on_error(event: ErrorEvent) -> bool:
    """Global error handler: log without personal data and tell the user politely."""
    exc = event.exception
    update = event.update
    if isinstance(exc, TelegramForbiddenError):
        logger.info("User blocked the bot (update %s)", update.update_id)
        return True
    logger.error("Error while handling update %s: %s", update.update_id, type(exc).__name__, exc_info=exc)
    message = update.message or (update.callback_query.message if update.callback_query else None)
    user = update.message.from_user if update.message else (
        update.callback_query.from_user if update.callback_query else None)
    if message is not None:
        lang = normalize_lang(user.language_code if user else None)
        try:
            await message.answer(tr("error_generic", lang))
        except TelegramAPIError:
            pass
    return True
