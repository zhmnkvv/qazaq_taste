"""Event request flow -> commercial proposal, and the budget calculator."""

from __future__ import annotations

import logging
import math
import re
from datetime import date

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.container import Services
from bot.data import menu as data
from bot.handlers.booking import notify_admin
from bot.keyboards.keyboards import budget_type_kb, cancel_kb, event_types_kb, main_menu
from bot.services.booking_service import ValidationError, clean_wishes, mask_phone, normalize_phone, parse_date
from bot.services.menu_service import format_kzt
from bot.services.proposal_service import (
    MAX_EVENT_GUESTS,
    MIN_BUDGET_PER_PERSON,
    ProposalInput,
    calculate_budget,
    format_budget,
    format_proposal,
)
from bot.texts import all_variants, tr

logger = logging.getLogger(__name__)
router = Router(name="events")

MAX_BUDGET = 1_000_000_000


class EventForm(StatesGroup):
    event_type = State()
    guests = State()
    date = State()
    budget_type = State()
    budget_amount = State()
    wishes = State()
    phone = State()


class BudgetForm(StatesGroup):
    guests = State()
    amount = State()


def parse_amount(text: str) -> int | None:
    cleaned = re.sub(r"[\s ,._]|₸|тг|тенге|теңге|kzt|tenge", "", (text or "").lower())
    if cleaned.endswith(("k", "к")) and cleaned[:-1].isdigit():
        cleaned = str(int(cleaned[:-1]) * 1000)
    if not cleaned.isdigit():
        return None
    value = int(cleaned)
    return value if 0 < value <= MAX_BUDGET else None


def parse_event_guests(text: str) -> int | None:
    value = (text or "").strip()
    if value.isdigit() and 1 <= int(value) <= MAX_EVENT_GUESTS:
        return int(value)
    return None


# --------------------------------------------------------------------------- #
# Event flow
# --------------------------------------------------------------------------- #
async def start_event(message: Message, state: FSMContext, lang: str) -> None:
    await state.clear()
    await state.set_state(EventForm.event_type)
    await message.answer(tr("event_start", lang), reply_markup=cancel_kb(lang))
    await message.answer(tr("event_ask_type", lang), reply_markup=event_types_kb(lang))


@router.callback_query(EventForm.event_type, F.data.startswith("evtype:"))
async def ev_type(callback: CallbackQuery, state: FSMContext, lang: str) -> None:
    event_type = callback.data.split(":", 1)[1]
    if event_type not in data.EVENT_TYPES:
        await callback.answer()
        return
    await state.update_data(event_type=event_type)
    await state.set_state(EventForm.guests)
    await callback.answer()
    await callback.message.edit_text(f"🎉 {data.EVENT_TYPES[event_type]['name'][lang]}")
    await callback.message.answer(tr("event_ask_guests", lang, max=MAX_EVENT_GUESTS), reply_markup=cancel_kb(lang))


@router.message(EventForm.event_type)
async def ev_type_text(message: Message, lang: str) -> None:
    await message.answer(tr("use_buttons", lang), reply_markup=event_types_kb(lang))


@router.message(EventForm.guests, F.text)
async def ev_guests(message: Message, state: FSMContext, lang: str) -> None:
    guests = parse_event_guests(message.text)
    if guests is None:
        await message.answer(tr("err_guests_event", lang, max=MAX_EVENT_GUESTS))
        return
    await state.update_data(guests=guests)
    await state.set_state(EventForm.date)
    await message.answer(tr("event_ask_date", lang), reply_markup=cancel_kb(lang))


@router.message(EventForm.date, F.text)
async def ev_date(message: Message, state: FSMContext, services: Services, lang: str) -> None:
    try:
        event_date = parse_date(message.text, services.booking.today())
    except ValidationError as err:
        await message.answer(tr(err.code, lang, **err.params))
        return
    await state.update_data(event_date=event_date.isoformat())
    await state.set_state(EventForm.budget_type)
    await message.answer(tr("event_ask_budget_type", lang), reply_markup=budget_type_kb(lang))


@router.callback_query(EventForm.budget_type, F.data.startswith("evbudget:"))
async def ev_budget_type(callback: CallbackQuery, state: FSMContext, lang: str) -> None:
    kind = callback.data.split(":", 1)[1]
    await state.update_data(budget_type=kind)
    await state.set_state(EventForm.budget_amount)
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    key = "event_ask_budget_pp" if kind == "pp" else "event_ask_budget_total"
    await callback.message.answer(tr(key, lang), reply_markup=cancel_kb(lang))


@router.message(EventForm.budget_type)
async def ev_budget_type_text(message: Message, lang: str) -> None:
    await message.answer(tr("use_buttons", lang), reply_markup=budget_type_kb(lang))


