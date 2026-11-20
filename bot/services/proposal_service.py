"""Deterministic budget and commercial-proposal calculations.

All numbers are computed here from the menu data and tariffs. The AI model is
never asked to produce prices or totals.
"""

from __future__ import annotations

import math
import secrets
import string
from dataclasses import dataclass, field
from datetime import date
from html import escape

from bot.data import menu as data
from bot.data.menu import Dish
from bot.database.models import EventRequest
from bot.database.repository import EventRepository
from bot.services.menu_service import MenuService, format_kzt

MAX_EVENT_GUESTS = 140  # main hall + terrace
MIN_BUDGET_PER_PERSON = 1000

# Course pools: which dishes can play which role in a per-person set.
COURSE_ORDER = ["main", "salad", "starter", "dessert", "drink"]
REQUIRED_COURSES = {"main", "drink"}
OPTIONAL_PRIORITY = ["salad", "dessert", "starter"]
# National dishes that are served as shared starters rather than a main course.
STARTER_LIKE_NATIONAL = {"kazy_karta", "baursak"}

COURSE_LABELS = {
    "main": data.t("Горячее", "Ыстық тағам", "Main course"),
    "salad": data.t("Салат", "Салат", "Salad"),
    "starter": data.t("Закуска", "Тіскебасар", "Starter"),
    "dessert": data.t("Десерт", "Десерт", "Dessert"),
    "drink": data.t("Напиток", "Сусын", "Drink"),
}


def course_pools(menu: MenuService, vegetarian: bool = False) -> dict[str, list[Dish]]:
    pools: dict[str, list[Dish]] = {c: [] for c in COURSE_ORDER}
    for dish in menu.dishes:
        if vegetarian and not dish.is_vegetarian:
            continue
        if dish.category in {"national", "main"} and dish.id not in STARTER_LIKE_NATIONAL:
            pools["main"].append(dish)
        elif dish.category in {"national", "starters"}:
            pools["starter"].append(dish)
        elif dish.category == "salads":
            pools["salad"].append(dish)
        elif dish.category == "desserts":
            pools["dessert"].append(dish)
        elif dish.category == "drinks":
            pools["drink"].append(dish)
    for pool in pools.values():
        pool.sort(key=lambda d: (d.price, d.id))
    return pools


@dataclass
class MenuSet:
    items: dict[str, Dish]  # course -> dish
    feasible: bool
    minimum_price: int  # cheapest possible set with required courses

    @property
    def price(self) -> int:
        return sum(d.price for d in self.items.values())


def select_menu_set(food_budget_pp: int, menu: MenuService, vegetarian: bool = False) -> MenuSet:
    """Pick the best per-person set of dishes that fits ``food_budget_pp``.

    1. Required courses (main + drink) always included.
    2. Optional courses are added by priority while the cheapest variants fit.
    3. Each course is then upgraded to the most expensive dish that still
       leaves room for the cheapest options of the remaining courses.
    """
    pools = course_pools(menu, vegetarian)
    courses = [c for c in COURSE_ORDER if pools[c]]
    required = [c for c in courses if c in REQUIRED_COURSES]
    cheapest = {c: pools[c][0].price for c in courses}
    minimum_price = sum(cheapest[c] for c in required)

    if food_budget_pp < minimum_price:
        return MenuSet({c: pools[c][0] for c in required}, feasible=False, minimum_price=minimum_price)

    chosen_courses = list(required)
    spent_min = minimum_price
    for course in OPTIONAL_PRIORITY:
        if course in courses and spent_min + cheapest[course] <= food_budget_pp:
            chosen_courses.append(course)
            spent_min += cheapest[course]
    chosen_courses.sort(key=COURSE_ORDER.index)

    items: dict[str, Dish] = {}
    spent = 0
    for i, course in enumerate(chosen_courses):
        reserve = sum(cheapest[c] for c in chosen_courses[i + 1:])
        allowed = food_budget_pp - spent - reserve
        candidates = [d for d in pools[course] if d.price <= allowed]
        pick = candidates[-1]  # most expensive that fits (always exists)
        items[course] = pick
        spent += pick.price
    return MenuSet(items, feasible=True, minimum_price=minimum_price)


