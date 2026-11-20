"""Restaurant menu browsing with inline keyboards."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message

from bot.container import Services
from bot.data import menu as data
from bot.keyboards.keyboards import categories_kb, dish_kb, dishes_kb
from bot.texts import tr

router = Router(name="menu")


async def show_menu(message: Message, lang: str) -> None:
    await message.answer(tr("menu_intro", lang, charge=data.SERVICE_CHARGE_PERCENT), reply_markup=categories_kb(lang))


async def _edit(callback: CallbackQuery, text: str, markup) -> None:
    try:
        await callback.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc):
            await callback.message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "cats")
async def on_categories(callback: CallbackQuery, lang: str) -> None:
    await _edit(callback, tr("menu_intro", lang, charge=data.SERVICE_CHARGE_PERCENT), categories_kb(lang))
    await callback.answer()


@router.callback_query(F.data.startswith("cat:"))
async def on_category(callback: CallbackQuery, services: Services, lang: str) -> None:
    category = callback.data.split(":", 1)[1]
    if category not in data.CATEGORIES:
        await callback.answer()
        return
    await _edit(callback, services.menu.category_text(category, lang), dishes_kb(services.menu, category, lang))
    await callback.answer()


@router.callback_query(F.data.startswith("dish:"))
async def on_dish(callback: CallbackQuery, services: Services, lang: str) -> None:
    dish = services.menu.get(callback.data.split(":", 1)[1])
    if dish is None:
        await callback.answer(tr("dish_not_found", lang), show_alert=True)
        return
    await _edit(callback, services.menu.dish_card(dish, lang), dish_kb(dish.id, dish.category, lang))
    await callback.answer()
