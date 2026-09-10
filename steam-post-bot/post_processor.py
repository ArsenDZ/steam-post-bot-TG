"""
Отделённая логика обработки (Steam → Gemini → preview).
Используется как telegram_bot.py, так и API.
Возвращает готовые данные для отправки боту/отображения.
"""
import logging
from typing import Optional, Tuple

from steam import fetch_app_details, SteamError
from image import fetch_and_process_banner, ImageError
from gemini import GeminiClient, GeminiError
from database import Database, PostRecord
from publisher import build_final_post

logger = logging.getLogger("steam_post_bot")


class PostProcessorError(Exception):
    pass


async def process_steam_link(
    db: Database,
    gemini: GeminiClient,
    user_id: int,
    steam_app_id: int,
    original_text: str,
    tmp_dir: str,
) -> Tuple[int, PostRecord, str, Optional[str]]:
    """
    Обрабатывает ссылку Steam:
    1. Получает данные из Steam
    2. Загружает баннер
    3. Создаёт черновик в БД
    4. Генерирует текст через Gemini
    5. Возвращает (post_id, PostRecord, final_text, banner_path)
    """
    # Получаем данные из Steam
    try:
        info = fetch_app_details(steam_app_id)
    except SteamError as e:
        logger.error("Steam error for app_id=%s: %s", steam_app_id, e)
        raise PostProcessorError(f"Ошибка Steam: {e}")

    # Загружаем баннер
    banner_path: Optional[str] = None
    if info.image_url:
        try:
            banner_path = fetch_and_process_banner(info.image_url, info.app_id, tmp_dir)
        except ImageError as e:
            logger.error("Image error for app_id=%s: %s", steam_app_id, e)
            logger.warning("Продолжаю без баннера")
    
    # Создаём черновик
    post_id = db.create_post(
        admin_id=user_id,
        steam_app_id=info.app_id,
        game_name=info.name,
        steam_url=info.steam_url,
        image_url=info.image_url,
        image_local_path=banner_path,
        original_text=original_text,
        draft_text=None,
        status="draft",
    )

    # Генерируем текст через Gemini
    try:
        raw_text = gemini.create_post(
            game_name=info.name,
            steam_url=info.steam_url,
            original_text=original_text,
            developers=info.developers,
            publishers=info.publishers,
            release_date=info.release_date,
        )
    except GeminiError as e:
        logger.error("Gemini error for post_id=%s: %s", post_id, e)
        db.update_status(post_id, "draft")
        raise PostProcessorError(f"Ошибка Gemini: {e}")

    db.update_draft_text(post_id, raw_text)
    
    # Собираем финальный текст (со ссылкой)
    final_text = build_final_post(info.name, info.steam_url, raw_text)
    
    # Получаем обновлённый PostRecord
    post = db.get_post(post_id)
    
    return post_id, post, final_text, banner_path


async def revise_post(
    db: Database,
    gemini: GeminiClient,
    post_id: int,
    instruction: str,
) -> Tuple[str, Optional[str]]:
    """
    Правит существующий черновик по инструкции.
    Возвращает (final_text, banner_path).
    """
    post = db.get_post(post_id)
    if not post:
        raise PostProcessorError(f"Пост {post_id} не найден")

    try:
        new_raw_text = gemini.revise_post(post.draft_text, instruction)
    except GeminiError as e:
        logger.error("Gemini revise error for post_id=%s: %s", post_id, e)
        raise PostProcessorError(f"Ошибка Gemini: {e}")

    db.update_draft_text(post_id, new_raw_text)
    
    final_text = build_final_post(post.game_name, post.steam_url, new_raw_text)
    
    return final_text, post.image_local_path
