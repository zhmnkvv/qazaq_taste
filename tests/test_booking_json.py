"""HW9: JSON booking extraction, retry, Python validation, missing fields, bookings.csv."""

import csv
import json
import re
from datetime import date, datetime

import pytest

from bot.database.csv_store import CSV_FIELDS, BookingsCsv, CsvFormatError
from bot.services.ai_service import OllamaUnavailableError
from bot.services.booking_draft import (
    check_draft,
    is_confirmation,
    is_rejection,
    merge,
    normalize_phone_11,
)
from bot.services.booking_extraction import (
    EXTRACTION_PROMPT_PATH,
    RETRY_MESSAGE,
    BookingExtractor,
    BookingJSONError,
    extract_by_rules,
    looks_like_booking,
    parse_booking_json,
)
from bot.services.booking_service import ValidationError

TODAY = date(2026, 11, 24)            # Tuesday
NOW = datetime(2026, 11, 24, 12, 0)

VALID = {"intent": "booking", "date": "2026-11-25", "time": "19:00", "guests": 4,
         "name": None, "phone": None, "missing": ["name", "phone"]}


class FakeClient:
    """Returns prepared raw answers one by one and records every call."""

    def __init__(self, *answers, error: Exception | None = None):
        self.answers = list(answers)
        self.error = error
        self.calls: list[dict] = []

    async def chat(self, messages, json_mode=False, temperature=None):
        self.calls.append({"messages": [dict(m) for m in messages], "json_mode": json_mode,
                           "temperature": temperature})
        if self.error:
            raise self.error
        return self.answers.pop(0)


def extractor(client, today=TODAY) -> BookingExtractor:
    return BookingExtractor(client, today=lambda: today)


# ---- JSON parsing ------------------------------------------------------------------
def test_parse_valid_json():
    data = parse_booking_json(json.dumps(VALID))
    assert data["date"] == "2026-11-25" and data["guests"] == 4
    assert data["missing"] == ["name", "phone"]


def test_parse_recomputes_missing_and_accepts_numeric_string():
    raw = dict(VALID, guests="4", missing=[])  # the model "forgot" missing fields
    assert parse_booking_json(json.dumps(raw))["missing"] == ["name", "phone"]


def test_parse_tolerates_code_fence_only():
    assert parse_booking_json("```json\n" + json.dumps(VALID) + "\n```")["time"] == "19:00"


@pytest.mark.parametrize("raw", [
    "Конечно! " + json.dumps(VALID),                     # text before JSON
    json.dumps(VALID) + " Готово.",                      # text after JSON
    "[1, 2, 3]",                                         # not an object
    json.dumps({k: v for k, v in VALID.items() if k != "phone"}),   # key missing
    json.dumps(dict(VALID, date="25.11.2026")),          # wrong date format
    json.dumps(dict(VALID, time="7 pm")),                # wrong time format
    json.dumps(dict(VALID, guests="four")),              # wrong type
    json.dumps(dict(VALID, intent="order")),             # unknown intent
    "",
])
def test_parse_rejects_invalid(raw):
    with pytest.raises(BookingJSONError):
        parse_booking_json(raw)


# ---- extraction call, dynamic date, retry ----------------------------------------------
async def test_extraction_uses_llm_json_mode():
    client = FakeClient(json.dumps(VALID))
    result = await extractor(client).extract("Столик на завтра в 19:00 на 4 человек")
    assert result.status == "ok" and result.source == "llm" and result.attempts == 1
    assert client.calls[0]["json_mode"] is True and client.calls[0]["temperature"] == 0
    assert client.calls[0]["messages"][-1]["content"] == "Столик на завтра в 19:00 на 4 человек"


async def test_today_is_passed_dynamically():
    for today, tomorrow in ((date(2026, 11, 24), "2026-11-25"), (date(2027, 2, 28), "2027-03-01")):
        client = FakeClient(json.dumps(VALID))
        await extractor(client, today).extract("завтра")
        system = client.calls[0]["messages"][0]["content"]
        assert f"Today is {today.isoformat()}" in system
        assert f"-> {tomorrow}" in system
        assert "{{" not in system  # every placeholder was filled


def test_prompt_file_has_no_hardcoded_dates():
    assert not re.search(r"20\d\d-\d\d-\d\d", EXTRACTION_PROMPT_PATH.read_text(encoding="utf-8"))


async def test_invalid_json_triggers_exactly_one_retry():
    client = FakeClient("Sure, here it is: {broken", json.dumps(VALID))
    result = await extractor(client).extract("столик на завтра")
    assert result.status == "ok" and result.attempts == 2
    assert len(client.calls) == 2
    assert client.calls[1]["messages"][-1]["content"] == RETRY_MESSAGE


