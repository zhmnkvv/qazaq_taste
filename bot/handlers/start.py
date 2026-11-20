"""/start, /help, language selection, contacts and about."""

from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.container import Services
from bot.data import menu as data
from bot.keyboards.keyboards import language_kb, main_menu
from bot.texts import LANGS, tr

router = Router(name="start")


async def send_welcome(message: Message, lang: str, first_name: str | None) -> None:
    name = escape(first_name or "")
    await message.answer(tr("welcome", lang, name=name).replace(", !", "!"), reply_markup=main_menu(lang))


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, services: Services, lang: str) -> None:
    await state.clear()
    if services.users.get_language(message.from_user.id) is None:
        await message.answer(tr("choose_language", lang), reply_markup=language_kb())
        return
    await send_welcome(message, lang, message.from_user.first_name)


@router.message(Command("language"))
async def cmd_language(message: Message, lang: str) -> None:
    await message.answer(tr("choose_language", lang), reply_markup=language_kb())


@router.callback_query(F.data.startswith("lang:"))
async def on_language(callback: CallbackQuery, services: Services) -> None:
    new_lang = callback.data.split(":", 1)[1]
    if new_lang not in LANGS:
        await callback.answer()
        return
    services.users.set_language(callback.from_user.id, new_lang)
    await callback.answer(tr("language_set", new_lang))
    if callback.message:
        await callback.message.edit_text(tr("language_set", new_lang))
        await send_welcome(callback.message, new_lang, callback.from_user.first_name)


@router.message(Command("help"))
async def cmd_help(message: Message, lang: str) -> None:
    await message.answer(tr("help", lang), reply_markup=main_menu(lang))


async def show_contacts(message: Message, lang: str) -> None:
    r = data.RESTAURANT
    labels = {
        "ru": ("Контакты", "Адрес", "Телефон", "Часы работы"),
        "kk": ("Байланыс", "Мекенжай", "Телефон", "Жұмыс уақыты"),
        "en": ("Contacts", "Address", "Phone", "Opening hours"),
    }[lang]
    text = (
        f"📍 <b>{labels[0]} — Qazaq Taste</b>\n\n"
        f"🏠 <b>{labels[1]}:</b> {escape(r['address'][lang])}, {escape(r['city'][lang])}\n"
        f"☎️ <b>{labels[2]}:</b> {r['phone']}\n"
        f"✉️ Email: {r['email']}\n"
        f"📸 Instagram: {r['instagram']}\n"
        f"🕐 <b>{labels[3]}:</b> {escape(r['hours'][lang])}"
    )
    await message.answer(text, reply_markup=main_menu(lang))


async def show_about(message: Message, lang: str) -> None:
    r = data.RESTAURANT
    title = {"ru": "О ресторане", "kk": "Мейрамхана туралы", "en": "About us"}[lang]
    text = (
        f"ℹ️ <b>{title}</b>\n\n{escape(r['about'][lang])}\n\n"
        f"🏛 {escape(r['halls'][lang])}\n\n🎶 {escape(r['features'][lang])}"
    )
    await message.answer(text, reply_markup=main_menu(lang))
