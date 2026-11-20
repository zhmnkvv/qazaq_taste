import pytest
from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import GetUpdates, SendMessage

from bot.telegram_retry import RetryMiddleware


def flaky(failures: int):
    calls = {"n": 0}

    async def make_request(bot, method):
        calls["n"] += 1
        if calls["n"] <= failures:
            raise TelegramNetworkError(method=method, message="Request timeout error")
        return "ok"

    return make_request, calls


async def test_retries_then_succeeds():
    make_request, calls = flaky(failures=2)
    result = await RetryMiddleware(attempts=3, base_delay=0)(make_request, None, SendMessage(chat_id=1, text="x"))
    assert result == "ok" and calls["n"] == 3


async def test_gives_up_after_attempts():
    make_request, calls = flaky(failures=5)
    with pytest.raises(TelegramNetworkError):
        await RetryMiddleware(attempts=3, base_delay=0)(make_request, None, SendMessage(chat_id=1, text="x"))
    assert calls["n"] == 3


async def test_get_updates_is_not_retried():
    make_request, calls = flaky(failures=1)
    with pytest.raises(TelegramNetworkError):
        await RetryMiddleware(attempts=3, base_delay=0)(make_request, None, GetUpdates())
    assert calls["n"] == 1