@router.message(EventForm.budget_amount, F.text)
async def ev_budget_amount(message: Message, state: FSMContext, lang: str) -> None:
    amount = parse_amount(message.text)
    if amount is None:
        await message.answer(tr("err_number", lang))
        return
    d = await state.get_data()
    per_person = amount if d["budget_type"] == "pp" else amount // d["guests"]
    if per_person < MIN_BUDGET_PER_PERSON:
        await message.answer(tr("err_budget_small", lang, min=format_kzt(MIN_BUDGET_PER_PERSON)))
        return
    await state.update_data(budget_per_person=per_person)
    await state.set_state(EventForm.wishes)
    await message.answer(tr("event_ask_wishes", lang), reply_markup=cancel_kb(lang, skip=True))


@router.message(EventForm.wishes, F.text)
async def ev_wishes(message: Message, state: FSMContext, lang: str) -> None:
    text = "" if message.text in all_variants("btn_skip") else message.text
    try:
        wishes = clean_wishes(text, max_len=500)
    except ValidationError as err:
        await message.answer(tr(err.code, lang, **err.params))
        return
    await state.update_data(wishes=wishes)
    await state.set_state(EventForm.phone)
    await message.answer(tr("event_ask_phone", lang), reply_markup=cancel_kb(lang, skip=True, share_phone=True))


@router.message(EventForm.phone, F.contact | F.text)
async def ev_phone(message: Message, state: FSMContext, services: Services, bot: Bot, lang: str) -> None:
    phone = ""
    if message.contact or message.text not in all_variants("btn_skip"):
        raw = message.contact.phone_number if message.contact else message.text
        if message.contact and not raw.startswith("+"):
            raw = "+" + raw
        try:
            phone = normalize_phone(raw)
        except ValidationError as err:
            await message.answer(tr(err.code, lang))
            return
    d = await state.get_data()
    await state.clear()
    proposal = services.proposals.build(ProposalInput(
        event_type=d["event_type"], guests=int(d["guests"]), event_date=date.fromisoformat(d["event_date"]),
        budget_per_person=int(d["budget_per_person"]), wishes=d.get("wishes", ""), phone=phone,
    ))
    text = format_proposal(proposal, lang)
    saved = services.proposals.save(message.from_user.id, proposal, text)
    logger.info("Event request %s saved (type=%s, guests=%s, phone=%s)", saved.code, saved.event_type,
                saved.guests, mask_phone(phone) if phone else "-")
    await message.answer(text, reply_markup=main_menu(lang))
    footer = tr("event_saved", lang, code=saved.code)
    if not phone:
        footer += "\n" + tr("event_saved_no_phone", lang, rphone=data.RESTAURANT["phone"])
    await message.answer(footer)
    await notify_admin(bot, services, tr(
        "event_admin", "ru", code=saved.code, type=data.EVENT_TYPES[saved.event_type]["name"]["ru"],
        date=saved.event_date.strftime("%d.%m.%Y"), guests=saved.guests, total=format_kzt(saved.total_price),
        phone=phone or "—",
    ))


# --------------------------------------------------------------------------- #
# Budget calculator
# --------------------------------------------------------------------------- #
async def start_budget(message: Message, state: FSMContext, lang: str) -> None:
    await state.clear()
    await state.set_state(BudgetForm.guests)
    await message.answer(tr("budget_start", lang, max=MAX_EVENT_GUESTS), reply_markup=cancel_kb(lang))


@router.message(BudgetForm.guests, F.text)
async def budget_guests(message: Message, state: FSMContext, lang: str) -> None:
    guests = parse_event_guests(message.text)
    if guests is None:
        await message.answer(tr("err_guests_event", lang, max=MAX_EVENT_GUESTS))
        return
    await state.update_data(guests=guests)
    await state.set_state(BudgetForm.amount)
    await message.answer(tr("budget_ask_amount", lang), reply_markup=cancel_kb(lang))


@router.message(BudgetForm.amount, F.text)
async def budget_amount(message: Message, state: FSMContext, services: Services, lang: str) -> None:
    amount = parse_amount(message.text)
    if amount is None:
        await message.answer(tr("err_number", lang))
        return
    guests = int((await state.get_data())["guests"])
    if math.floor(amount / guests) < MIN_BUDGET_PER_PERSON:
        await message.answer(tr("err_budget_small", lang, min=format_kzt(MIN_BUDGET_PER_PERSON)))
        return
    await state.clear()
    result = calculate_budget(guests, amount, services.menu)
    await message.answer(format_budget(result, lang), reply_markup=main_menu(lang))
    if guests >= 10:
        await message.answer(tr("budget_next", lang))


@router.message(EventForm.guests)
@router.message(EventForm.date)
@router.message(EventForm.budget_amount)
@router.message(EventForm.wishes)
@router.message(EventForm.phone)
@router.message(BudgetForm.guests)
@router.message(BudgetForm.amount)
async def non_text(message: Message, lang: str) -> None:
    await message.answer(tr("err_text_expected", lang))
