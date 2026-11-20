"""Booking validation and creation.

A booking created here is a *request* (status "pending"): the system does not
check real table availability, so staff must confirm it.
"""

from __future__ import annotations

import re
import secrets
import string
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from bot.data.menu import BOOKING_MAX_DAYS_AHEAD, BOOKING_MAX_GUESTS, OPENING_HOURS
from bot.database.models import Booking
from bot.database.repository import BookingRepository


class ValidationError(ValueError):
    """Invalid user input. ``code`` is an i18n key describing the problem."""

    def __init__(self, code: str, **params) -> None:
        super().__init__(code)
        self.code = code
        self.params = params


NAME_RE = re.compile(r"^[^\W\d_]+(?:[ '\-][^\W\d_]+)*$", re.UNICODE)
TODAY_WORDS = {"сегодня", "бүгін", "today"}
TOMORROW_WORDS = {"завтра", "ертең", "tomorrow"}
MIN_LEAD_MINUTES = 30
LAST_BOOKING_BEFORE_CLOSE_MIN = 60


def validate_name(text: str) -> str:
    name = " ".join((text or "").split())
    if not 2 <= len(name) <= 60 or not NAME_RE.match(name):
        raise ValidationError("err_name")
    return name


def normalize_phone(text: str) -> str:
    raw = (text or "").strip()
    if not re.fullmatch(r"[+\d\s()\-]{7,25}", raw):
        raise ValidationError("err_phone")
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits[0] in "78":
        return "+7" + digits[1:]
    if len(digits) == 10 and digits[0] == "7":  # 7XX XXX XX XX without country code
        return "+7" + digits
    if raw.startswith("+") and 10 <= len(digits) <= 15:
        return "+" + digits
    raise ValidationError("err_phone")


def parse_date(text: str, today: date) -> date:
    value = (text or "").strip().lower()
    if value in TODAY_WORDS:
        result = today
    elif value in TOMORROW_WORDS:
        result = today + timedelta(days=1)
    else:
        result = None
        for fmt in ("%d.%m.%Y", "%d.%m.%y", "%d/%m/%Y", "%Y-%m-%d"):
            try:
                result = datetime.strptime(value, fmt).date()
                break
            except ValueError:
                continue
        if result is None:
            m = re.fullmatch(r"(\d{1,2})[./](\d{1,2})", value)
            if m:
                try:
                    result = date(today.year, int(m.group(2)), int(m.group(1)))
                except ValueError:
                    raise ValidationError("err_date_format") from None
                if result < today:
                    try:
                        result = result.replace(year=today.year + 1)
                    except ValueError:  # 29.02 in a non-leap year
                        raise ValidationError("err_date_format") from None
        if result is None:
            raise ValidationError("err_date_format")
    if result < today:
        raise ValidationError("err_date_past")
    if result > today + timedelta(days=BOOKING_MAX_DAYS_AHEAD):
        raise ValidationError("err_date_far", days=BOOKING_MAX_DAYS_AHEAD)
    return result


def opening_window(visit_date: date) -> tuple[time, time]:
    """Return (first_slot, last_slot) for the date."""
    open_h, close_h = OPENING_HOURS[visit_date.weekday()]
    last_minutes = close_h * 60 - LAST_BOOKING_BEFORE_CLOSE_MIN
    return time(open_h, 0), time(last_minutes // 60, last_minutes % 60)


def parse_time(text: str, visit_date: date, now: datetime) -> time:
    value = (text or "").strip().replace(".", ":").replace("-", ":")
    m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?", value)
    if not m:
        raise ValidationError("err_time_format")
    hour, minute = int(m.group(1)), int(m.group(2) or 0)
    if hour > 23 or minute > 59:
        raise ValidationError("err_time_format")
    visit_time = time(hour, minute)
    first, last = opening_window(visit_date)
    if not first <= visit_time <= last:
        raise ValidationError("err_time_hours", first=first.strftime("%H:%M"), last=last.strftime("%H:%M"))
    if visit_date == now.date():
        earliest = (now + timedelta(minutes=MIN_LEAD_MINUTES)).time()
        if visit_time < earliest:
            raise ValidationError("err_time_past", minutes=MIN_LEAD_MINUTES)
    return visit_time


def parse_guests(text: str, maximum: int = BOOKING_MAX_GUESTS) -> int:
    value = (text or "").strip()
    if not value.isdigit():
        raise ValidationError("err_guests_format")
    guests = int(value)
    if guests < 1:
        raise ValidationError("err_guests_format")
    if guests > maximum:
        raise ValidationError("err_guests_max", maximum=maximum)
    return guests


def clean_wishes(text: str, max_len: int = 300) -> str:
    value = " ".join((text or "").split())
    if value in {"-", "—", "нет", "жоқ", "no", "none"}:
        return ""
    if len(value) > max_len:
        raise ValidationError("err_wishes_long", maximum=max_len)
    return value


def generate_code(prefix: str, on_date: date) -> str:
    alphabet = string.ascii_uppercase + string.digits
    suffix = "".join(secrets.choice(alphabet) for _ in range(4))
    return f"{prefix}-{on_date:%y%m%d}-{suffix}"


@dataclass
class BookingData:
    name: str
    phone: str
    visit_date: date
    visit_time: time
    guests: int
    wishes: str = ""


class BookingService:
    def __init__(self, repo: BookingRepository, tz: str = "Asia/Almaty",
                 clock: Callable[[], datetime] | None = None) -> None:
        self.repo = repo
        self.tz = ZoneInfo(tz)
        self._clock = clock

    def now(self) -> datetime:
        if self._clock:
            return self._clock()
        return datetime.now(self.tz).replace(tzinfo=None)

    def today(self) -> date:
        return self.now().date()

    def validate(self, data: BookingData) -> BookingData:
        """Full re-validation (used before saving, also protects against stale FSM data)."""
        now = self.now()
        validated = BookingData(
            name=validate_name(data.name),
            phone=normalize_phone(data.phone),
            visit_date=parse_date(data.visit_date.strftime("%d.%m.%Y"), now.date()),
            visit_time=data.visit_time,
            guests=parse_guests(str(data.guests)),
            wishes=clean_wishes(data.wishes),
        )
        parse_time(data.visit_time.strftime("%H:%M"), validated.visit_date, now)
        return validated

    def create(self, telegram_id: int, data: BookingData) -> Booking:
        valid = self.validate(data)
        code = self._unique_code()
        booking = Booking(
            code=code,
            telegram_id=telegram_id,
            customer_name=valid.name,
            phone=valid.phone,
            visit_date=valid.visit_date,
            visit_time=valid.visit_time,
            guests=valid.guests,
            wishes=valid.wishes,
            status="pending",
        )
        return self.repo.add(booking)

    def _unique_code(self) -> str:
        for _ in range(20):
            code = generate_code("QT", self.today())
            if not self.repo.code_exists(code):
                return code
        raise RuntimeError("Could not generate a unique booking code")


def mask_phone(phone: str) -> str:
    """For logs: +77011234567 -> +7701***67."""
    if len(phone) < 7:
        return "***"
    return phone[:5] + "***" + phone[-2:]
