"""Deterministic calculations for the AI consultant ("PROGRAM CALCULATIONS").

The language model is good at understanding text and bad at arithmetic. So for
money, numbers of guests and times the program does the work:

* a bill for several dishes/drinks — items and quantities are recognised in the
  guest's message, prices come from bot/data/menu.py, Python adds them up and
  applies the 10 % service charge;
* a number of guests — compared with the booking limit and hall capacities;
* being late for a booking — the expected arrival time is computed and checked
  against today's opening hours.

The results are passed to the model as trusted facts (it must copy them, not
recalculate) and are also used by the rule-based fallback when the model is down.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from bot.data import menu as data
from bot.data.menu import Dish
from bot.services.booking_service import opening_window
from bot.services.menu_service import MenuService, format_kzt
from bot.services.proposal_service import MAX_EVENT_GUESTS, apply_service_charge

# Words/stems that identify a dish in a message (parsing helpers, not menu facts).
# Longer, more specific phrases are matched first; matched text is consumed.
DISH_ALIASES: dict[str, list[str]] = {
    "beshbarmak": ["бешбармак", "бесбармақ", "beshbarmak"],
    "kazy_karta": ["казы-карт", "казы карт", "ассорти казы", "қазы-қарта", "kazy & karta", "kazy and karta"],
    "kuyrdak": ["куырдак", "қуырдақ", "kuyrdak"],
    "manty": ["мант", "manty"],
    "plov": ["плов", "палау", "plov"],
    "baursak": ["баурсак", "бауырсақ", "baursak"],
    "horse_medallions": ["медальон", "medallion"],
    "lagman": ["лагман", "лағман", "lagman"],
    "lamb_shashlik": ["шашлык", "кәуап", "shashlik"],
    "balkhash_zander": ["судак", "көксерке", "zander"],
    "pumpkin_chickpea": ["тыкв\\w* с нут", "томлён", "томлен", "нутом", "chickpea"],
    "samsa": ["самс", "samsa"],
    "horse_tartare": ["тартар", "tartare"],
    "kurt_platter": ["ассорти курт", "иримшик", "ірімшік", "irimshik"],
    "chebureki": ["чебурек", "шебурек", "cheburek"],
    "achichuk": ["ачичук", "achichuk"],
    "kazy_salad": ["салат с казы", "kazy salad", "kazy and roasted pepper"],
    "beet_kurt_salad": ["свёкл", "свекл", "қызылша", "beetroot"],
    "kumys": ["кумыс", "қымыз", "kumys"],
    "shubat": ["шубат", "шұбат", "shubat"],
    "kazakh_tea": ["чай", "чая", "чаю", "шай", "tea"],
    "ayran": ["айран", "ayran"],
    "sea_buckthorn_mors": ["морс", "mors"],
    "chak_chak": ["чак-чак", "чакчак", "шақ-шақ", "chak-chak", "chak chak"],
    "zhent": ["жент", "zhent"],
    "talkan_tiramisu": ["тирамису", "tiramisu"],
}

NUMBER_WORDS = {
    "один": 1, "одна": 1, "одну": 1, "одно": 1, "два": 2, "две": 2, "три": 3, "четыре": 4, "пять": 5,
    "шесть": 6, "семь": 7, "восемь": 8, "девять": 9, "десять": 10, "пара": 2, "пару": 2,
    "бір": 1, "екі": 2, "үш": 3, "төрт": 4, "бес": 5, "алты": 6,
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "a": 1, "an": 1,
}
_QTY = r"(\d{1,3}|" + "|".join(sorted(NUMBER_WORDS, key=len, reverse=True)) + r")"
SEPARATORS = re.compile(r"[,;\n+]|(?<!\w)(?:и|а также|плюс|and|және|мен)(?!\w)", re.IGNORECASE)
BILL_CUES = re.compile(
    r"сч[её]т|посчита|подсчита|итог|сколько (?:будет|выйдет|всего|стоит|заплат)|во сколько обойд|"
    r"сумм|bill|total|how much|есепте|қанша", re.IGNORECASE)
GUEST_RE = re.compile(r"(\d{1,4})\s*(?:человек|чел\b|гост\w*|персон\w*|people|persons|guests|адам|қонақ)",
                      re.IGNORECASE)
LATE_RE = re.compile(r"опозда\w*|задерж\w*|\blate\b|кешіг\w*", re.IGNORECASE)
TIME_RE = re.compile(r"(?<!\d)(\d{1,2}):(\d{2})(?!\d)")
DELAY_PATTERNS = [
    (re.compile(r"полтора\s+час", re.I), lambda m: 90),
    (re.compile(r"полчаса|half an hour", re.I), lambda m: 30),
    (re.compile(r"(\d{1,3})\s*(?:мин|minutes?|mins?|минут)", re.I), lambda m: int(m.group(1))),
    (re.compile(r"мин\w*\s+на\s+(\d{1,3})(?![\d:])", re.I), lambda m: int(m.group(1))),        # "минут на 40"
    (re.compile(r"(?:опозда|задерж)\w*\s+(?:на\s+)?(\d{1,3})(?![\d:])", re.I), lambda m: int(m.group(1))),
    (re.compile(r"(\d{1,2})\s*(?:час|hour)", re.I), lambda m: int(m.group(1)) * 60),
    (re.compile(r"(?<!\w)(?:на\s+)?час(?!\w)|an hour", re.I), lambda m: 60),
]


# --------------------------------------------------------------------------- #
# Bill
# --------------------------------------------------------------------------- #
@dataclass
class BillLine:
    dish: Dish
    qty: int

    @property
    def amount(self) -> int:
        return self.dish.price * self.qty


@dataclass
class Bill:
    lines: list[BillLine]

    @property
    def subtotal(self) -> int:
        return sum(line.amount for line in self.lines)

    @property
    def service(self) -> int:
        return apply_service_charge(self.subtotal)

    @property
    def total(self) -> int:
        return self.subtotal + self.service


def _segment_start(text: str, pos: int) -> int:
    start = 0
    for m in SEPARATORS.finditer(text, 0, pos):
        start = m.end()
    return start


def parse_order(text: str, menu: MenuService) -> list[BillLine]:
    """Recognise dishes and quantities: "2 бешбармака, три айрана и чай" -> [(beshbarmak, 2), (ayran, 3), (tea, 1)]."""
    low = (text or "").lower()
    consumed = [False] * len(low)
    found: dict[str, tuple[int, int]] = {}  # dish_id -> (position, qty)
    candidates = [(alias, dish_id) for dish_id, aliases in DISH_ALIASES.items() for alias in aliases]
    candidates.sort(key=lambda c: len(c[0]), reverse=True)
    for alias, dish_id in candidates:
        for m in re.finditer(rf"(?<!\w){alias}", low):
            if any(consumed[m.start():m.end()]):
                continue
            for i in range(m.start(), m.end()):
                consumed[i] = True
            if dish_id in found:
                continue
            segment = low[_segment_start(low, m.start()):m.start()]
            after = low[m.end():m.end() + 25]
            qty = 1
            # "2 бешбармака", "три порции плова", "2 x айран" — a number right before the dish name
            before_q = re.search(rf"(?<!\w){_QTY}(?!\w)\s*(?:x|х|×|шт\.?|порц\w*|чашк\w*|стакан\w*|"
                                 rf"бокал\w*|чайник\w*)?\s*$", segment)
            # "айран x3", "айран — 2 шт"
            after_q = re.match(r"^\w*\s*(?:x|х|×)\s*(\d{1,3})", after) or \
                re.match(r"^\w*\s*[-—:]?\s*(\d{1,3})\s*(?:шт|порц|pcs)", after)
            if before_q:
                word = before_q.group(1)
                qty = int(word) if word.isdigit() else NUMBER_WORDS.get(word, 1)
            elif after_q:
                qty = int(after_q.group(1))
            found[dish_id] = (m.start(), max(1, min(qty, 999)))
    ordered = sorted(found.items(), key=lambda kv: kv[1][0])
    return [BillLine(menu.get(dish_id), qty) for dish_id, (_, qty) in ordered if menu.get(dish_id)]


def bill_from_text(text: str, menu: MenuService) -> Bill | None:
    """A bill is calculated only when the guest asks for a sum and lists items."""
    if not BILL_CUES.search(text or ""):
        return None
    lines = parse_order(text, menu)
    if not lines or (len(lines) == 1 and lines[0].qty == 1):
        return None
    return Bill(lines)


# --------------------------------------------------------------------------- #
# Guests and halls
# --------------------------------------------------------------------------- #
@dataclass
class GuestCheck:
    guests: int
    month: int
    fits: list[str] = field(default_factory=list)       # hall keys that fit
    too_small: list[str] = field(default_factory=list)  # hall keys that are too small
    off_season: list[str] = field(default_factory=list)

    @property
    def over_booking_limit(self) -> bool:
        return self.guests > data.BOOKING_MAX_GUESTS

    @property
    def over_total_capacity(self) -> bool:
        return self.guests > MAX_EVENT_GUESTS


def guests_from_text(text: str) -> int | None:
    m = GUEST_RE.search(text or "")
    return int(m.group(1)) if m else None


def check_guests(guests: int, on: date) -> GuestCheck:
    result = GuestCheck(guests, on.month)
    for key, hall in data.HALL_CAPACITY.items():
        season = hall["season"]
        if season and not season[0] <= on.month <= season[1]:
            result.off_season.append(key)
        elif guests <= hall["capacity"]:
            result.fits.append(key)
        else:
            result.too_small.append(key)
    return result


# --------------------------------------------------------------------------- #
# Being late for a booking
# --------------------------------------------------------------------------- #
@dataclass
class LateCheck:
    booked: datetime
    delay_min: int
    arrival: datetime
    open_from: str
    close_at: str
    within_hours: bool


def late_from_text(text: str, today: date) -> LateCheck | None:
    if not LATE_RE.search(text or ""):
        return None
    tm = TIME_RE.search(text)
    if not tm or int(tm.group(1)) > 23:
        return None
    delay = None
    rest = text[:tm.start()] + " " + text[tm.end():]
    for pattern, value in DELAY_PATTERNS:
        m = pattern.search(rest)
        if m:
            delay = value(m)
            break
    if delay is None:
        return None
    booked = datetime.combine(today, datetime.min.time()).replace(hour=int(tm.group(1)), minute=int(tm.group(2)))
    arrival = booked + timedelta(minutes=delay)
    open_h, close_h = data.OPENING_HOURS[today.weekday()]
    closing = datetime.combine(today, datetime.min.time()) + timedelta(hours=close_h)
    first, _ = opening_window(today)
    return LateCheck(booked, delay, arrival, first.strftime("%H:%M"), "00:00" if close_h == 24 else f"{close_h:02d}:00",
                     arrival < closing)


# --------------------------------------------------------------------------- #
# Facts for the model
# --------------------------------------------------------------------------- #
@dataclass
class Calculations:
    bill: Bill | None = None
    guests: GuestCheck | None = None
    late: LateCheck | None = None

    def __bool__(self) -> bool:
        return any((self.bill, self.guests, self.late))

    def as_prompt(self) -> str:
        """English facts block appended to the system message."""
        lines = ["## PROGRAM CALCULATIONS (computed by Python from the menu data — copy these numbers exactly, "
                 "do not recalculate)"]
        if self.bill:
            lines.append("Bill requested by the guest:")
            for line in self.bill.lines:
                lines.append(f"- {line.dish.name['ru']} / {line.dish.name['en']}: {line.qty} × "
                             f"{format_kzt(line.dish.price)} = {format_kzt(line.amount)}")
            lines.append(f"Subtotal: {format_kzt(self.bill.subtotal)}; service charge "
                         f"{data.SERVICE_CHARGE_PERCENT}%: {format_kzt(self.bill.service)}; "
                         f"TOTAL: {format_kzt(self.bill.total)}")
        if self.guests:
            g = self.guests
            hall = lambda k: data.HALL_CAPACITY[k]["name"]["en"] + f" (up to {data.HALL_CAPACITY[k]['capacity']})"  # noqa: E731
            lines.append(f"Number of guests mentioned: {g.guests}.")
            lines.append(f"Table booking through the bot allows 1–{data.BOOKING_MAX_GUESTS} guests: "
                         + ("EXCEEDED — a regular table booking is not possible, offer the event request flow "
                            "(\"🎉 Организовать мероприятие\")." if g.over_booking_limit else "within the limit."))
            if g.fits:
                lines.append("Halls that fit this group: " + ", ".join(hall(k) for k in g.fits) + ".")
            if g.too_small:
                lines.append("Halls that are TOO SMALL: " + ", ".join(hall(k) for k in g.too_small) + ".")
            if g.off_season:
                lines.append("Not available this month (seasonal): " + ", ".join(hall(k) for k in g.off_season) + ".")
            if g.over_total_capacity:
                lines.append(f"The group is larger than the restaurant's total capacity for events "
                             f"({MAX_EVENT_GUESTS}).")
        if self.late:
            lt = self.late
            lines.append(f"Late arrival: booked for {lt.booked:%H:%M}, delay {lt.delay_min} min -> expected arrival "
                         f"{lt.arrival:%H:%M}. Today's opening hours: {lt.open_from}–{lt.close_at}; the arrival is "
                         + ("within opening hours." if lt.within_hours else "AFTER closing time."))
            lines.append("The KNOWLEDGE BASE contains NO rule on how long a table is held for late guests — do not "
                         "invent one; advise the guest to call the restaurant.")
        return "\n".join(lines)


def calculate(text: str, menu: MenuService, today: date) -> Calculations:
    guests = guests_from_text(text)
    return Calculations(
        bill=bill_from_text(text, menu),
        guests=check_guests(guests, today) if guests else None,
        late=late_from_text(text, today),
    )
