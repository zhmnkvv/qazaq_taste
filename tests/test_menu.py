import re
from string import Formatter

from bot.data import menu as data
from bot.services.menu_service import MenuService, format_kzt
from bot.texts import LANGS, TEXTS


def test_menu_has_at_least_20_dishes():
    assert len(data.DISHES) >= 20


def test_all_categories_present_and_filled():
    required = {"national", "main", "starters", "salads", "drinks", "desserts"}
    assert required == set(data.CATEGORIES)
    for cat in required:
        assert MenuService().by_category(cat), f"category {cat} is empty"


def test_dish_fields_complete_in_all_languages():
    ids = set()
    for dish in data.DISHES:
        assert dish.id not in ids, f"duplicate id {dish.id}"
        ids.add(dish.id)
        assert dish.category in data.CATEGORIES
        assert isinstance(dish.price, int) and 100 <= dish.price <= 50000
        assert dish.weight
        for attr in ("name", "description", "ingredients"):
            for lang in LANGS:
                assert getattr(dish, attr)[lang].strip(), f"{dish.id}.{attr}.{lang} is empty"
        assert dish.tags <= set(data.TAG_LABELS), f"{dish.id} has unknown tags"


def test_no_pork_on_menu():
    for dish in data.DISHES:
        text = " ".join(dish.ingredients.values()).lower()
        assert "свинин" not in text and "pork" not in text


def test_vegetarian_dishes_have_no_meat():
    meat = re.compile(r"мясо|говядин|баранин|конин|ягн|казы|печень|fish|beef|lamb|horse|zander", re.I)
    for dish in MenuService().vegetarian():
        assert not meat.search(dish.ingredients["ru"] + dish.ingredients["en"]), dish.id


def test_dish_card_contains_price_and_ingredients(menu):
    dish = menu.get("beshbarmak")
    card = menu.dish_card(dish, "ru")
    assert "Бешбармак" in card and "5 900 ₸" in card and "Состав" in card
    assert "Beshbarmak" in menu.dish_card(dish, "en")
    assert "Құрамы" in menu.dish_card(dish, "kk")


def test_format_kzt():
    assert format_kzt(900) == "900 ₸"
    assert format_kzt(5900) == "5 900 ₸"
    assert format_kzt(1250000) == "1 250 000 ₸"


def test_find_mentioned(menu):
    found = {d.id for d in menu.find_mentioned("Что такое бешбармак и кумыс? А плов острый?")}
    assert {"beshbarmak", "kumys", "plov"} <= found
    assert menu.find_mentioned("Привет!") == []


def test_knowledge_base_contains_every_dish_and_price(menu):
    kb = menu.knowledge_base()
    for dish in data.DISHES:
        assert dish.name["en"] in kb and f"{dish.price} KZT" in kb


def test_texts_exist_in_all_languages_with_same_placeholders():
    for key, entry in TEXTS.items():
        assert set(entry) == set(LANGS), key
        fields = [{f for _, f, _, _ in Formatter().parse(entry[lang]) if f} for lang in LANGS]
        assert fields[0] == fields[1] == fields[2], f"placeholder mismatch in {key}"
