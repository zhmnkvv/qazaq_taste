import pytest

from bot.config import ConfigError, load_settings

ENV_VARS = ["BOT_TOKEN", "DATABASE_URL", "OLLAMA_URL", "OLLAMA_MODEL", "OLLAMA_TIMEOUT", "AI_HISTORY_LIMIT",
            "ADMIN_CHAT_ID", "LOG_LEVEL", "OLLAMA_NUM_CTX", "TIMEZONE"]
FAKE_TOKEN = "123456789:" + "A" * 35  # format-valid, not a real token


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_loads_values_from_env_file(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        f"BOT_TOKEN={FAKE_TOKEN}\nOLLAMA_MODEL=llama3.2:3b\nAI_HISTORY_LIMIT=6\nADMIN_CHAT_ID=-100123\n"
        "DATABASE_URL=sqlite:///custom/test.db\n",
        encoding="utf-8",
    )
    s = load_settings(env)
    assert s.has_valid_token
    assert s.require_token() == FAKE_TOKEN
    assert s.ollama_model == "llama3.2:3b"
    assert s.ai_history_limit == 6
    assert s.admin_chat_id == -100123
    assert s.database_url.endswith("custom/test.db")
    assert s.database_url.startswith("sqlite:///") and "custom" in s.database_url


def test_defaults_without_env_file(tmp_path):
    s = load_settings(tmp_path / "missing.env")
    assert s.bot_token == ""
    assert s.ollama_url == "http://localhost:11434"
    assert s.ollama_model == "qwen2.5:3b"
    assert s.database_url.endswith("data/qazaq_taste.db")
    assert s.timezone == "Asia/Almaty"


def test_missing_token_raises_clear_error(tmp_path):
    s = load_settings(tmp_path / "missing.env")
    with pytest.raises(ConfigError, match="BotFather"):
        s.require_token()


def test_invalid_token_format(monkeypatch, tmp_path):
    monkeypatch.setenv("BOT_TOKEN", "not-a-token")
    s = load_settings(tmp_path / "missing.env")
    assert not s.has_valid_token
    with pytest.raises(ConfigError):
        s.require_token()


def test_token_is_not_in_repr(monkeypatch, tmp_path):
    monkeypatch.setenv("BOT_TOKEN", FAKE_TOKEN)
    s = load_settings(tmp_path / "missing.env")
    assert FAKE_TOKEN not in repr(s)


@pytest.mark.parametrize("name,value", [("AI_HISTORY_LIMIT", "abc"), ("AI_HISTORY_LIMIT", "500"),
                                        ("ADMIN_CHAT_ID", "admin"), ("LOG_LEVEL", "LOUD")])
def test_invalid_values_raise(monkeypatch, tmp_path, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(ConfigError):
        load_settings(tmp_path / "missing.env")
