"""Logging configuration with redaction of secrets and personal data."""

from __future__ import annotations

import logging
import re

TOKEN_RE = re.compile(r"\d{5,}:[A-Za-z0-9_-]{30,}")
PHONE_RE = re.compile(r"\+?\d[\d\s()\-]{9,}\d")


class RedactingFilter(logging.Filter):
    """Masks Telegram tokens and phone numbers in every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        redacted = TOKEN_RE.sub("<redacted-token>", message)
        redacted = PHONE_RE.sub("<redacted-phone>", redacted)
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"))
    handler.addFilter(RedactingFilter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    # aiohttp/aiogram may log request URLs that contain the bot token.
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
