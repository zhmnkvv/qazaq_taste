"""AI consultant chat mode."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.chat_action import ChatActionSender

from bot.container import Services
from bot.handlers.booking_chat import try_start_booking_chat
from bot.keyboards.keyboards import ai_kb
from bot.texts import all_variants, tr

logger = logging.getLogger(__name__)
router = Router(name="ai_chat")

TELEGRAM_LIMIT = 4000
_user_locks: dict[int, asyncio.Lock] = {}


class AIChat(StatesGroup):
    active = State()


def split_message(text: str, limit: int = TELEGRAM_LIMIT) -> list[str]:
    parts: list[str] = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = limit
        parts.append(text[:cut])
        text = text[cut:].lstrip()
    if text:
        parts.append(text)
    return parts


async def start_ai(message: Message, state: FSMContext, lang: str) -> None:
    await state.clear()
    await state.set_state(AIChat.active)
    await message.answer(tr("ai_intro", lang), reply_markup=ai_kb(lang))


async def ask_ai(message: Message, bot: Bot, services: Services, user_id: int, text: str, lang: str) -> None:
    lock = _user_locks.setdefault(user_id, asyncio.Lock())
    if lock.locked():
        await message.answer(tr("ai_busy", lang))
        return
    async with lock:
        async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
            reply = await services.ai.answer(user_id, text, lang)
        logger.info("AI reply sent (source=%s, chars=%s)", reply.source, len(reply.text))
        for part in split_message(reply.text):
            # parse_mode=None: model output is plain text and must not be parsed as HTML.
            await message.answer(part, parse_mode=None, reply_markup=ai_kb(lang))


@router.message(AIChat.active, F.text.func(lambda t: t in all_variants("btn_ai_reset")))
async def on_reset_button(message: Message, services: Services, lang: str) -> None:
    services.ai.reset(message.from_user.id)
    await message.answer(tr("ai_reset_done", lang), reply_markup=ai_kb(lang))


@router.message(AIChat.active, F.text)
async def on_ai_message(message: Message, state: FSMContext, bot: Bot, services: Services, lang: str) -> None:
    # "Забронируйте столик на завтра в 19:00" inside the AI chat starts the JSON booking flow
    if await try_start_booking_chat(message, state, bot, services, lang):
        return
    await ask_ai(message, bot, services, message.from_user.id, message.text, lang)


@router.message(AIChat.active)
async def on_ai_non_text(message: Message, lang: str) -> None:
    await message.answer(tr("ai_text_only", lang))


@router.callback_query(F.data.startswith("askai:"))
async def on_ask_about_dish(callback: CallbackQuery, state: FSMContext, bot: Bot, services: Services,
                            lang: str) -> None:
    dish = services.menu.get(callback.data.split(":", 1)[1])
    await callback.answer()
    if dish is None or callback.message is None:
        return
    await state.set_state(AIChat.active)
    question = {
        "ru": f"Расскажи подробнее о блюде «{dish.name['ru']}»: вкус, с чем сочетать, кому подойдёт?",
        "kk": f"«{dish.name['kk']}» тағамы туралы толығырақ айтып беріңізші: дәмі, немен үйлеседі, кімге лайық?",
        "en": f"Tell me more about \"{dish.name['en']}\": taste, what to pair it with, who would enjoy it?",
    }[lang]
    await callback.message.answer(f"💬 {question}", parse_mode=None)
    await ask_ai(callback.message, bot, services, callback.from_user.id, question, lang)