def apply_service_charge(amount: int) -> int:
    return round(amount * data.SERVICE_CHARGE_PERCENT / 100)


# --------------------------------------------------------------------------- #
# Budget calculator
# --------------------------------------------------------------------------- #
@dataclass
class BudgetResult:
    guests: int
    total_budget: int
    budget_per_person: int
    menu_set: MenuSet
    food_total: int
    service_charge: int
    grand_total: int

    @property
    def remaining(self) -> int:
        return self.total_budget - self.grand_total

    @property
    def per_person(self) -> int:
        return math.ceil(self.grand_total / self.guests)


def validate_guests(guests: int, maximum: int = MAX_EVENT_GUESTS) -> int:
    if not isinstance(guests, int) or guests < 1 or guests > maximum:
        raise ValueError(f"guests must be between 1 and {maximum}")
    return guests


def calculate_budget(guests: int, total_budget: int, menu: MenuService, vegetarian: bool = False) -> BudgetResult:
    validate_guests(guests)
    if total_budget <= 0:
        raise ValueError("budget must be positive")
    per_person = total_budget // guests
    food_budget_pp = math.floor(per_person * 100 / (100 + data.SERVICE_CHARGE_PERCENT))
    menu_set = select_menu_set(food_budget_pp, menu, vegetarian)
    food_total = menu_set.price * guests
    charge = apply_service_charge(food_total)
    return BudgetResult(guests, total_budget, per_person, menu_set, food_total, charge, food_total + charge)


# --------------------------------------------------------------------------- #
# Commercial proposal
# --------------------------------------------------------------------------- #
SERVICE_KEYWORDS = {
    "dombra": ("домбр", "домбыр", "dombra", "музык", "music"),
    "photographer": ("фото", "photo", "сурет"),
    "host": ("ведущ", "тамад", "асаба", "host", "mc"),
    "projector": ("проектор", "projector", "экран", "screen", "презентац", "presentation"),
}
VEGETARIAN_KEYWORDS = ("вегетариан", "vegetarian", "vegan", "веган", "без мяса", "етсіз")


def detect_services(wishes: str) -> list[str]:
    low = (wishes or "").lower()
    words = set(low.replace(",", " ").replace(".", " ").split())
    found = []
    for service, keys in SERVICE_KEYWORDS.items():
        if any((k in words) if len(k) <= 3 else (k in low) for k in keys):
            found.append(service)
    return found


def wants_vegetarian(wishes: str) -> bool:
    low = (wishes or "").lower()
    return any(k in low for k in VEGETARIAN_KEYWORDS)


@dataclass
class ProposalInput:
    event_type: str
    guests: int
    event_date: date
    budget_per_person: int
    wishes: str = ""
    phone: str = ""


@dataclass
class Proposal:
    input: ProposalInput
    menu_set: MenuSet
    services: list[str]
    food_per_person: int
    food_total: int
    service_charge: int
    services_total: int
    grand_total: int
    vegetarian: bool
    warnings: list[str] = field(default_factory=list)

    @property
    def price_per_person(self) -> int:
        return math.ceil(self.grand_total / self.input.guests)

    @property
    def budget_total(self) -> int:
        return self.input.budget_per_person * self.input.guests

    @property
    def within_budget(self) -> bool:
        return self.grand_total <= self.budget_total


