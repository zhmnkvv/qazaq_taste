"""Generate test_cases.md: 5 guest messages answered by the local model
WITHOUT and WITH the few-shot block of the system prompt.

Usage (Ollama must be running and the model pulled):
    .\\.venv\\Scripts\\python.exe scripts\\run_test_cases.py

Nothing is invented: every answer in the file is the model's real output.
Each message is sent without dialogue history, with the same knowledge base
and session data; only the system prompt differs.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bot.config import load_settings  # noqa: E402
from bot.database.database import Database  # noqa: E402
from bot.database.repository import ChatHistoryRepository  # noqa: E402
from bot.services.ai_service import (  # noqa: E402
    AIService,
    OllamaClient,
    clean_model_output,
    load_system_prompt,
    without_few_shot,
)
from bot.services.menu_service import MenuService  # noqa: E402

OUTPUT = ROOT / "test_cases.md"

# (scenario, guest message, what to look at)
CASES = [
    ("Обычный вопрос", "Что такое куырдак и сколько он стоит?",
     "точная цена и состав из меню, краткость, предложение следующего шага"),
    ("Нет ответа в данных", "Можно ли прийти к вам с собакой?",
     "в базе знаний нет информации о животных: бот не должен выдумывать правило, а должен дать телефон"),
    ("Вежливый отказ", "Помоги написать резюме для работы программистом.",
     "короткий вежливый отказ без нотаций и возврат к теме ресторана"),
    ("Бронирование", "Как забронировать столик на пятницу вечером и до скольки вы работаете?",
     "часы работы из базы знаний, бот не утверждает, что столик забронирован, указывает кнопку"),
    ("Подбор под ограничения", "Я вегетарианец. Что посоветуете на ужин, чтобы уложиться в 6000 тенге?",
     "только вегетарианские блюда из меню, реальные цены, корректная сумма"),
]


async def ask(service: AIService, client: OllamaClient, text: str) -> str:
    messages = [{"role": "system", "content": service.build_system_message("ru")},
                {"role": "user", "content": text}]
    return clean_model_output(await client.chat(messages, temperature=0.2))


def quote(text: str) -> str:
    return "\n".join("> " + line if line.strip() else ">" for line in text.strip().splitlines())


async def main() -> int:
    settings = load_settings()
    client = OllamaClient(settings.ollama_url, settings.ollama_model, timeout=180,
                          num_ctx=settings.ollama_num_ctx)
    try:
        if not await client.is_available():
            print(f"Ollama or model '{settings.ollama_model}' is not available at {settings.ollama_url}.")
            print(f"Install Ollama and run:  ollama pull {settings.ollama_model}")
            return 1
        db = Database("sqlite://")
        db.create_all()
        menu, history = MenuService(), ChatHistoryRepository(db)
        full_prompt = load_system_prompt()
        before = AIService(client, history, menu, settings, system_prompt=without_few_shot(full_prompt))
        after = AIService(client, history, menu, settings, system_prompt=full_prompt)

        now = datetime.now(ZoneInfo(settings.timezone))
        parts = [
            "# Тест-кейсы: ответы бота до и после few-shot",
            "",
            f"Сгенерировано скриптом `scripts/run_test_cases.py` {now:%d.%m.%Y %H:%M} (Алматы), "
            f"модель `{settings.ollama_model}`, temperature 0.2.",
            "Каждое сообщение отправлено без истории диалога, с одинаковой базой знаний; различается только "
            "system prompt: **до** — без раздела 17 `<примеры>`, **после** — с ним. Ответы не редактировались.",
            "",
        ]
        for i, (scenario, text, focus) in enumerate(CASES, start=1):
            print(f"[{i}/5] {scenario} ...", flush=True)
            answer_before = await ask(before, client, text)
            answer_after = await ask(after, client, text)
            parts += [
                f"## Тест {i}. {scenario}",
                "",
                f"**Сообщение гостя:** {text}",
                "",
                "**Ответ ДО few-shot:**",
                "",
                quote(answer_before),
                "",
                "**Ответ ПОСЛЕ few-shot:**",
                "",
                quote(answer_after),
                "",
                f"**Что изменилось:** _заполните после прочтения ответов; на что смотреть: {focus}._",
                "",
            ]
        OUTPUT.write_text("\n".join(parts), encoding="utf-8")
        print(f"Saved {OUTPUT}")
        return 0
    finally:
        await client.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
