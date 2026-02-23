import os

from dotenv import load_dotenv

load_dotenv()


def _parse_int_set(val):
    if not val:
        return set()
    if isinstance(val, (set, list, tuple)):
        return {int(x) for x in val}
    try:
        return {int(val)}
    except Exception:
        pass
    parts = str(val).replace(";", ",").split(",")
    out = set()
    for p in parts:
        p = p.strip()
        if p:
            out.add(int(p))
    return out


class Config:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    # ── Telegram ──
    TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
    ALLOWED_USERS: set = _parse_int_set(os.getenv("ALLOWED_USERS"))

    # ── OpenRouter / LLM ──
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openrouter")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "openai/gpt-4o")
    OPENROUTER_APP_NAME: str = os.getenv("OPENROUTER_APP_NAME", "MyTelegramBot")
    OPENROUTER_SITE_URL: str = os.getenv("OPENROUTER_SITE_URL", "")

    # ── История диалога ──
    MAX_HISTORY: int = int(os.getenv("MAX_HISTORY", "20"))

    # ── Obsidian ──
    OBSIDIAN_VAULT_PATH: str = os.getenv("OBSIDIAN_VAULT_PATH", "./vault")
    OBSIDIAN_TICKETS_DIR: str = os.getenv("OBSIDIAN_TICKETS_DIR", "tickets")

    # ── iCloud / Sync ──
    ICLOUD_SYNC_ENABLED: bool = (
        os.getenv("ICLOUD_SYNC_ENABLED", "false").lower() == "true"
    )
    ICLOUD_VAULT_PATH: str = os.getenv("ICLOUD_VAULT_PATH", "")
    RCLONE_REMOTE: str = os.getenv("RCLONE_REMOTE", "")

    # ── Напоминания ──
    REMINDER_ENABLED: bool = os.getenv("REMINDER_ENABLED", "true").lower() == "true"
    REMINDER_HOUR: int = int(os.getenv("REMINDER_HOUR", "9"))
    REMINDER_MINUTE: int = int(os.getenv("REMINDER_MINUTE", "0"))
    TIMEZONE: str = os.getenv("TIMEZONE", "Europe/Moscow")

    # ── Парсинг статей ──
    ARTICLE_MAX_CHARS: int = int(os.getenv("ARTICLE_MAX_CHARS", "15000"))
