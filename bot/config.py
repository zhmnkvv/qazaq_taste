"""Application configuration loaded from environment variables / .env file.

Secrets (the Telegram token) are never hard-coded and never logged.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BOT_DIR = Path(__file__).resolve().parent

TOKEN_PATTERN = re.compile(r"^\d{5,}:[A-Za-z0-9_-]{30,}$")


class ConfigError(RuntimeError):
    """Raised when configuration is missing or invalid."""


def _get_int(name: str, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw.strip())
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer") from exc
    if minimum is not None and value < minimum:
        raise ConfigError(f"{name} must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise ConfigError(f"{name} must be <= {maximum}")
    return value


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw.strip())
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number") from exc


@dataclass(frozen=True)
class Settings:
    bot_token: str = field(repr=False)
    database_url: str
    ollama_url: str
    ollama_model: str
    ollama_timeout: float
    ollama_temperature: float
    ollama_num_ctx: int
    ai_history_limit: int
    ai_max_input_chars: int
    timezone: str
    admin_chat_id: int | None
    log_level: str

    @property
    def has_valid_token(self) -> bool:
        return bool(TOKEN_PATTERN.match(self.bot_token))

    def require_token(self) -> str:
        if not self.bot_token:
            raise ConfigError(
                "BOT_TOKEN is not set. Create a bot via @BotFather and put the token into .env"
            )
        if not self.has_valid_token:
            raise ConfigError("BOT_TOKEN has an invalid format. Check the value in .env")
        return self.bot_token


def load_settings(env_file: str | Path | None = None, override: bool = False) -> Settings:
    """Load settings. ``env_file`` defaults to ``<project>/.env`` (optional)."""
    path = Path(env_file) if env_file else PROJECT_ROOT / ".env"
    if path.exists():
        load_dotenv(path, override=override)

    default_db = PROJECT_ROOT / "data" / "qazaq_taste.db"
    database_url = os.getenv("DATABASE_URL", "").strip() or f"sqlite:///{default_db.as_posix()}"
    # Resolve relative SQLite paths against the project root (not the current directory).
    if database_url.startswith("sqlite:///") and database_url != "sqlite:///:memory:":
        db_path = Path(database_url.removeprefix("sqlite:///"))
        if not db_path.is_absolute():
            database_url = f"sqlite:///{(PROJECT_ROOT / db_path).as_posix()}"

    admin_raw = os.getenv("ADMIN_CHAT_ID", "").strip()
    admin_chat_id: int | None = None
    if admin_raw:
        try:
            admin_chat_id = int(admin_raw)
        except ValueError as exc:
            raise ConfigError("ADMIN_CHAT_ID must be an integer Telegram chat id") from exc

    log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO"
    if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ConfigError("LOG_LEVEL must be one of DEBUG, INFO, WARNING, ERROR, CRITICAL")

    return Settings(
        bot_token=os.getenv("BOT_TOKEN", "").strip(),
        database_url=database_url,
        ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434").strip().rstrip("/"),
        ollama_model=os.getenv("OLLAMA_MODEL", "qwen2.5:3b").strip(),
        ollama_timeout=_get_float("OLLAMA_TIMEOUT", 90.0),
        ollama_temperature=_get_float("OLLAMA_TEMPERATURE", 0.4),
        ollama_num_ctx=_get_int("OLLAMA_NUM_CTX", 16384, minimum=2048),
        ai_history_limit=_get_int("AI_HISTORY_LIMIT", 10, minimum=0, maximum=40),
        ai_max_input_chars=_get_int("AI_MAX_INPUT_CHARS", 1000, minimum=50),
        timezone=os.getenv("TIMEZONE", "Asia/Almaty").strip(),
        admin_chat_id=admin_chat_id,
        log_level=log_level,
    )
