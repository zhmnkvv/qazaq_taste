"""LLM-based extraction of booking details as JSON.

The guest's message is sent to the model with a separate instruction
(bot/prompts/booking_extraction_prompt.txt) that demands ONLY a JSON object.
Today's date is inserted from Python on every call, never hard-coded.

* The answer is parsed and its schema is checked in code.
* Invalid JSON -> the request is repeated ONCE.
* Invalid again -> status "invalid" (the bot asks the guest to repeat).
* Ollama unreachable -> a small rule-based extractor produces the same JSON
  structure, so the booking flow keeps working without the model.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from bot.config import BOT_DIR
from bot.services.ai_service import AIServiceError

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT_PATH = BOT_DIR / "prompts" / "booking_extraction_prompt.txt"
FIELDS = ("date", "time", "guests", "name", "phone")
REQUIRED_KEYS = ("intent", *FIELDS, "missing")
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
RETRY_MESSAGE = ("Your previous answer was not a valid JSON object with the required keys. "
                 "Reply again with ONLY the JSON object, nothing else.")

BOOKING_KEYWORDS = re.compile(
    r"(?<!\w)(брон|забронир|столик|резерв|book|reserv|table for|үстел|брондау)",
    re.IGNORECASE,
)


class BookingJSONError(ValueError):
    """The model output is not valid booking JSON."""


def looks_like_booking(text: str) -> bool:
    """Cheap pre-check so that only booking-like messages go to the extraction call."""
    return bool(BOOKING_KEYWORDS.search(text or ""))


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #
def parse_booking_json(raw: str) -> dict:
    """Parse and validate the model output. Raises BookingJSONError."""
    text = (raw or "").strip()
    # Tolerate a Markdown code fence around the object, nothing else.
    fence = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL)
    if fence:
        text = fence.group(1)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise BookingJSONError(f"not JSON: {exc.msg}") from None
    if not isinstance(data, dict):
        raise BookingJSONError("JSON is not an object")
    absent = [k for k in REQUIRED_KEYS if k not in data]
    if absent:
        raise BookingJSONError(f"missing keys: {absent}")

    intent = data["intent"]
    if intent not in ("booking", "other"):
        raise BookingJSONError("intent must be 'booking' or 'other'")

    result: dict = {"intent": intent}
    for key in ("date", "time", "name", "phone"):
        value = data[key]
        if value is not None and not isinstance(value, str):
            raise BookingJSONError(f"{key} must be a string or null")
        result[key] = value.strip() or None if isinstance(value, str) else None
    if result["date"] is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", result["date"]):
        raise BookingJSONError("date must be YYYY-MM-DD")
    if result["time"] is not None and not re.fullmatch(r"\d{1,2}:\d{2}", result["time"]):
        raise BookingJSONError("time must be HH:MM")

    guests = data["guests"]
    if isinstance(guests, str) and guests.strip().isdigit():
        guests = int(guests.strip())
    if guests is not None and (isinstance(guests, bool) or not isinstance(guests, int)):
        raise BookingJSONError("guests must be an integer or null")
    result["guests"] = guests

    missing = data["missing"]
    if not isinstance(missing, list) or not all(isinstance(m, str) for m in missing):
        raise BookingJSONError("missing must be a list of strings")
    # The final list is always recomputed by the program (see booking_draft.py).
    result["missing"] = [f for f in FIELDS if result[f] is None]
    return result


# --------------------------------------------------------------------------- #
# Rule-based fallback (used only when the model is unreachable)
# --------------------------------------------------------------------------- #
_REL_DATES = {
    0: ("сегодня", "бүгін", "today"),
    1: ("завтра", "ертең", "tomorrow"),
    2: ("послезавтра", "бүрсігүні", "day after tomorrow"),
}
_MONTHS = {"январ": 1, "феврал": 2, "март": 3, "апрел": 4, "ма": 5, "июн": 6, "июл": 7, "август": 8,
           "сентябр": 9, "октябр": 10, "ноябр": 11, "декабр": 12}
_GUEST_WORDS = r"(?:человек|чел|гост\w*|персон\w*|people|persons|guests|адам|қонақ)"
_NAME_RE = re.compile(r"(?:меня зовут|моё имя|мое имя|имя|my name is|i am|i'm|атым|есімім)\s*[:\-]?\s*"
                      r"([^\W\d_]+(?:[ -][^\W\d_]+)?)", re.IGNORECASE)
_PHONE_RE = re.compile(r"\+?\d[\d\s()\-]{8,18}\d")


def _nearest(day: int, month: int, today: date) -> date | None:
    try:
        candidate = date(today.year, month, day)
    except ValueError:
        return None
    if candidate < today:
        try:
            candidate = candidate.replace(year=today.year + 1)
        except ValueError:
            return None
    return candidate


def _rule_date(low: str, today: date) -> str | None:
    for offset in (2, 1, 0):  # "послезавтра" contains "завтра": check it first
        if any(word in low for word in _REL_DATES[offset]):
            return (today + timedelta(days=offset)).isoformat()
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", low)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.search(r"(?<![\d:])(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?(?![\d:])", low)
    if m:
        day, month = int(m.group(1)), int(m.group(2))
        if m.group(3):
            year = int(m.group(3)) + (2000 if len(m.group(3)) == 2 else 0)
            try:
                return date(year, month, day).isoformat()
            except ValueError:
                return None
        found = _nearest(day, month, today)
        return found.isoformat() if found else None
    m = re.search(r"(\d{1,2})\s+(январ|феврал|март|апрел|ма[яй]|июн|июл|август|сентябр|октябр|ноябр|декабр)", low)
    if m:
        key = "ма" if m.group(2).startswith("ма") and m.group(2) != "март" else m.group(2)
        found = _nearest(int(m.group(1)), _MONTHS[key], today)
        return found.isoformat() if found else None
    return None


def _rule_time(low: str, asked: str | None) -> str | None:
    # "19:30" (a dot is reserved for dates like 25.11)
    m = re.search(r"(?<!\d)(\d{1,2}):(\d{2})(?!\d)", low)
    if m:
        return f"{int(m.group(1)):02d}:{m.group(2)}"
    # "в 19", "к 7 вечера", "at 7 pm", "сағат 19-да"
    m = re.search(r"(?:(?<!\w)в|(?<!\w)к|(?<!\w)at|сағат)\s+(\d{1,2})(?![\d./])", low)
    if m:
        hour = int(m.group(1))
        if re.search(r"вечера|pm|кешкі", low) and hour < 12:
            hour += 12
        if 0 <= hour <= 23:
            return f"{hour:02d}:00"
    if asked == "time":
        m = re.fullmatch(r"(\d{1,2})(?:[.:](\d{2}))?", low.strip())
        if m and int(m.group(1)) <= 23:
            return f"{int(m.group(1)):02d}:{m.group(2) or '00'}"
    return None


def _rule_guests(low: str, asked: str | None) -> int | None:
    m = re.search(rf"(\d{{1,3}})\s*{_GUEST_WORDS}", low) or re.search(
        r"\bна\s+(\d{1,3})\b(?![.:/])(?!\s*(?:январ|феврал|март|апрел|ма[яй]|июн|июл|август|сентябр|октябр|"
        r"ноябр|декабр|час|утра|вечера))", low)
    m = m or re.search(r"\bfor\s+(\d{1,3})\b(?!\s*(?:pm|am|:|o'clock))", low)
    if m:
        return int(m.group(1))
    words = {"вдвоём": 2, "вдвоем": 2, "втроём": 3, "втроем": 3, "вчетвером": 4, "на двоих": 2, "на троих": 3,
             "на четверых": 4}
    for word, value in words.items():
        if word in low:
            return value
    if asked == "guests" and low.strip().isdigit():
        return int(low.strip())
    return None


def extract_by_rules(text: str, today: date, asked: str | None = None) -> dict:
    low = (text or "").lower().replace("ё", "е")
    phone_m = _PHONE_RE.search(text or "")
    phone = re.sub(r"[^\d+]", "", phone_m.group(0)) if phone_m else None
    without_phone = low.replace(phone_m.group(0).lower(), " ") if phone_m else low

    name = None
    m = _NAME_RE.search(text or "")
    if m:
        name = m.group(1).strip()
    elif asked == "name" and re.fullmatch(r"[^\W\d_]+(?:[ -][^\W\d_]+)?", (text or "").strip()):
        name = text.strip()

    data = {
        "date": _rule_date(without_phone, today),
        "time": _rule_time(without_phone, asked),
        "guests": _rule_guests(without_phone, asked),
        "name": name,
        "phone": phone,
    }
    has_any = any(v is not None for v in data.values())
    if asked:  # inside the booking dialog: any recognised value is an answer to the question
        intent = "booking" if has_any else "other"
    else:
        intent = "booking" if _classify(text, has_details=_has_details(data)) == "request" else "other"
    return {"intent": intent, **data, "missing": [f for f in FIELDS if data[f] is None]}


# --------------------------------------------------------------------------- #
# Inquiry about booking vs. an actual booking request
# --------------------------------------------------------------------------- #
# "Как забронировать?", "Вы принимаете бронирования?", "До скольки можно забронировать?" -> inquiry
# "Хочу забронировать столик", "Забронируйте столик на завтра на 4 человек"             -> request
REQUEST_MARKERS = re.compile(
    r"(?<!\w)(?:"
    r"хочу(?!\s+(?:узнать|спросить|уточнить))|хотим(?!\s+(?:узнать|спросить|уточнить))|"
    r"хотел[аи]?\s+бы(?!\s+(?:узнать|спросить|уточнить))|"
    r"забронируйте|забронируй|зарезервируйте|запишите|оформите|прошу\s+забронир\w*|давайте\s+забронир\w*|"
    r"бронирую|нужен\s+столик|нужно\s+забронир\w*|мне\s+нужно|нам\s+нужно|"
    r"i\s+want(?!\s+to\s+(?:know|ask))|i'?d\s+like|i\s+would\s+like|please\s+book|book\s+me|"
    r"book\s+a\s+table\s+for|reserve\s+a\s+table\s+for|"
    r"брондағым\s+келеді|брондап\s+беріңіз|брондаңыз|керек(?!\s+пе)"
    r")",
    re.IGNORECASE,
)
INQUIRY_MARKERS = re.compile(
    r"(?<!\w)(?:"
    r"как|каким\s+образом|принимаете|принимают|до\s+скольк\w*|во\s+сколько|нужно\s+ли|надо\s+ли|"
    r"обязательно\s+ли|заранее\s+ли|сколько\s+стоит|"
    r"опозда\w*|задержусь|задержимся|сохранится|i'?ll\s+be\s+late|кешігемін|"
    r"how|do\s+you|does\s+the|until\s+what|what\s+time|is\s+it\s+necessary|"
    r"қалай|қабылдайсыздар|керек\s+пе"
    r")(?!\w)",
    re.IGNORECASE,
)


# A message about an EXISTING booking (move / cancel / "у меня бронь") is never a new request,
# even with "хочу": "Хочу перенести бронь", "У меня бронь на 19:00, я опоздаю".
EXISTING_BOOKING_MARKERS = re.compile(
    r"(?<!\w)(?:перенес\w*|отмен\w*|у\s+(?:меня|нас)\s+(?:есть\s+)?бронь|мо[яюей]\w*\s+бро\w*|"
    r"my\s+(?:booking|reservation)|cancel\w*|reschedul\w*)",
    re.IGNORECASE,
)


def _has_details(data: dict) -> bool:
    return any(data.get(f) is not None for f in ("date", "time", "guests", "phone"))


def _classify(text: str, has_details: bool) -> str:
    if not looks_like_booking(text):
        return "none"
    if EXISTING_BOOKING_MARKERS.search(text):
        return "inquiry"
    if REQUEST_MARKERS.search(text):
        return "request"
    if INQUIRY_MARKERS.search(text):
        return "inquiry"
    if "?" in text and not has_details:  # "Можно забронировать столик?" without any details
        return "inquiry"
    return "request"  # "Столик на завтра в 19:00 на четверых", "Бронь на субботу"


def classify_booking_message(text: str, today: date) -> str:
    """'request' — the guest wants to book now; 'inquiry' — an informational question about
    booking (goes to the AI consultant); 'none' — not about booking at all."""
    details = extract_by_rules(text, today)  # cheap, no model call
    return _classify(text, has_details=_has_details(details))


# --------------------------------------------------------------------------- #
# Extractor
# --------------------------------------------------------------------------- #
@dataclass
class ExtractionResult:
    status: str  # "ok" | "invalid"
    data: dict | None
    source: str  # "llm" | "rules"
    attempts: int


class BookingExtractor:
    def __init__(self, client, today: Callable[[], date], prompt_path: Path = EXTRACTION_PROMPT_PATH) -> None:
        self.client = client
        self.today = today
        self.template = prompt_path.read_text(encoding="utf-8")

    def build_prompt(self, known: dict | None = None, asked: str | None = None) -> str:
        today = self.today()
        known_json = json.dumps({f: (known or {}).get(f) for f in FIELDS}, ensure_ascii=False)
        replacements = {
            "{{TODAY}}": today.isoformat(),
            "{{WEEKDAY}}": WEEKDAYS[today.weekday()],
            "{{TOMORROW}}": (today + timedelta(days=1)).isoformat(),
            "{{AFTER_TOMORROW}}": (today + timedelta(days=2)).isoformat(),
            "{{KNOWN}}": known_json if known else "nothing yet",
            "{{ASKED}}": asked or "nothing (this is the first message)",
        }
        prompt = self.template
        for key, value in replacements.items():
            prompt = prompt.replace(key, value)
        return prompt

    async def extract(self, text: str, known: dict | None = None, asked: str | None = None) -> ExtractionResult:
        messages = [
            {"role": "system", "content": self.build_prompt(known, asked)},
            {"role": "user", "content": (text or "")[:1000]},
        ]
        attempts = 0
        for attempt in (1, 2):  # first try + exactly one retry
            attempts = attempt
            try:
                raw = await self.client.chat(messages, json_mode=True, temperature=0)
            except AIServiceError as exc:
                logger.warning("Booking extraction: model unavailable (%s), using rules", type(exc).__name__)
                return ExtractionResult("ok", extract_by_rules(text, self.today(), asked), "rules", attempts)
            try:
                return ExtractionResult("ok", parse_booking_json(raw), "llm", attempts)
            except BookingJSONError as exc:
                logger.warning("Booking extraction: invalid JSON on attempt %s (%s)", attempt, exc)
                messages += [{"role": "assistant", "content": raw[:2000]},
                             {"role": "user", "content": RETRY_MESSAGE}]
        return ExtractionResult("invalid", None, "llm", attempts)
