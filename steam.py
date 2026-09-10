"""
Steam — единственный источник истины для App ID и данных об игре.
Gemini никогда не вызывается для угадывания этих данных.
"""
import logging
import re
import time
from dataclasses import dataclass
from typing import Optional

import requests

logger = logging.getLogger("steam_post_bot")

STEAM_URL_RE = re.compile(
    r"store\.steampowered\.com/app/(\d+)", re.IGNORECASE
)
APPDETAILS_ENDPOINT = "https://store.steampowered.com/api/appdetails"


class SteamError(Exception):
    pass


@dataclass
class SteamGameInfo:
    app_id: str
    name: str
    steam_url: str
    short_description: Optional[str]
    developers: Optional[str]
    publishers: Optional[str]
    release_date: Optional[str]
    image_url: Optional[str]  # лучшее доступное горизонтальное изображение


def extract_app_id(text: str) -> Optional[str]:
    """Ищет Steam App ID в произвольном тексте сообщения."""
    if not text:
        return None
    match = STEAM_URL_RE.search(text)
    return match.group(1) if match else None


def build_steam_url(app_id: str) -> str:
    return f"https://store.steampowered.com/app/{app_id}/"


def fetch_app_details(
    app_id: str, timeout: int = 15, max_retries: int = 3
) -> SteamGameInfo:
    """
    Программно (без Gemini) получает проверенные данные об игре из Steam
    Store API. Бросает SteamError, если App ID неверный или Steam недоступен
    после нескольких попыток.
    """
    params = {"appids": app_id, "l": "russian", "cc": "us"}

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(APPDETAILS_ENDPOINT, params=params, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                return _parse_appdetails(app_id, data)
            if resp.status_code in (429, 500, 502, 503, 504):
                logger.warning(
                    "Steam API вернул %s (попытка %s/%s)", resp.status_code, attempt, max_retries
                )
                time.sleep(attempt * 2)
                continue
            raise SteamError(f"Steam API вернул ошибку {resp.status_code}")
        except requests.exceptions.Timeout:
            last_error = SteamError("Таймаут запроса к Steam API")
            time.sleep(attempt * 2)
        except requests.exceptions.RequestException as e:
            last_error = SteamError(f"Сетевая ошибка Steam API: {e}")
            time.sleep(attempt * 2)

    raise last_error or SteamError("Не удалось получить данные из Steam API")


def _parse_appdetails(app_id: str, data: dict) -> SteamGameInfo:
    entry = data.get(str(app_id))
    if not entry or not entry.get("success"):
        raise SteamError(
            f"Steam не нашёл приложение с App ID {app_id}. "
            f"Проверьте, что ссылка правильная и игра доступна в Steam."
        )

    game = entry["data"]

    image_url = (
        game.get("background_raw")
        or game.get("header_image")
        or game.get("capsule_imagev5")
        or game.get("capsule_image")
    )

    developers = ", ".join(game.get("developers", [])) or None
    publishers = ", ".join(game.get("publishers", [])) or None

    release = game.get("release_date") or {}
    release_date = release.get("date") if not release.get("coming_soon") else None

    return SteamGameInfo(
        app_id=str(app_id),
        name=game.get("name", f"App {app_id}"),
        steam_url=build_steam_url(app_id),
        short_description=game.get("short_description") or None,
        developers=developers,
        publishers=publishers,
        release_date=release_date,
        image_url=image_url,
    )