async def test_two_invalid_answers_give_up():
    client = FakeClient("not json", "still not json", json.dumps(VALID))
    result = await extractor(client).extract("столик на завтра")
    assert result.status == "invalid" and result.data is None
    assert len(client.calls) == 2  # no third call


async def test_model_unavailable_uses_rules():
    client = FakeClient(error=OllamaUnavailableError("down"))
    result = await extractor(client).extract("Хочу забронировать столик на завтра в 19:00 на 4 человек")
    assert result.status == "ok" and result.source == "rules"
    assert result.data == {"intent": "booking", "date": "2026-11-25", "time": "19:00", "guests": 4,
                           "name": None, "phone": None, "missing": ["name", "phone"]}


async def test_known_data_and_asked_field_are_in_prompt():
    client = FakeClient(json.dumps(VALID))
    await extractor(client).extract("19:00", known={"date": "2026-11-25"}, asked="time")
    system = client.calls[0]["messages"][0]["content"]
    assert '"date": "2026-11-25"' in system and "asked the guest for: time" in system


# ---- rule-based fallback --------------------------------------------------------------------
@pytest.mark.parametrize("text,asked,expected", [
    ("Забронируйте на 25 ноября в 7 вечера, нас вдвоём. Меня зовут Жомарт, +7 701 123 45 67", None,
     {"date": "2026-11-25", "time": "19:00", "guests": 2, "name": "Жомарт", "phone": "+77011234567"}),
    ("Book a table for 2 tomorrow at 8 pm", None, {"date": "2026-11-25", "time": "20:00", "guests": 2}),
    ("столик на 12.12 к 20", None, {"date": "2026-12-12", "time": "20:00", "guests": None}),
    ("19", "time", {"time": "19:00"}),
    ("Айгерим", "name", {"name": "Айгерим"}),
])
def test_rules_extraction(text, asked, expected):
    data = extract_by_rules(text, TODAY, asked)
    assert data["intent"] == "booking"
    for key, value in expected.items():
        assert data[key] == value


def test_rules_never_invent_values():
    data = extract_by_rules("Хочу забронировать столик", TODAY)
    assert data["intent"] == "booking"
    assert all(data[f] is None for f in ("date", "time", "guests", "name", "phone"))
    assert data["missing"] == ["date", "time", "guests", "name", "phone"]


def test_looks_like_booking():
    assert looks_like_booking("Можно забронировать столик?")
    assert looks_like_booking("Үстел брондау керек")
    assert looks_like_booking("I want to book a table")
    assert not looks_like_booking("Сколько стоит бешбармак?")


# ---- Python validation --------------------------------------------------------------------
def full(**kw) -> dict:
    values = {"date": "2026-11-25", "time": "19:00", "guests": 4, "name": "Жомарт", "phone": "+77011234567"}
    values.update(kw)
    return values


def codes(check) -> dict:
    return {f: e.code for f, e in check.errors}


def test_complete_valid_draft():
    check = check_draft(full(), NOW)
    assert check.complete and not check.errors
    assert check.draft["phone"] == "+77011234567"


def test_past_date_rejected():
    check = check_draft(full(date="2026-11-20"), NOW)
    assert codes(check) == {"date": "err_date_past"}
    assert check.draft["date"] is None and check.next_field == "date"


@pytest.mark.parametrize("value", ["09:00", "10:59", "22:30", "23:30"])
def test_time_outside_opening_hours_rejected(value):
    # 25.11.2026 is a Wednesday: open 11:00–23:00, last booking 22:00 (from bot/data/menu.py)
    check = check_draft(full(time=value), NOW)
    assert codes(check) == {"time": "err_time_hours"}


def test_friday_allows_later_time():
    assert check_draft(full(date="2026-11-27", time="23:00"), NOW).complete


def test_time_today_already_passed():
    assert codes(check_draft(full(date="2026-11-24", time="11:30"), NOW)) == {"time": "err_time_past"}


@pytest.mark.parametrize("phone,ok", [
    ("+77011234567", True), ("87011234567", True), ("8 (701) 123-45-67", True),
    ("+7701123456", False), ("+770112345678", False), ("12345", False), ("phone", False),
])
def test_phone_must_have_11_digits(phone, ok):
    if ok:
        assert normalize_phone_11(phone) == "+77011234567"
    else:
        with pytest.raises(ValidationError):
            normalize_phone_11(phone)


def test_missing_order_and_single_next_question():
    check = check_draft({"date": "2026-11-25", "time": None, "guests": 4, "name": None, "phone": None}, NOW)
    assert check.missing == ["time", "name", "phone"]
    assert check.next_field == "time"  # only ONE question: about the first missing field


def test_merge_keeps_collected_data():
    known = {"date": "2026-11-25", "time": None, "guests": 4, "name": None, "phone": None}
    merged = merge(known, {"date": None, "time": "19:00", "guests": None, "name": None, "phone": None})
    assert merged == {"date": "2026-11-25", "time": "19:00", "guests": 4, "name": None, "phone": None}
    assert merge(merged, {"time": "20:00"})["time"] == "20:00"  # a correction overrides


