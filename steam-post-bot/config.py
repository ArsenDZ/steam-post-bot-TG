"""
Централизованная загрузка конфигурации из .env.
"""
import os
from dataclasses import dataclass, field
from typing import List

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Отсутствует обязательная переменная окружения: {name}. "
            f"Проверьте файл .env (см. .env.example)."
        )
    return value


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _parse_id_list(raw: str) -> List[int]:
    ids = []
    for part in raw.split(","):
        part = part.strip()
        if part:
            ids.append(int(part))
    return ids


def _normalize_gemini_model(raw_value: str | None) -> str:
    value = (raw_value or "gemini-3.6-flash").strip()
    if value.startswith("models/"):
        value = value.replace("models/", "", 1)
    if value.startswith("gemini-2."):
        return "gemini-3.6-flash"
    return value or "gemini-3.6-flash"


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    telegram_channel_id: str

    owner_id: int
    initial_admin_ids: List[int]

    gemini_api_key: str
    gemini_model: str

    auto_publish: bool

    database_path: str
    log_file: str
    log_level: str
    tmp_dir: str


def load_settings() -> Settings:
    return Settings(
        telegram_bot_token=_require("TELEGRAM_BOT_TOKEN"),
        telegram_channel_id=_require("TELEGRAM_CHANNEL_ID"),
        owner_id=int(_require("OWNER_ID")),
        initial_admin_ids=_parse_id_list(os.getenv("ADMIN_IDS", "")),
        gemini_api_key=_require("GEMINI_API_KEY"),
        gemini_model=_normalize_gemini_model(os.getenv("GEMINI_MODEL")),
        auto_publish=_bool("AUTO_PUBLISH", False),
        database_path=os.getenv("DATABASE_PATH", "data/bot.db"),
        log_file=os.getenv("LOG_FILE", "logs/bot.log"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        tmp_dir=os.getenv("TMP_DIR", "tmp"),
    )
