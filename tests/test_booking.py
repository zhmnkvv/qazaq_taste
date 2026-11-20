from datetime import date, time

import pytest

from bot.database.database import Database
from bot.database.repository import BookingRepository, UserRepository
from bot.services.booking_service import (
    BookingData,
    BookingService,
    ValidationError,
    clean_wishes,
    mask_phone,
    normalize_phone,
    parse_date,
    parse_guests,
    parse_time,
    validate_name,
)
from tests.conftest import FIXED_NOW

TODAY = FIXED_NOW.date()  # Wednesday 10.06.2026


def valid_data(**kw) -> BookingData:
    values = dict(name="Айгерим", phone="+7 701 123 45 67", visit_date=date(2026, 6, 12),
                  visit_time=time(19, 30), guests=4, wishes="у окна")
    values.update(kw)
    return BookingData(**values)


# ---- dates -------------------------------------------------------------------
@pytest.mark.parametrize("text,expected", [
    ("12.06.2026", date(2026, 6, 12)),
    ("12.06.26", date(2026, 6, 12)),
    ("2026-06-12", date(2026, 6, 12)),
    ("12.06", date(2026, 6, 12)),
    ("Сегодня", TODAY),
    ("завтра", date(2026, 6, 11)),
    ("Ертең", date(2026, 6, 11)),
    ("tomorrow", date(2026, 6, 11)),
])
def test_parse_valid_dates(text, expected):
    assert parse_date(text, TODAY) == expected


@pytest.mark.parametrize("text", ["09.06.2026", "01.01.2020", "yesterday-ish"])
def test_past_or_garbage_dates_rejected(text):
    with pytest.raises(ValidationError) as exc:
        parse_date(text, TODAY)
    assert exc.value.code in {"err_date_past", "err_date_format"}


def test_past_date_has_specific_error():
    with pytest.raises(ValidationError) as exc:
        parse_date("09.06.2026", TODAY)
    assert exc.value.code == "err_date_past"


@pytest.mark.parametrize("text", ["31.02.2026", "32.01.2027", "abc", "", "12/13/2026"])
def test_invalid_dates_rejected(text):
    with pytest.raises(ValidationError) as exc:
        parse_date(text, TODAY)
    assert exc.value.code == "err_date_format"


def test_short_date_in_past_rolls_to_next_year():
    # 01.06 already passed this year -> interpreted as 01.06.2027, which is beyond the 90-day window
    with pytest.raises(ValidationError) as exc:
        parse_date("01.06", TODAY)
    assert exc.value.code == "err_date_far"


def test_date_too_far_ahead():
    with pytest.raises(ValidationError) as exc:
        parse_date("10.12.2026", TODAY)
    assert exc.value.code == "err_date_far"


# ---- time --------------------------------------------------------------------
def test_time_within_opening_hours():
    assert parse_time("19:30", date(2026, 6, 12), FIXED_NOW) == time(19, 30)
    assert parse_time("19.30", date(2026, 6, 12), FIXED_NOW) == time(19, 30)
    assert parse_time("20", date(2026, 6, 12), FIXED_NOW) == time(20, 0)


@pytest.mark.parametrize("text,code", [("09:00", "err_time_hours"), ("22:30", "err_time_hours"),
                                       ("25:00", "err_time_format"), ("abc", "err_time_format")])
def test_time_rejected(text, code):
    # 11.06.2026 is a Thursday: open 11:00–23:00, last booking 22:00
    with pytest.raises(ValidationError) as exc:
        parse_time(text, date(2026, 6, 11), FIXED_NOW)
    assert exc.value.code == code


def test_friday_has_later_last_slot():
    assert parse_time("23:00", date(2026, 6, 12), FIXED_NOW) == time(23, 0)


def test_time_today_must_be_in_future():
    with pytest.raises(ValidationError) as exc:
        parse_time("12:10", TODAY, FIXED_NOW)
    assert exc.value.code == "err_time_past"
    assert parse_time("13:00", TODAY, FIXED_NOW) == time(13, 0)


