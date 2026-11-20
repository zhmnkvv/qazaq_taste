"""Menu queries, formatting and the knowledge base given to the AI."""

from __future__ import annotations

from html import escape

from bot.data import menu as data
from bot.data.menu import Dish


GENERIC_FIRST_WORDS = {
    "салат", "ассорти", "томленая", "sea-buckthorn", "slow-cooked", "lamb", "beef", "horse-meat", "kazakh",
    "ноқат", "сүтті", "балмұздақ", "асқабақ", "сиыр", "қой", "жылқы", "шырғанақ", "almaty-style",
}


def format_kzt(amount: int) -> str:
    """5900 -> '5 900 ₸' (non-breaking thin grouping with a regular space)."""
    return f"{amount:,}".replace(",", " ") + " ₸"


class MenuService:
    def __init__(self, dishes: list[Dish] | None = None) -> None:
        self.dishes = dishes if dishes is not None else data.DISHES
        self._by_id = {d.id: d for d in self.dishes}

    # ---- queries ------------------------------------------------------------
    def categories(self) -> dict[str, dict[str, str]]:
        return data.CATEGORIES

    def by_category(self, category: str) -> list[Dish]:
        return [d for d in self.dishes if d.category == category]

    def get(self, dish_id: str) -> Dish | None:
        return self._by_id.get(dish_id)

    def vegetarian(self) -> list[Dish]:
        return [d for d in self.dishes if d.is_vegetarian]

    def find_mentioned(self, text: str) -> list[Dish]:
        """Dishes whose name (in any language) is mentioned in ``text``."""
        low = text.lower().replace("ё", "е")
        found = []
        for dish in self.dishes:
            for name in dish.name.values():
                full = name.lower().replace("ё", "е")
                first = full.split(" ")[0]
                keys = [full]
                if len(first) >= 4 and first not in GENERIC_FIRST_WORDS:
                    keys.append(first.rstrip("иы") if len(first) > 6 else first)
                if any(k in low for k in keys):
                    found.append(dish)
                    break
        return found

    # ---- formatting (HTML) --------------------------------------------------
    def tags_text(self, dish: Dish, lang: str) -> str:
        labels = [data.TAG_LABELS[tag][lang] for tag in sorted(dish.tags) if tag in data.TAG_LABELS]
        return ", ".join(labels)

    def dish_card(self, dish: Dish, lang: str) -> str:
        labels = {
            "ru": ("Состав", "Порция", "Цена", "Особенности"),
            "kk": ("Құрамы", "Порция", "Бағасы", "Ерекшеліктері"),
            "en": ("Ingredients", "Portion", "Price", "Notes"),
        }[lang]
        lines = [
            f"<b>{escape(dish.localized('name', lang))}</b>",
            f"<i>{escape(data.CATEGORIES[dish.category][lang])}</i>",
            "",
            escape(dish.localized("description", lang)),
            "",
            f"🧾 <b>{labels[0]}:</b> {escape(dish.localized('ingredients', lang))}",
            f"⚖️ <b>{labels[1]}:</b> {escape(dish.weight)}",
            f"💵 <b>{labels[2]}:</b> {format_kzt(dish.price)}",
        ]
        tags = self.tags_text(dish, lang)
        if tags:
            lines.append(f"🏷 <b>{labels[3]}:</b> {escape(tags)}")
        return "\n".join(lines)

    def category_text(self, category: str, lang: str) -> str:
        lines = [f"<b>{escape(data.CATEGORIES[category][lang])}</b>", ""]
        for dish in self.by_category(category):
            veg = " 🌱" if dish.is_vegetarian else ""
            spicy = " 🌶" if "spicy" in dish.tags else ""
            lines.append(f"• {escape(dish.localized('name', lang))}{veg}{spicy} — {format_kzt(dish.price)}")
        return "\n".join(lines)

    # ---- AI knowledge base (plain text, English labels, multilingual names) --
    def knowledge_base(self) -> str:
        r = data.RESTAURANT
        lines = [
            "## RESTAURANT FACTS",
            f"Name: {r['name']} (fictional demo restaurant used for a student project)",
            f"City: {r['city']['en']}",
            f"Address: {r['address']['en']}",
            f"Phone: {r['phone']} | Email: {r['email']} | Instagram: {r['instagram']}",
            f"Opening hours: {r['hours']['en']}",
            f"About: {r['about']['en']}",
            f"Halls: {r['halls']['en']}",
            f"Features: {r['features']['en']}",
            f"Service charge: {data.SERVICE_CHARGE_PERCENT}% added to the food bill.",
            f"Table booking via bot: 1–{data.BOOKING_MAX_GUESTS} guests, up to {data.BOOKING_MAX_DAYS_AHEAD} days ahead; "
            "larger groups use the event request flow.",
            "",
            "## MENU (prices in KZT per portion; names given as RU / KK / EN)",
        ]
        for cat_id, cat_names in data.CATEGORIES.items():
            lines.append(f"### {cat_names['en'].split(' ', 1)[1]}")
            for d in self.by_category(cat_id):
                tags = ", ".join(sorted(d.tags)) or "none"
                lines.append(
                    f"- [{d.id}] {d.name['ru']} / {d.name['kk']} / {d.name['en']} — {d.price} KZT, {d.weight}. "
                    f"{d.description['en']} Ingredients: {d.ingredients['en']}. Tags: {tags}."
                )
        lines += ["", "## EVENT TYPES (minimum guests; services included by default)"]
        for ev in data.EVENT_TYPES.values():
            included = ", ".join(data.ADDITIONAL_SERVICES[s]["name"]["en"] for s in ev["included_services"])
            lines.append(f"- {ev['name']['en']}: min {ev['min_guests']} guests; includes: {included}")
        lines += ["", "## ADDITIONAL SERVICES (fixed price per event, KZT)"]
        for svc in data.ADDITIONAL_SERVICES.values():
            lines.append(f"- {svc['name']['en']}: {svc['price']} KZT")
        return "\n".join(lines)