class ProposalService:
    def __init__(self, menu: MenuService, repo: EventRepository | None = None) -> None:
        self.menu = menu
        self.repo = repo

    def build(self, inp: ProposalInput) -> Proposal:
        if inp.event_type not in data.EVENT_TYPES:
            raise ValueError("unknown event type")
        validate_guests(inp.guests)
        if inp.budget_per_person < MIN_BUDGET_PER_PERSON:
            raise ValueError("budget per person is too small")

        event = data.EVENT_TYPES[inp.event_type]
        services = list(event["included_services"])
        for extra in detect_services(inp.wishes):
            if extra not in services:
                services.append(extra)
        services_total = sum(data.ADDITIONAL_SERVICES[s]["price"] for s in services)
        vegetarian = wants_vegetarian(inp.wishes)

        services_pp = math.ceil(services_total / inp.guests)
        food_budget_pp = math.floor(
            (inp.budget_per_person - services_pp) * 100 / (100 + data.SERVICE_CHARGE_PERCENT)
        )
        menu_set = select_menu_set(max(food_budget_pp, 0), self.menu, vegetarian)

        food_pp = menu_set.price
        food_total = food_pp * inp.guests
        charge = apply_service_charge(food_total)
        grand_total = food_total + charge + services_total

        warnings = []
        if inp.guests < event["min_guests"]:
            warnings.append("warn_min_guests")
        if not menu_set.feasible or grand_total > inp.budget_per_person * inp.guests:
            warnings.append("warn_over_budget")

        return Proposal(inp, menu_set, services, food_pp, food_total, charge, services_total,
                        grand_total, vegetarian, warnings)

    def save(self, telegram_id: int, proposal: Proposal, text: str) -> EventRequest:
        if self.repo is None:
            raise RuntimeError("repository is not configured")
        code = self._unique_code(proposal.input.event_date)
        req = EventRequest(
            code=code,
            telegram_id=telegram_id,
            event_type=proposal.input.event_type,
            guests=proposal.input.guests,
            event_date=proposal.input.event_date,
            budget_per_person=proposal.input.budget_per_person,
            price_per_person=proposal.price_per_person,
            total_price=proposal.grand_total,
            wishes=proposal.input.wishes,
            phone=proposal.input.phone,
            proposal_text=text,
        )
        return self.repo.add(req)

    def _unique_code(self, on_date: date) -> str:
        alphabet = string.ascii_uppercase + string.digits
        for _ in range(20):
            code = f"EV-{on_date:%y%m%d}-" + "".join(secrets.choice(alphabet) for _ in range(4))
            if not self.repo.code_exists(code):
                return code
        raise RuntimeError("Could not generate a unique event code")


# --------------------------------------------------------------------------- #
# Formatting
# --------------------------------------------------------------------------- #
_L = {
    "proposal_title": data.t("КОММЕРЧЕСКОЕ ПРЕДЛОЖЕНИЕ", "КОММЕРЦИЯЛЫҚ ҰСЫНЫС", "COMMERCIAL PROPOSAL"),
    "event": data.t("Мероприятие", "Іс-шара", "Event"),
    "date": data.t("Дата", "Күні", "Date"),
    "guests": data.t("Количество участников", "Қатысушылар саны", "Number of guests"),
    "menu": data.t("Предлагаемое меню (на 1 персону)", "Ұсынылатын мәзір (1 адамға)", "Proposed menu (per person)"),
    "food_pp": data.t("Меню на 1 персону", "1 адамға мәзір", "Menu per person"),
    "food_total": data.t("Меню на всех гостей", "Барлық қонаққа мәзір", "Menu for all guests"),
    "charge": data.t("Обслуживание", "Қызмет көрсету", "Service charge"),
    "services": data.t("Дополнительные услуги", "Қосымша қызметтер", "Additional services"),
    "no_services": data.t("не выбраны", "таңдалмаған", "none selected"),
    "optional": data.t("Можно добавить", "Қосуға болады", "Available on request"),
    "price_pp": data.t("Стоимость на 1 человека", "1 адамға құны", "Price per person"),
    "total": data.t("ОБЩАЯ СТОИМОСТЬ", "ЖАЛПЫ ҚҰНЫ", "TOTAL COST"),
    "budget": data.t("Ваш бюджет", "Сіздің бюджетіңіз", "Your budget"),
    "fits": data.t("✅ Укладывается в бюджет, остаток", "✅ Бюджетке сыяды, қалдық", "✅ Within budget, remaining"),
    "over": data.t("⚠️ Превышение бюджета на", "⚠️ Бюджеттен асуы", "⚠️ Over budget by"),
    "veg": data.t("🌱 Вегетарианский вариант меню", "🌱 Вегетариандық мәзір нұсқасы", "🌱 Vegetarian menu option"),
    "wishes": data.t("Пожелания", "Тілектер", "Wishes"),
    "summary": data.t("Итог", "Қорытынды", "Summary"),
    "summary_text": data.t(
        "Расчёт предварительный и выполнен автоматически по действующему меню и тарифам. "
        "Окончательные условия подтверждает менеджер ресторана после проверки даты и зала.",
        "Есеп алдын ала және қолданыстағы мәзір мен тарифтер бойынша автоматты түрде жасалды. "
        "Түпкілікті шарттарды күн мен залды тексергеннен кейін мейрамхана менеджері растайды.",
        "This is a preliminary estimate calculated automatically from the current menu and tariffs. "
        "Final terms are confirmed by the restaurant manager after checking date and hall availability.",
    ),
    "warn_min_guests": data.t(
        "⚠️ Для этого формата рекомендовано от {n} гостей — уточним условия с менеджером.",
        "⚠️ Бұл формат үшін {n} қонақтан бастап ұсынылады — шарттарды менеджермен нақтылаймыз.",
        "⚠️ This format is recommended from {n} guests — the manager will clarify the terms.",
    ),
    "min_budget": data.t(
        "Минимальный бюджет для этого формата: ~{v} на человека.",
        "Бұл формат үшін ең аз бюджет: адамына ~{v}.",
        "Minimum budget for this format: ~{v} per person.",
    ),
}