# ---- other fields --------------------------------------------------------------
@pytest.mark.parametrize("raw,expected", [("+7 701 123 45 67", "+77011234567"), ("87011234567", "+77011234567"),
                                          ("8 (701) 123-45-67", "+77011234567"), ("+44 20 7946 0958", "+442079460958")])
def test_phone_normalization(raw, expected):
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize("raw", ["123", "phone", "+7 701 123 45 67 89 00 11", "'; DROP TABLE bookings;--"])
def test_invalid_phone(raw):
    with pytest.raises(ValidationError):
        normalize_phone(raw)


def test_names():
    assert validate_name("  Айгерим   Нурлановна ") == "Айгерим Нурлановна"
    assert validate_name("Jean-Luc") == "Jean-Luc"
    for bad in ["A", "R2D2", "<script>", "x" * 61, "Robert'); DROP TABLE bookings;--"]:
        with pytest.raises(ValidationError):
            validate_name(bad)


def test_guests():
    assert parse_guests("4") == 4
    for bad in ["0", "-2", "four", "21"]:
        with pytest.raises(ValidationError):
            parse_guests(bad)


def test_wishes():
    assert clean_wishes("-") == ""
    assert clean_wishes("  детский   стул ") == "детский стул"
    with pytest.raises(ValidationError):
        clean_wishes("x" * 301)


def test_mask_phone():
    assert mask_phone("+77011234567") == "+7701***67"


# ---- creation & persistence ------------------------------------------------------
def test_create_booking_saves_pending_request(booking_service):
    booking = booking_service.create(1001, valid_data())
    assert booking.id is not None
    assert booking.status == "pending"
    assert booking.code.startswith("QT-260610-") and len(booking.code) == 14
    stored = booking_service.repo.get_by_code(booking.code)
    assert stored.customer_name == "Айгерим"
    assert stored.phone == "+77011234567"
    assert stored.visit_date == date(2026, 6, 12) and stored.visit_time == time(19, 30)


def test_booking_codes_are_unique(booking_service):
    codes = {booking_service.create(1, valid_data()).code for _ in range(30)}
    assert len(codes) == 30


def test_create_booking_rejects_past_date(booking_service):
    with pytest.raises(ValidationError) as exc:
        booking_service.create(1, valid_data(visit_date=date(2026, 6, 1)))
    assert exc.value.code == "err_date_past"
    assert booking_service.repo.list_for_user(1) == []


def test_create_booking_rejects_time_outside_hours(booking_service):
    with pytest.raises(ValidationError):
        booking_service.create(1, valid_data(visit_time=time(8, 0)))


def test_sql_injection_text_is_stored_as_plain_data(booking_service):
    payload = "'); DROP TABLE bookings; --"
    booking = booking_service.create(7, valid_data(wishes=payload))
    assert booking_service.repo.get_by_code(booking.code).wishes == payload
    assert len(booking_service.repo.list_for_user(7)) == 1  # table still exists


def test_sqlite_file_persists_between_connections(tmp_path):
    url = f"sqlite:///{(tmp_path / 'sub' / 'test.db').as_posix()}"
    db1 = Database(url)
    db1.create_all()
    service = BookingService(BookingRepository(db1), clock=lambda: FIXED_NOW)
    code = service.create(55, valid_data()).code
    UserRepository(db1).set_language(55, "kk")
    db1.dispose()

    db2 = Database(url)
    try:
        assert BookingRepository(db2).get_by_code(code).guests == 4
        assert UserRepository(db2).get_language(55) == "kk"
    finally:
        db2.dispose()
    assert (tmp_path / "sub" / "test.db").exists()


def test_user_language_validation(db):
    repo = UserRepository(db)
    assert repo.get_language(1) is None
    repo.set_language(1, "en")
    repo.set_language(1, "kk")
    assert repo.get_language(1) == "kk"
    with pytest.raises(ValueError):
        repo.set_language(1, "de")
