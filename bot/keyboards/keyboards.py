"""Reply and inline keyboards."""

from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from bot.data import menu as data
from bot.services.menu_service import MenuService, format_kzt
from bot.texts import tr


def main_menu(lang: str) -> ReplyKeyboardMarkup:
    b = lambda key: KeyboardButton(text=tr(key, lang))  # noqa: E731
    return ReplyKeyboardMarkup(
        keyboard=[
            [b("btn_menu"), b("btn_booking")],
            [b("btn_ai"), b("btn_event")],
            [b("btn_budget"), b("btn_contacts")],
            [b("btn_about")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Qazaq Taste",
    )


def cancel_kb(lang: str, skip: bool = False, share_phone: bool = False,
              extra: list[str] | None = None) -> ReplyKeyboardMarkup:
    rows: list[list[KeyboardButton]] = []
    if share_phone:
        rows.append([KeyboardButton(text=tr("btn_share_phone", lang), request_contact=True)])
    if extra:
        rows.append([KeyboardButton(text=e) for e in extra])
    if skip:
        rows.append([KeyboardButton(text=tr("btn_skip", lang))])
    rows.append([KeyboardButton(text=tr("btn_cancel", lang))])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def ai_kb(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=tr("btn_ai_reset", lang)), KeyboardButton(text=tr("btn_exit_ai", lang))]],
        resize_keyboard=True,
        input_field_placeholder="💬",
    )


def language_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
        InlineKeyboardButton(text="🇰🇿 Қазақша", callback_data="lang:kk"),
        InlineKeyboardButton(text="🇬🇧 English", callback_data="lang:en"),
    ]])


def categories_kb(lang: str) -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(text=name[lang], callback_data=f"cat:{cid}")
               for cid, name in data.CATEGORIES.items()]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def dishes_kb(menu: MenuService, category: str, lang: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"{d.localized('name', lang)} · {format_kzt(d.price)}",
                                  callback_data=f"dish:{d.id}")]
            for d in menu.by_category(category)]
    rows.append([InlineKeyboardButton(text=tr("btn_back", lang), callback_data="cats")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def dish_kb(dish_id: str, category: str, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=tr("btn_ask_ai_dish", lang), callback_data=f"askai:{dish_id}")],
        [InlineKeyboardButton(text=tr("btn_back", lang), callback_data=f"cat:{category}")],
    ])


def confirm_kb(lang: str, prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=tr("btn_confirm", lang), callback_data=f"{prefix}:confirm"),
        InlineKeyboardButton(text=tr("btn_restart", lang), callback_data=f"{prefix}:restart"),
    ]])


def event_types_kb(lang: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=ev["name"][lang], callback_data=f"evtype:{key}")]
            for key, ev in data.EVENT_TYPES.items()]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def budget_type_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=tr("btn_per_person", lang), callback_data="evbudget:pp"),
        InlineKeyboardButton(text=tr("btn_total", lang), callback_data="evbudget:total"),
    ]])
