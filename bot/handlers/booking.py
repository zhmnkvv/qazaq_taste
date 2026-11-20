"""Table booking request flow (aiogram FSM)."""

from __future__ import annotations

import logging
from datetime import date, time
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.container import Services
from bot.data import menu as data
from bot.keyboards.keyboards import cancel_kb, confirm_kb, main_menu
from bot.services.booking_service import (
    BookingData,
    ValidationError,
    clean_wishes,
    mask_phone,
    normalize_phone,
    opening_window,
    parse_date,
    parse_guests,
    parse_time,
    validate_name,
)
from bot.texts import all_variants, tr

logger = logging.getLogger(__name__)
router = Router(name="booking")


class BookingForm(StatesGroup):
    name = State()
    phone = State()
    date = State()
    time = State()
    guests = State()
    wishes = State()
    confirm = State()


async def reply_error(message: Message, err: ValidationError, lang: str) -> None:
    await message.answer(tr(err.code, lang, **err.params))


async def start_booking(message: Message, state: FSMContext, lang: str) -> None:
    await state.clear()
    await state.set_state(BookingForm.name)
    await message.answer(tr("booking_start", lang), reply_markup=cancel_kb(lang))


@router.message(BookingForm.name, F.text)
async def step_name(message: Message, state: FSMContext, lang: str) -> None:
    try:
        name = validate_name(message.text)
    except ValidationError as err:
        await reply_error(message, err, lang)
        return
    await state.update_data(name=name)
    await state.set_state(BookingForm.phone)
    await message.answer(tr("ask_phone", lang), reply_markup=cancel_kb(lang, share_phone=True))


@router.message(BookingForm.phone, F.contact | F.text)
async def step_phone(message: Message, state: FSMContext, services: Services, lang: str) -> None:
    raw = message.contact.phone_number if message.contact else message.text
    if message.contact and message.contact.user_id not in (None, message.from_user.id):
        await message.answer(tr("err_phone", lang))
        return
    try:
        phone = normalize_phone(raw if raw.startswith("+") or not message.contact else "+" + raw)
    except ValidationError as err:
        await reply_error(message, err, lang)
        return
    await state.update_data(phone=phone)
    await state.set_state(BookingForm.date)
    example = services.booking.today().replace(day=min(services.booking.today().day, 28))
    await message.answer(
        tr("ask_date", lang, example=f"{example:%d.%m.%Y}"),
        reply_markup=cancel_kb(lang, extra=[tr("btn_today", lang), tr("btn_tomorrow", lang)]),
    )


@router.message(BookingForm.date, F.text)
async def step_date(message: Message, state: FSMContext, services: Services, lang: str) -> None:
    try:
        visit_date = parse_date(message.text, services.booking.today())
    except ValidationError as err:
        await reply_error(message, err, lang)
        return
    await state.update_data(visit_date=visit_date.isoformat())
    await state.set_state(BookingForm.time)
    first, last = opening_window(visit_date)
    await message.answer(tr("ask_time", lang, first=f"{first:%H:%M}", last=f"{last:%H:%M}"),
                         reply_markup=cancel_kb(lang))


@router.message(BookingForm.time, F.text)
async def step_time(message: Message, state: FSMContext, services: Services, lang: str) -> None:
    visit_date = date.fromisoformat((await state.get_data())["visit_date"])
    try:
        visit_time = parse_time(message.text, visit_date, services.booking.now())
    except ValidationError as err:
        await reply_error(message, err, lang)
        return
    await state.update_data(visit_time=visit_time.strftime("%H:%M"))
    await state.set_state(BookingForm.guests)
    await message.answer(tr("ask_guests", lang, max=data.BOOKING_MAX_GUESTS), reply_markup=cancel_kb(lang))


@router.message(BookingForm.guests, F.text)
async def step_guests(message: Message, state: FSMContext, lang: str) -> None:
    try:
        guests = parse_guests(message.text)
    except ValidationError as err:
        await reply_error(message, err, lang)
        return
    await state.update_data(guests=guests)
    await state.set_state(BookingForm.wishes)
    await message.answer(tr("ask_wishes", lang), reply_markup=cancel_kb(lang, skip=True))


@router.message(BookingForm.wishes, F.text)
async def step_wishes(message: Message, state: FSMContext, lang: str) -> None:
    text = "" if message.text in all_variants("btn_skip") else message.text
    try:
        wishes = clean_wishes(text)
    except ValidationError as err:
        await reply_error(message, err, lang)
        return
    await state.update_data(wishes=wishes)
    await state.set_state(BookingForm.confirm)
    d = await state.get_data()
    await message.answer(
        tr("booking_summary", lang,
           name=escape(d["name"]), phone=escape(d["phone"]),
           date=date.fromisoformat(d["visit_date"]).strftime("%d.%m.%Y"), time=d["visit_time"],
           guests=d["guests"], wishes=escape(d["wishes"]) or tr("no_wishes", lang)),
        reply_markup=confirm_kb(lang, "book"),
    )


@router.callback_query(BookingForm.confirm, F.data == "book:restart")
async def on_restart(callback: CallbackQuery, state: FSMContext, lang: str) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await start_booking(callback.message, state, lang)


@router.callback_query(BookingForm.confirm, F.data == "book:confirm")
async def on_confirm(callback: CallbackQuery, state: FSMContext, services: Services, bot: Bot,
                     lang: str) -> None:
    d = await state.get_data()
    await callback.message.edit_reply_markup(reply_markup=None)
    try:
        booking = services.booking.create(
            callback.from_user.id,
            BookingData(
                name=d["name"], phone=d["phone"], visit_date=date.fromisoformat(d["visit_date"]),
                visit_time=time.fromisoformat(d["visit_time"]), guests=int(d["guests"]), wishes=d.get("wishes", ""),
            ),
        )
    except ValidationError as err:
        # e.g. the chosen time passed while the user was confirming
        await callback.answer()
        await callback.message.answer(tr(err.code, lang, **err.params))
        await start_booking(callback.message, state, lang)
        return
    await state.clear()
    await callback.answer("✅")
    logger.info("Booking request %s created (guests=%s, phone=%s)", booking.code, booking.guests,
                mask_phone(booking.phone))
    params = dict(
        code=booking.code, date=booking.visit_date.strftime("%d.%m.%Y"), time=booking.visit_time.strftime("%H:%M"),
        guests=booking.guests, phone=escape(booking.phone), rphone=data.RESTAURANT["phone"],
    )
    await callback.message.answer(tr("booking_done", lang, **params), reply_markup=main_menu(lang))
    await notify_admin(bot, services, tr(
        "booking_admin", "ru", code=booking.code, date=params["date"], time=params["time"], guests=booking.guests,
        name=escape(booking.customer_name), phone=escape(booking.phone), wishes=escape(booking.wishes) or "—",
    ))


@router.callback_query(F.data.startswith("book:"))
async def on_stale_confirm(callback: CallbackQuery, lang: str) -> None:
    await callback.answer(tr("session_expired", lang), show_alert=True)


@router.message(BookingForm.name)
@router.message(BookingForm.phone)
@router.message(BookingForm.date)
@router.message(BookingForm.time)
@router.message(BookingForm.guests)
@router.message(BookingForm.wishes)
async def non_text(message: Message, lang: str) -> None:
    await message.answer(tr("err_text_expected", lang))


async def notify_admin(bot: Bot, services: Services, text: str) -> None:
    chat_id = services.settings.admin_chat_id
    if not chat_id:
        return
    try:
        await bot.send_message(chat_id, text)
    except TelegramAPIError as exc:
        logger.warning("Could not notify admin chat: %s", type(exc).__name__)
