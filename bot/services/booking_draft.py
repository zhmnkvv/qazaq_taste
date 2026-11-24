"""Merging and validating booking data collected through the JSON flow.

The model only extracts what the guest said. Everything that matters is
checked here in Python:
  1. the date is not in the past (and not too far ahead);
  2. the time is inside the restaurant's opening hours from bot/data/menu.py;
  3. the phone number has exactly 11 digits;
plus a sane number of guests and a valid name.

An invalid value is removed (set to None) so the bot asks for it again, and
the list of missing fields is always recomputed by the program.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, time

from bot.data.menu import BOOKING_MAX_GUESTS
from bot.services.booking_extraction import FIELDS
from bot.services.booking_service import (
    ValidationError,
    parse_date,
    parse_guests,
    parse_time,
    validate_name,
)


FORMAT_ERRORS = {"date": "err_date_format", "time": "err_time_format", "guests": "err_guests_format",
                 "name": "err_name", "phone": "err_phone_11"}


def empty_draft() -> dict:
    return {f: None for f in FIELDS}


def merge(known: dict, new: dict) -> dict:
    """Keep collected values; a non-null new value fills or corrects a field."""
    merged = {f: known.get(f) for f in FIELDS}
    for f in FIELDS:
        if new.get(f) is not None:
            merged[f] = new[f]
    return merged


def normalize_phone_11(raw: str) -> str:
    """Kazakhstan format: exactly 11 digits, 8XXXXXXXXXX is converted to +7XXXXXXXXXX."""
    digits = re.sub(r"\D", "", raw or "")
    if not re.fullmatch(r"[+\d\s()\-]{11,20}", (raw or "").strip()) or len(digits) != 11:
        raise ValidationError("err_phone_11")
    if digits[0] == "8":
        digits = "7" + digits[1:]
    return "+" + digits


@dataclass
class DraftCheck:
    draft: dict                                   # cleaned values (invalid ones removed)
    errors: list[tuple[str, ValidationError]] = field(default_factory=list)

    @property
    def missing(self) -> list[str]:
        return [f for f in FIELDS if self.draft.get(f) is None]

    @property
    def complete(self) -> bool:
        return not self.missing

    @property
    def next_field(self) -> str | None:
        """Only ONE question is asked: about the first missing field."""
        return self.missing[0] if self.missing else None


def check_draft(draft: dict, now: datetime) -> DraftCheck:
    clean = empty_draft()
    errors: list[tuple[str, ValidationError]] = []

    def run(field_name: str, func):
        try:
            clean[field_name] = func()
        except ValidationError as err:
            errors.append((field_name, err))
        except (TypeError, ValueError):  # e.g. "2026-02-30" from the model
            errors.append((field_name, ValidationError(FORMAT_ERRORS[field_name])))

    if draft.get("date"):
        run("date", lambda: parse_date(date.fromisoformat(draft["date"]).strftime("%d.%m.%Y"), now.date()).isoformat())
    if draft.get("time"):
        hhmm = draft["time"]
        if clean["date"]:
            # opening hours depend on the weekday, so time is checked together with the date
            run("time", lambda: parse_time(hhmm, date.fromisoformat(clean["date"]), now).strftime("%H:%M"))
        else:
            run("time", lambda: _check_time_format(hhmm))
    if draft.get("guests") is not None:
        run("guests", lambda: parse_guests(str(draft["guests"]), maximum=BOOKING_MAX_GUESTS))
    if draft.get("name"):
        run("name", lambda: validate_name(draft["name"]))
    if draft.get("phone"):
        run("phone", lambda: normalize_phone_11(draft["phone"]))
    return DraftCheck(clean, errors)


def _check_time_format(value: str) -> str:
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", value or "")
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        raise ValidationError("err_time_format")
    return time(int(m.group(1)), int(m.group(2))).strftime("%H:%M")


CONFIRM_YES = {"да", "подтверждаю", "подтверждаю бронь", "подтверждаю бронирование", "да подтверждаю",
               "да, подтверждаю", "иә", "иа", "растаймын", "yes", "confirm", "yes, confirm", "ok", "ок"}
CONFIRM_NO = {"нет", "не", "отмена", "отменить", "жоқ", "no", "cancel"}


def _norm(text: str) -> str:
    return re.sub(r"[!.?…\s]+$", "", " ".join((text or "").lower().split()))


def is_confirmation(text: str) -> bool:
    return _norm(text) in CONFIRM_YES


def is_rejection(text: str) -> bool:
    return _norm(text) in CONFIRM_NO