def minimum_budget_per_person(proposal: Proposal) -> int:
    services_pp = math.ceil(proposal.services_total / proposal.input.guests)
    food = proposal.menu_set.minimum_price
    return food + apply_service_charge(food) + services_pp


def format_proposal(proposal: Proposal, lang: str) -> str:
    p, inp = proposal, proposal.input
    ev_name = data.EVENT_TYPES[inp.event_type]["name"][lang]
    lines = [
        f"📋 <b>{_L['proposal_title'][lang]}</b>",
        "<b>Qazaq Taste</b> · " + escape(data.RESTAURANT["city"][lang]),
        "",
        f"🎉 <b>{_L['event'][lang]}:</b> {escape(ev_name)}",
        f"📅 <b>{_L['date'][lang]}:</b> {inp.event_date:%d.%m.%Y}",
        f"👥 <b>{_L['guests'][lang]}:</b> {inp.guests}",
        "",
        f"🍽 <b>{_L['menu'][lang]}:</b>",
    ]
    for course, dish in p.menu_set.items.items():
        lines.append(
            f"• {COURSE_LABELS[course][lang]}: {escape(dish.localized('name', lang))} — {format_kzt(dish.price)}"
        )
    if p.vegetarian:
        lines.append(_L["veg"][lang])
    lines += [
        "",
        f"💵 {_L['food_pp'][lang]}: {format_kzt(p.food_per_person)}",
        f"💵 {_L['food_total'][lang]}: {format_kzt(p.food_per_person)} × {inp.guests} = {format_kzt(p.food_total)}",
        f"🧑‍🍳 {_L['charge'][lang]} ({data.SERVICE_CHARGE_PERCENT}%): {format_kzt(p.service_charge)}",
        "",
        f"✨ <b>{_L['services'][lang]}:</b>",
    ]
    if p.services:
        for s in p.services:
            svc = data.ADDITIONAL_SERVICES[s]
            lines.append(f"• {escape(svc['name'][lang])} — {format_kzt(svc['price'])}")
    else:
        lines.append(f"• {_L['no_services'][lang]}")
    optional = [s for s in data.OPTIONAL_SERVICES if s not in p.services]
    if optional:
        opts = "; ".join(
            f"{data.ADDITIONAL_SERVICES[s]['name'][lang]} — {format_kzt(data.ADDITIONAL_SERVICES[s]['price'])}"
            for s in optional
        )
        lines.append(f"<i>{_L['optional'][lang]}: {escape(opts)}</i>")
    lines += [
        "",
        f"👤 <b>{_L['price_pp'][lang]}:</b> {format_kzt(p.price_per_person)}",
        f"💰 <b>{_L['total'][lang]}: {format_kzt(p.grand_total)}</b>",
        f"📊 {_L['budget'][lang]}: {format_kzt(inp.budget_per_person)} × {inp.guests} = {format_kzt(p.budget_total)}",
    ]
    diff = p.budget_total - p.grand_total
    if diff >= 0:
        lines.append(f"{_L['fits'][lang]}: {format_kzt(diff)}")
    else:
        lines.append(f"{_L['over'][lang]} {format_kzt(-diff)}")
        lines.append(_L["min_budget"][lang].format(v=format_kzt(minimum_budget_per_person(p))))
    if "warn_min_guests" in p.warnings:
        lines.append(_L["warn_min_guests"][lang].format(n=data.EVENT_TYPES[inp.event_type]["min_guests"]))
    if inp.wishes:
        lines += ["", f"📝 <b>{_L['wishes'][lang]}:</b> {escape(inp.wishes)}"]
    lines += ["", f"ℹ️ <b>{_L['summary'][lang]}:</b> {_L['summary_text'][lang]}"]
    return "\n".join(lines)