@pytest.mark.parametrize("text", ["да", "Да", "ДА!", "подтверждаю", "Подтверждаю бронь", "иә", "yes"])
def test_confirmation_words(text):
    assert is_confirmation(text)


@pytest.mark.parametrize("text", ["да, но в 20:00", "может быть", "нет", ""])
def test_not_confirmation(text):
    assert not is_confirmation(text)


def test_rejection_words():
    assert is_rejection("Нет") and is_rejection("отмена") and not is_rejection("да")


# ---- bookings.csv --------------------------------------------------------------------------
def row(**kw):
    values = {"intent": "booking", "date": "2026-11-25", "time": "19:00", "guests": 4, "name": "Жомарт",
              "phone": "+77011234567", "code": "QT-1"}
    values.update(kw)
    return values


def test_csv_created_with_header(tmp_path):
    store = BookingsCsv(tmp_path / "bookings.csv")
    assert store.read_all() == []
    store.append(row())
    with (tmp_path / "bookings.csv").open(encoding="utf-8-sig", newline="") as f:
        lines = list(csv.reader(f))
    assert lines[0] == CSV_FIELDS
    assert lines[1][:6] == ["booking", "2026-11-25", "19:00", "4", "Жомарт", "+77011234567"]


def test_csv_appends_without_touching_existing_rows(tmp_path):
    store = BookingsCsv(tmp_path / "bookings.csv")
    store.append(row(code="QT-1"))
    before = (tmp_path / "bookings.csv").read_bytes()
    store.append(row(code="QT-2", name="Айгерим"))
    after = (tmp_path / "bookings.csv").read_bytes()
    assert after.startswith(before)
    assert [r["code"] for r in store.read_all()] == ["QT-1", "QT-2"]


def test_csv_quotes_special_characters(tmp_path):
    store = BookingsCsv(tmp_path / "bookings.csv")
    store.append(row(name='Анна, "VIP"\nновая строка'))
    assert store.read_all()[0]["name"] == 'Анна, "VIP"\nновая строка'


def test_csv_refuses_unexpected_header(tmp_path):
    path = tmp_path / "bookings.csv"
    path.write_text("a,b,c\n1,2,3\n", encoding="utf-8")
    with pytest.raises(CsvFormatError):
        BookingsCsv(path).append(row())
    assert path.read_text(encoding="utf-8") == "a,b,c\n1,2,3\n"  # not corrupted


# ---- regression: informational question about booking vs. booking request -----------------
from bot.services.booking_extraction import classify_booking_message  # noqa: E402

INQUIRIES = [
    "Как забронировать столик?",
    "Вы принимаете бронирования?",
    "До скольки можно забронировать?",
    "Как забронировать столик на пятницу вечером и до скольки вы работаете?",
    "Нужно ли бронировать столик заранее?",
    "Хочу узнать, как забронировать столик",
    "Можно забронировать столик?",
    "How can I book a table?",
    "Do you take reservations?",
    "Үстелді қалай брондауға болады?",
]
REQUESTS = [
    "Хочу забронировать столик",
    "Забронируйте столик на завтра на 4 человек",
    "Хотели бы забронировать столик на субботу",
    "Мне нужно забронировать столик на 19:00",
    "Столик на завтра в 19:00 на четверых",
    "Можно забронировать столик на завтра в 19:00?",
    "Book a table for 2 tomorrow at 8 pm",
    "I'd like to book a table",
    "Үстел брондау керек",
]


@pytest.mark.parametrize("text", INQUIRIES)
def test_booking_inquiry_is_not_a_request(text):
    assert classify_booking_message(text, TODAY) == "inquiry"
    assert extract_by_rules(text, TODAY)["intent"] == "other"


@pytest.mark.parametrize("text", REQUESTS)
def test_booking_request_is_recognised(text):
    assert classify_booking_message(text, TODAY) == "request"
    assert extract_by_rules(text, TODAY)["intent"] == "booking"


def test_unrelated_message_is_none():
    assert classify_booking_message("Сколько стоит бешбармак?", TODAY) == "none"


def test_answers_inside_the_dialog_are_still_booking():
    # inside the flow a short answer to the asked question is not an "inquiry"
    assert extract_by_rules("19:00", TODAY, asked="time")["intent"] == "booking"
    assert extract_by_rules("Как?", TODAY, asked="time")["intent"] == "other"


def test_extraction_prompt_explains_inquiry_vs_request():
    text = EXTRACTION_PROMPT_PATH.read_text(encoding="utf-8")
    assert "Как забронировать столик?" in text and "Хочу забронировать столик" in text
