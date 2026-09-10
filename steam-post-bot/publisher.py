"""
Сборка финального поста (кликабельная ссылка добавляется программно, а не
Gemini) и отправка баннера + текста — в чат админу на предпросмотр либо в
канал при публикации.
"""
import logging
from html import escape
from typing import Optional

from telegram import Bot, InputFile
from telegram.constants import ParseMode

logger = logging.getLogger("steam_post_bot")

# Лимит Telegram на подпись к фото (UTF-16 code units, но с запасом хватает len())
CAPTION_LIMIT = 1024


def build_final_post(game_name: str, steam_url: str, gemini_text: str) -> str:
    """
    Программно строит финальный HTML-пост: весь текст от Gemini экранируется
    для безопасного HTML, а название игры (где бы оно ни встретилось в
    тексте — в живой вступительной фразе, в отдельном блоке при нескольких
    играх и т.д.) оборачивается в кликабельную ссылку на точный Steam URL.
    Gemini ссылку не создаёт и не видит — она добавляется здесь.
    """
    text = gemini_text.strip()
    safe_name = escape(game_name)
    safe_text = escape(text)
    link = f'<a href="{escape(steam_url, quote=True)}">{safe_name}</a>'

    if safe_name in safe_text:
        # Заменяем только первое вхождение — на случай если название
        # игры случайно повторится в тексте (например, в описании).
        return safe_text.replace(safe_name, link, 1)

    # Если Gemini почему-то не упомянул название явно - подстрахуемся
    # и добавим кликабельный заголовок отдельной строкой сверху.
    return f"🎮 {link}\n\n{safe_text}" if safe_text else f"🎮 {link}"


async def send_preview(
    bot: Bot,
    chat_id: int,
    banner_path: Optional[str],
    final_text: str,
    reply_markup,
):
    """Отправляет админу баннер+текст с кнопками управления. Возвращает Message."""
    if banner_path and len(final_text) <= CAPTION_LIMIT:
        with open(banner_path, "rb") as f:
            return await bot.send_photo(
                chat_id=chat_id,
                photo=InputFile(f),
                caption=final_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
            )

    # Текст слишком длинный для подписи, либо баннера нет вовсе:
    # отправляем фото отдельно (без кнопок), а текст с кнопками - вторым сообщением.
    if banner_path:
        with open(banner_path, "rb") as f:
            await bot.send_photo(chat_id=chat_id, photo=InputFile(f))

    return await bot.send_message(
        chat_id=chat_id,
        text=final_text,
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup,
    )


async def publish_to_channel(
    bot: Bot,
    channel_id: str,
    banner_path: Optional[str],
    final_text: str,
):
    """Публикует готовый пост в канал (баннер + кликабельное название + текст)."""
    if banner_path and len(final_text) <= CAPTION_LIMIT:
        with open(banner_path, "rb") as f:
            await bot.send_photo(
                chat_id=channel_id,
                photo=InputFile(f),
                caption=final_text,
                parse_mode=ParseMode.HTML,
            )
        return

    if banner_path:
        with open(banner_path, "rb") as f:
            await bot.send_photo(chat_id=channel_id, photo=InputFile(f))

    await bot.send_message(chat_id=channel_id, text=final_text, parse_mode=ParseMode.HTML)