_B = {
    "title": data.t("💰 Расчёт бюджета", "💰 Бюджет есебі", "💰 Budget estimate"),
    "guests": data.t("Гостей", "Қонақтар", "Guests"),
    "budget": data.t("Бюджет", "Бюджет", "Budget"),
    "pp": data.t("на человека", "адамына", "per person"),
    "set": data.t("Рекомендуемый набор на 1 персону", "1 адамға ұсынылатын жиынтық", "Recommended set per person"),
    "food": data.t("Блюда", "Тағамдар", "Food"),
    "charge": data.t("Обслуживание", "Қызмет көрсету", "Service charge"),
    "total": data.t("Итого", "Барлығы", "Total"),
    "left": data.t("Остаток бюджета", "Бюджет қалдығы", "Budget remaining"),
    "not_enough": data.t(
        "⚠️ Бюджета недостаточно даже для минимального набора (горячее + напиток). "
        "Нужно минимум {v} на человека с учётом обслуживания.",
        "⚠️ Бюджет ең аз жиынтыққа да жетпейді (ыстық тағам + сусын). "
        "Қызмет көрсетуді қоса адамына кемінде {v} қажет.",
        "⚠️ The budget does not cover even the minimum set (main + drink). "
        "You need at least {v} per person including service.",
    ),
    "note": data.t(
        "Расчёт ориентировочный, по ценам текущего меню.",
        "Есеп шамамен, қазіргі мәзір бағасы бойынша.",
        "Approximate estimate based on current menu prices.",
    ),
}


def format_budget(result: BudgetResult, lang: str) -> str:
    lines = [
        f"<b>{_B['title'][lang]}</b>",
        "",
        f"👥 {_B['guests'][lang]}: {result.guests}",
        f"💵 {_B['budget'][lang]}: {format_kzt(result.total_budget)} "
        f"({format_kzt(result.budget_per_person)} {_B['pp'][lang]})",
        "",
    ]
    ms = result.menu_set
    if not ms.feasible:
        minimum = ms.minimum_price + apply_service_charge(ms.minimum_price)
        lines.append(_B["not_enough"][lang].format(v=format_kzt(minimum)))
        return "\n".join(lines)
    lines.append(f"🍽 <b>{_B['set'][lang]}:</b>")
    for course, dish in ms.items.items():
        lines.append(f"• {COURSE_LABELS[course][lang]}: {escape(dish.localized('name', lang))} — {format_kzt(dish.price)}")
    lines += [
        "",
        f"{_B['food'][lang]}: {format_kzt(ms.price)} × {result.guests} = {format_kzt(result.food_total)}",
        f"{_B['charge'][lang]} ({data.SERVICE_CHARGE_PERCENT}%): {format_kzt(result.service_charge)}",
        f"<b>{_B['total'][lang]}: {format_kzt(result.grand_total)}</b> "
        f"(~{format_kzt(result.per_person)} {_B['pp'][lang]})",
        f"{_B['left'][lang]}: {format_kzt(result.remaining)}",
        "",
        f"<i>{_B['note'][lang]}</i>",
    ]
    return "\n".join(lines)
