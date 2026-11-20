import math
from datetime import date

import pytest

from bot.data import menu as data
from bot.services.proposal_service import (
    ProposalInput,
    apply_service_charge,
    calculate_budget,
    detect_services,
    format_budget,
    format_proposal,
    select_menu_set,
    wants_vegetarian,
)


@pytest.mark.parametrize("budget", [3900, 5000, 8000, 12000, 20000, 50000])
def test_menu_set_never_exceeds_budget(menu, budget):
    ms = select_menu_set(budget, menu)
    assert ms.feasible
    assert ms.price <= budget
    assert {"main", "drink"} <= set(ms.items)


def test_menu_set_uses_real_dishes_and_prices(menu):
    ms = select_menu_set(10000, menu)
    for dish in ms.items.values():
        assert data.DISHES_BY_ID[dish.id].price == dish.price


def test_bigger_budget_gives_more_or_better_courses(menu):
    small, big = select_menu_set(5000, menu), select_menu_set(20000, menu)
    assert len(big.items) >= len(small.items)
    assert big.price > small.price


def test_too_small_budget_is_infeasible(menu):
    ms = select_menu_set(1000, menu)
    assert not ms.feasible
    assert ms.minimum_price > 1000


def test_vegetarian_set(menu):
    ms = select_menu_set(10000, menu, vegetarian=True)
    assert all(d.is_vegetarian for d in ms.items.values())


def test_calculate_budget_math(menu):
    r = calculate_budget(guests=10, total_budget=100_000, menu=menu)
    assert r.budget_per_person == 10_000
    assert r.food_total == r.menu_set.price * 10
    assert r.service_charge == round(r.food_total * 0.10)
    assert r.grand_total == r.food_total + r.service_charge
    assert r.grand_total <= 100_000
    assert r.remaining == 100_000 - r.grand_total
    text = format_budget(r, "ru")
    assert "Итого" in text and "₸" in text


def test_calculate_budget_rejects_bad_input(menu):
    with pytest.raises(ValueError):
        calculate_budget(0, 10000, menu)
    with pytest.raises(ValueError):
        calculate_budget(5, -1, menu)
    with pytest.raises(ValueError):
        calculate_budget(1000, 10_000_000, menu)


def test_budget_text_when_not_enough(menu):
    text = format_budget(calculate_budget(10, 20000, menu), "en")
    assert "at least" in text


def test_proposal_totals_are_consistent(proposal_service):
    p = proposal_service.build(ProposalInput("corporate", 30, date(2026, 12, 20), 15000, "нужна домбра"))
    services_total = sum(data.ADDITIONAL_SERVICES[s]["price"] for s in p.services)
    assert "dombra" in p.services and "hall_rental" in p.services
    assert p.services_total == services_total
    assert p.food_total == p.food_per_person * 30
    assert p.service_charge == apply_service_charge(p.food_total)
    assert p.grand_total == p.food_total + p.service_charge + p.services_total
    assert p.price_per_person == math.ceil(p.grand_total / 30)
    assert p.within_budget


def test_proposal_over_budget_warning(proposal_service):
    p = proposal_service.build(ProposalInput("wedding", 30, date(2026, 12, 20), 4000))
    assert "warn_over_budget" in p.warnings
    assert not p.within_budget
    assert "Превышение" in format_proposal(p, "ru")


def test_proposal_min_guests_warning(proposal_service):
    p = proposal_service.build(ProposalInput("wedding", 10, date(2026, 12, 20), 30000))
    assert "warn_min_guests" in p.warnings


def test_proposal_vegetarian_wish(proposal_service):
    p = proposal_service.build(ProposalInput("birthday", 8, date(2026, 12, 20), 12000, "вегетарианское меню"))
    assert p.vegetarian
    assert all(d.is_vegetarian for d in p.menu_set.items.values())


def test_proposal_text_has_required_sections(proposal_service):
    p = proposal_service.build(ProposalInput("banquet", 20, date(2026, 12, 20), 20000, "фотограф"))
    text = format_proposal(p, "ru")
    for part in ("КОММЕРЧЕСКОЕ ПРЕДЛОЖЕНИЕ", "Банкет", "Количество участников", "Предлагаемое меню",
                 "Стоимость на 1 человека", "ОБЩАЯ СТОИМОСТЬ", "Дополнительные услуги", "Итог"):
        assert part in text
    assert f"{p.grand_total:,}".replace(",", " ") in text
    for lang in ("kk", "en"):
        assert format_proposal(p, lang)


def test_proposal_escapes_user_html(proposal_service):
    p = proposal_service.build(ProposalInput("birthday", 6, date(2026, 12, 20), 15000, "<b>торт</b>"))
    assert "<b>торт</b>" not in format_proposal(p, "ru")
    assert "&lt;b&gt;торт" in format_proposal(p, "ru")


def test_proposal_invalid_input(proposal_service):
    with pytest.raises(ValueError):
        proposal_service.build(ProposalInput("unknown", 10, date(2026, 12, 20), 10000))
    with pytest.raises(ValueError):
        proposal_service.build(ProposalInput("banquet", 10, date(2026, 12, 20), 10))


def test_proposal_saved_to_sqlite(proposal_service):
    p = proposal_service.build(ProposalInput("corporate", 15, date(2026, 12, 20), 18000))
    saved = proposal_service.save(42, p, format_proposal(p, "ru"))
    assert saved.code.startswith("EV-261220-")
    loaded = proposal_service.repo.get_by_code(saved.code)
    assert loaded.total_price == p.grand_total
    assert loaded.guests == 15 and loaded.telegram_id == 42


def test_detect_services_and_vegetarian():
    assert set(detect_services("Нужен ведущий, фотограф и проектор")) == {"host", "photographer", "projector"}
    assert detect_services("dombra please") == ["dombra"]
    assert detect_services("") == []
    assert wants_vegetarian("Vegetarian menu please")
    assert not wants_vegetarian("мясо побольше")
