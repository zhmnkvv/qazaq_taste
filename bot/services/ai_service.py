"""AI consultant powered by a local Ollama model, with a rule-based fallback.

Flow for every user message:
    system prompt (bot/prompts/system_prompt.txt)
  + knowledge base generated from bot/data/menu.py
  + session info (language, date)
  + last N messages of the dialogue (from SQLite)
  + the new user message
  -> Ollama /api/chat -> output guard -> reply

If Ollama is not running, the model is missing or the request fails, the
``FallbackResponder`` answers common questions with plain program logic so the
bot keeps working.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from html import unescape
from pathlib import Path
from zoneinfo import ZoneInfo

import aiohttp

from bot.config import BOT_DIR, Settings
from bot.data import menu as data
from bot.database.repository import ChatHistoryRepository
from bot.services.menu_service import MenuService, format_kzt
from bot.services.proposal_service import calculate_budget

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_PATH = BOT_DIR / "prompts" / "system_prompt.txt"
CANARY = "QT-CANARY-7731"
LEAK_MARKERS = (
    CANARY,
    "PROMPT INJECTION PROTECTION",
    "BUSINESS CONTEXT",
    "SYSTEM INSTRUCTIONS",
    "These instructions define who you are",
)
KAZAKH_LETTERS = set("әғқңөұүһіӘҒҚҢӨҰҮҺІ")
LANG_NAMES = {"ru": "Russian", "kk": "Kazakh", "en": "English"}


class AIServiceError(Exception):
    """Generic AI failure."""


class OllamaUnavailableError(AIServiceError):
    """Ollama server unreachable, model missing or request timed out."""


def detect_language(text: str, default: str = "ru") -> str:
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return default
    if any(ch in KAZAKH_LETTERS for ch in letters):
        return "kk"
    cyrillic = sum(1 for ch in letters if "Ѐ" <= ch <= "ӿ")
    if cyrillic / len(letters) > 0.5:
        # Russian vs Kazakh without special letters: keep a Kazakh default.
        return "kk" if default == "kk" else "ru"
    latin = sum(1 for ch in letters if ch.isascii())
    if latin / len(letters) > 0.5:
        return "en"
    return default


def load_system_prompt(path: Path = SYSTEM_PROMPT_PATH) -> str:
    text = path.read_text(encoding="utf-8").strip()
    if len(text) < 500:
        raise AIServiceError("System prompt file is missing or too short")
    return text


def clean_model_output(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = text.replace("**", "").replace("__", "")
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    return unescape(text).strip()


def leaks_system_prompt(reply: str, system_prompt: str) -> bool:
    if any(marker.lower() in reply.lower() for marker in LEAK_MARKERS):
        return True
    # Long verbatim fragments of the prompt (8+ consecutive words).
    words = re.findall(r"\w+", system_prompt.lower())
    reply_norm = " ".join(re.findall(r"\w+", reply.lower()))
    for i in range(0, max(len(words) - 12, 0), 6):
        chunk = " ".join(words[i:i + 12])
        if len(chunk) > 60 and chunk in reply_norm:
            return True
    return False


# --------------------------------------------------------------------------- #
# Ollama HTTP client
# --------------------------------------------------------------------------- #
class OllamaClient:
    def __init__(self, base_url: str, model: str, timeout: float = 90.0,
                 temperature: float = 0.4, num_ctx: int = 16384) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.temperature = temperature
        self.num_ctx = num_ctx
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def is_available(self) -> bool:
        """True if the server answers and the configured model is pulled."""
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/api/tags",
                                   timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status != 200:
                    return False
                payload = await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError, ValueError):
            return False
        names = {m.get("name", "") for m in payload.get("models", [])}
        wanted = self.model if ":" in self.model else f"{self.model}:latest"
        return wanted in names or self.model in names

    async def chat(self, messages: list[dict[str, str]]) -> str:
        body = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": self.temperature, "num_ctx": self.num_ctx, "top_p": 0.9},
            "keep_alive": "30m",
        }
        try:
            session = await self._get_session()
            async with session.post(f"{self.base_url}/api/chat", json=body,
                                    timeout=aiohttp.ClientTimeout(total=self.timeout)) as resp:
                if resp.status == 404:
                    raise OllamaUnavailableError(f"Model '{self.model}' is not available in Ollama")
                if resp.status != 200:
                    raise AIServiceError(f"Ollama returned HTTP {resp.status}")
                payload = await resp.json()
        except AIServiceError:
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
            raise OllamaUnavailableError(f"Ollama request failed: {type(exc).__name__}") from exc
        except ValueError as exc:
            raise AIServiceError("Invalid JSON from Ollama") from exc
        content = (payload.get("message") or {}).get("content", "")
        if not isinstance(content, str) or not content.strip():
            raise AIServiceError("Empty response from Ollama")
        return content


# --------------------------------------------------------------------------- #
# Rule-based fallback
# --------------------------------------------------------------------------- #
_F = {
    "unavailable": data.t(
        "🤖 AI-консультант сейчас недоступен, но я помогу с основными вопросами.",
        "🤖 AI-кеңесші қазір қолжетімсіз, бірақ негізгі сұрақтарға көмектесемін.",
        "🤖 The AI consultant is unavailable right now, but I can help with the basics.",
    ),
    "default": data.t(
        "Я могу показать меню, принять заявку на бронирование, рассчитать бюджет или подготовить "
        "коммерческое предложение — воспользуйтесь кнопками ниже. Вопросы о блюдах можно задать, "
        "указав название блюда.",
        "Мәзірді көрсетіп, брондауға өтінім қабылдап, бюджетті есептеп немесе коммерциялық ұсыныс "
        "дайындай аламын — төмендегі батырмаларды пайдаланыңыз. Тағам туралы сұрағанда атауын жазыңыз.",
        "I can show the menu, take a booking request, calculate a budget or prepare a commercial "
        "proposal — please use the buttons below. For dish questions, mention the dish name.",
    ),
    "veg": data.t("🌱 Вегетарианские блюда:", "🌱 Вегетариандық тағамдар:", "🌱 Vegetarian dishes:"),
    "booking": data.t(
        "Чтобы оставить заявку на бронирование, нажмите «📅 Забронировать столик» или отправьте /booking.",
        "Брондауға өтінім қалдыру үшін «📅 Үстел брондау» батырмасын басыңыз немесе /booking жіберіңіз.",
        "To leave a booking request press \"📅 Book a table\" or send /booking.",
    ),
    "event": data.t(
        "Для расчёта мероприятия нажмите «🎉 Организовать мероприятие» или отправьте /event — "
        "я подготовлю коммерческое предложение по реальным ценам.",
        "Іс-шараны есептеу үшін «🎉 Іс-шара ұйымдастыру» батырмасын басыңыз немесе /event жіберіңіз.",
        "To plan an event press \"🎉 Organize an event\" or send /event — you will get a proposal "
        "calculated from real prices.",
    ),
    "contacts": data.t("📍 Контакты", "📍 Байланыс", "📍 Contacts"),
    "hours": data.t("🕐 Часы работы", "🕐 Жұмыс уақыты", "🕐 Opening hours"),
    "injection": data.t(
        "Я AI-консультант ресторана Qazaq Taste и могу помочь только с меню, бронированием и мероприятиями.",
        "Мен Qazaq Taste мейрамханасының AI-кеңесшісімін, тек мәзір, брондау және іс-шаралар бойынша көмектесемін.",
        "I'm the AI consultant of Qazaq Taste and can only help with the menu, bookings and events.",
    ),
    "cheapest": data.t("💸 Самые доступные блюда:", "💸 Ең қолжетімді тағамдар:", "💸 Most affordable dishes:"),
}

KEYWORDS = {
    "veg": ("вегетариан", "веган", "без мяса", "vegetarian", "vegan", "етсіз", "вегетариандық"),
    "booking": ("брон", "столик", "book", "reserv", "резерв", "үстел"),
    "event": ("мероприят", "корпоратив", "банкет", "свадьб", "той", "event", "party", "banquet", "wedding",
              "іс-шара", "туған күн", "день рождения", "birthday"),
    "contacts": ("адрес", "контакт", "телефон", "где вы", "address", "contact", "phone", "where", "мекенжай",
                 "байланыс", "қайда"),
    "hours": ("часы", "время работы", "открыт", "работаете", "hours", "open", "close", "жұмыс уақыты", "ашық"),
    "cheap": ("дешев", "недорог", "бюджетн", "cheap", "affordable", "арзан"),
    "menu": ("меню", "menu", "мәзір", "блюд", "dish", "тағам"),
}
INJECTION_PATTERNS = re.compile(
    r"(ignore|forget|disregard|override).{0,30}(instruction|rule|prompt)|"
    r"(игнорир|забудь|отмени).{0,30}(инструкц|правил|промпт)|"
    r"(system\s*prompt|системн\w*\s+промпт|системн\w*\s+инструкц|jailbreak|developer mode|режим разработчика|"
    r"нұсқаулықты елеме)",
    re.IGNORECASE,
)
BUDGET_RE = re.compile(r"(\d[\d\s]{2,})\s*(?:₸|тг|тенге|теңге|kzt|tenge)?", re.IGNORECASE)
GUESTS_RE = re.compile(r"(\d{1,3})\s*(?:человек|чел|гост|people|persons|guests|адам|қонақ)", re.IGNORECASE)


class FallbackResponder:
    def __init__(self, menu: MenuService) -> None:
        self.menu = menu

    def answer(self, text: str, lang: str) -> str:
        low = text.lower()
        parts: list[str] = [_F["unavailable"][lang]]

        if INJECTION_PATTERNS.search(text):
            return _F["injection"][lang]

        mentioned = self.menu.find_mentioned(text)[:3]
        for dish in mentioned:
            parts.append(_plain(self.menu.dish_card(dish, lang)))

        def has(key: str) -> bool:
            # keywords must start a word: "етсіз" (meatless) must not match "сәлеметсіз"
            return any(re.search(r"(?<!\w)" + re.escape(k), low) for k in KEYWORDS[key])

        if not mentioned and has("veg"):
            veg = "\n".join(f"• {d.localized('name', lang)} — {format_kzt(d.price)}" for d in self.menu.vegetarian())
            parts.append(f"{_F['veg'][lang]}\n{veg}")

        budget = self._budget_estimate(low, lang)
        if budget:
            parts.append(budget)
        elif not mentioned and has("cheap"):
            cheapest = sorted(self.menu.dishes, key=lambda d: d.price)[:6]
            parts.append(_F["cheapest"][lang] + "\n" + "\n".join(
                f"• {d.localized('name', lang)} — {format_kzt(d.price)}" for d in cheapest))

        r = data.RESTAURANT
        if has("contacts"):
            parts.append(f"{_F['contacts'][lang]}: {r['address'][lang]}, {r['city'][lang]}\n☎️ {r['phone']}")
        if has("hours"):
            parts.append(f"{_F['hours'][lang]}: {r['hours'][lang]}")
        if has("booking"):
            parts.append(_F["booking"][lang])
        if has("event"):
            parts.append(_F["event"][lang])
        if len(parts) == 1:
            parts.append(_F["default"][lang])
        return "\n\n".join(parts)

    def _budget_estimate(self, low: str, lang: str) -> str | None:
        guests_m = GUESTS_RE.search(low)
        amounts = [int(m.group(1).replace(" ", "")) for m in BUDGET_RE.finditer(low)]
        amounts = [a for a in amounts if a >= 1000]
        if not guests_m or not amounts:
            return None
        guests = int(guests_m.group(1))
        if not 1 <= guests <= 140:
            return None
        from bot.services.proposal_service import format_budget  # local import to avoid cycles
        return _plain(format_budget(calculate_budget(guests, max(amounts), self.menu), lang))


def _plain(html_text: str) -> str:
    return unescape(re.sub(r"<[^>]+>", "", html_text))


# --------------------------------------------------------------------------- #
# AI service
# --------------------------------------------------------------------------- #
@dataclass
class AIReply:
    text: str
    source: str  # "ai" | "fallback" | "guard"


class AIService:
    def __init__(self, client: OllamaClient, history: ChatHistoryRepository, menu: MenuService,
                 settings: Settings, system_prompt: str | None = None) -> None:
        self.client = client
        self.history = history
        self.menu = menu
        self.settings = settings
        self.system_prompt = system_prompt or load_system_prompt()
        self.knowledge_base = menu.knowledge_base()
        self.fallback = FallbackResponder(menu)

    def build_system_message(self, lang: str) -> str:
        now = datetime.now(ZoneInfo(self.settings.timezone))
        session = (
            "## SESSION\n"
            f"User interface language: {LANG_NAMES.get(lang, 'Russian')} ({lang}).\n"
            f"Current date and time in Almaty: {now:%d.%m.%Y %H:%M} ({now:%A})."
        )
        return f"{self.system_prompt}\n\n# KNOWLEDGE BASE\n{self.knowledge_base}\n\n{session}"

    def build_messages(self, telegram_id: int, user_text: str, lang: str) -> list[dict[str, str]]:
        history = self.history.last(telegram_id, self.settings.ai_history_limit)
        reply_lang = detect_language(user_text, lang)
        reminder = (
            f"[Reply in {LANG_NAMES[reply_lang]}. Follow the Qazaq Taste consultant rules.]\n"
        )
        return [
            {"role": "system", "content": self.build_system_message(lang)},
            *history,
            {"role": "user", "content": reminder + user_text},
        ]

    async def answer(self, telegram_id: int, user_text: str, lang: str) -> AIReply:
        text = (user_text or "").strip()[: self.settings.ai_max_input_chars]
        reply_lang = detect_language(text, lang)
        if not text:
            return AIReply(self.fallback.answer("", reply_lang), "fallback")

        messages = self.build_messages(telegram_id, text, lang)
        try:
            raw = await self.client.chat(messages)
        except AIServiceError as exc:
            logger.warning("AI unavailable, using fallback: %s", exc)
            return AIReply(self.fallback.answer(text, reply_lang), "fallback")
        except Exception:  # never let the AI break the bot
            logger.exception("Unexpected AI error, using fallback")
            return AIReply(self.fallback.answer(text, reply_lang), "fallback")

        reply = clean_model_output(raw)
        if not reply:
            return AIReply(self.fallback.answer(text, reply_lang), "fallback")
        if leaks_system_prompt(reply, self.system_prompt):
            logger.warning("Blocked a reply that leaked system instructions")
            return AIReply(_F["injection"][reply_lang], "guard")

        self.history.add(telegram_id, "user", text)
        self.history.add(telegram_id, "assistant", reply)
        self.history.prune(telegram_id, keep=max(self.settings.ai_history_limit, 2))
        return AIReply(reply, "ai")

    def reset(self, telegram_id: int) -> None:
        self.history.clear(telegram_id)
