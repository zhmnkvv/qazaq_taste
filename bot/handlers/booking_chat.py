"""Booking from free text: LLM JSON extraction -> Python checks -> one question at a time
-> confirmation -> bookings.csv.

The guided button flow (handlers/booking.py) stays unchanged; this flow starts when a
guest simply writes something like "столик на завтра в 19:00 на четверых".
"""

from __future__ import annotations

import logging
from datetime import date, time
from html import escape

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from aiogram.utils.chat_action import ChatActionSender

from bot.container import Services
from bot.database.csv_store import CsvFormatError
from bot.handlers.booking import notify_admin
from bot.keyboards.keyboards import cancel_kb, main_menu
from bot.services.booking_draft import check_draft, empty_draft, is_confirmation, is_rejection, merge
from bot.services.booking_extraction import FIELDS, classify_booking_message, looks_like_booking
from bot.services.booking_service import BookingData, ValidationError, mask_phone
from bot.texts import tr

logger = logging.getLogger(__name__)
router = Router(name="booking_chat")

ERROR_FIELD = {"err_date": "date", "err_time": "time", "err_guests": "guests", "err_name": "name",
               "err_phone": "phone"}


class BookingChat(StatesGroup):
    collecting = State()
    confirm = State()


async def _extract(message: Message, bot: Bot, services: Services, text: str,
                   known: dict | None = None, asked: str | None = None):
    async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
        result = await services.extractor.extract(text, known=known, asked=asked)
    logger.info("Booking extraction: status=%s source=%s attempts=%s", result.status, result.source, result.attempts)
    return result


async def try_start_booking_chat(message: Message, state: FSMContext, bot: Bot, services: Services,
                                 lang: str) -> bool:
    """Called for free text. Returns True if the message was handled as a booking request.

    Informational questions about booking ("Как забронировать столик?", "Вы принимаете
    бронирования?") are recognised in Python and left to the AI consultant without an
    extraction call; only real requests ("Хочу забронировать столик") start the flow.
    """
    if not message.text or not looks_like_booking(message.text):
        return False
    kind = classify_booking_message(message.text, services.booking.today())
    logger.info("Booking message classified as %s", kind)
    if kind != "request":
        return False
    result = await _extract(message, bot, services, message.text)
    if result.status == "invalid":
        await message.answer(tr("jb_invalid_json", lang))
        return True
    if result.data["intent"] != "booking":
        return False  # e.g. "сколько стоит бронь зала?" -> the AI consultant answers
    await state.set_state(BookingChat.collecting)
    await state.update_data(jb_draft=empty_draft(), jb_asked=None, jb_errors={})
    await process(message, state, services, lang, result.data)
    return True


async def process(message: Message, state: FSMContext, services: Services, lang: str, new_data: dict) -> None:
    """Merge new values, validate in Python and either ask ONE question or show the summary."""
    data = await state.get_data()
    check = check_draft(merge(data.get("jb_draft") or empty_draft(), new_data), services.booking.now())

    errors: dict = {f: v for f, v in (data.get("jb_errors") or {}).items() if check.draft.get(f) is None}
    for field_name, err in check.errors:
        errors[field_name] = [err.code, err.params]
    await state.update_data(jb_draft=check.draft)

    if check.complete:
        await state.set_state(BookingChat.confirm)
        await state.update_data(jb_asked=None, jb_errors={})
        await message.answer(summary_text(check.draft, lang), reply_markup=cancel_kb(lang))
        return

    field_name = check.next_field  # the first missing field only
    await state.set_state(BookingChat.collecting)
    if field_name in errors:
        code, params = errors.pop(field_name)
        question = tr(code, lang, **params)
    else:
        question = tr(f"jb_q_{field_name}", lang)
    await state.update_data(jb_asked=field_name, jb_errors=errors)
    await message.answer(question, reply_markup=cancel_kb(lang))


def summary_text(draft: dict, lang: str) -> str:
    return tr(
        "jb_summary", lang,
        date=date.fromisoformat(draft["date"]).strftime("%d.%m.%Y"), time=draft["time"], guests=draft["guests"],
        name=escape(draft["name"]), phone=escape(draft["phone"]),
    )


@router.message(BookingChat.collecting, F.text)
async def on_answer(message: Message, state: FSMContext, bot: Bot, services: Services, lang: str) -> None:
    data = await state.get_data()
    asked = data.get("jb_asked")
    result = await _extract(message, bot, services, message.text, known=data.get("jb_draft"), asked=asked)
    if result.status == "invalid":
        await message.answer(tr("jb_invalid_answer", lang) + "\n" + tr(f"jb_q_{asked}", lang))
        return
    if not any(result.data.get(f) is not None for f in FIELDS):
        await message.answer(tr("jb_not_understood", lang) + "\n" + tr(f"jb_q_{asked}", lang))
        return
    await process(message, state, services, lang, result.data)


@router.message(BookingChat.confirm, F.text)
async def on_confirm(message: Message, state: FSMContext, bot: Bot, services: Services, lang: str) -> None:
    if is_confirmation(message.text):
        await save(message, state, bot, services, lang)
        return
    if is_rejection(message.text):
        await state.clear()
        await message.answer(tr("jb_cancelled", lang), reply_markup=main_menu(lang))
        return
    # anything else is treated as a correction: "время 20:00", "нас будет 6"
    data = await state.get_data()
    result = await _extract(message, bot, services, message.text, known=data.get("jb_draft"))
    if result.status == "ok" and any(result.data.get(f) is not None for f in FIELDS):
        await process(message, state, services, lang, result.data)
    else:
        await message.answer(tr("jb_confirm_hint", lang))


async def save(message: Message, state: FSMContext, bot: Bot, services: Services, lang: str) -> None:
    """Only here — after an explicit "yes" — the request is written to SQLite and bookings.csv."""
    draft = (await state.get_data())["jb_draft"]
    try:
        booking = services.booking.create(message.from_user.id, BookingData(
            name=draft["name"], phone=draft["phone"], visit_date=date.fromisoformat(draft["date"]),
            visit_time=time.fromisoformat(draft["time"]), guests=int(draft["guests"]),
        ))
    except ValidationError as err:  # e.g. the time passed while the guest was confirming
        field_name = next((f for prefix, f in ERROR_FIELD.items() if err.code.startswith(prefix)), "time")
        draft[field_name] = None
        await state.update_data(jb_draft=draft, jb_errors={field_name: [err.code, err.params]})
        await process(message, state, services, lang, {})
        return
    try:
        services.bookings_csv.append({
            "intent": "booking", "date": draft["date"], "time": draft["time"], "guests": draft["guests"],
            "name": draft["name"], "phone": draft["phone"], "code": booking.code,
        })
    except (CsvFormatError, OSError) as exc:
        logger.error("Could not write bookings.csv: %s", exc)
    await state.clear()
    logger.info("JSON booking %s saved (guests=%s, phone=%s)", booking.code, booking.guests,
                mask_phone(booking.phone))
    await message.answer(tr("jb_saved", lang, code=booking.code), reply_markup=main_menu(lang))
    await notify_admin(bot, services, tr(
        "booking_admin", "ru", code=booking.code, date=booking.visit_date.strftime("%d.%m.%Y"),
        time=booking.visit_time.strftime("%H:%M"), guests=booking.guests, name=escape(booking.customer_name),
        phone=escape(booking.phone), wishes="—",
    ))


@router.message(BookingChat.collecting)
@router.message(BookingChat.confirm)
async def non_text(message: Message, lang: str) -> None:
    await message.answer(tr("err_text_expected", lang))
