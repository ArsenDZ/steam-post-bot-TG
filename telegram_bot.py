"""
Обработчики Telegram-бота: команды, приём исходного материала от админа,
кнопки предпросмотра (Опубликовать / Редактировать / Создать заново / Отменить).

Состояние диалога (ждём ли мы Steam-ссылку или правку) хранится в памяти
процесса (SESSIONS) - это осознанное упрощение для первой версии: сами
черновики (draft/preview/published/cancelled) переживают перезапуск в
SQLite, а вот "на каком шаге диалога" находится админ - нет. После
перезапуска админу достаточно просто отправить материал заново.
"""
import logging
from typing import Dict, Optional

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from database import Database
from gemini import GeminiClient, GeminiError
from image import fetch_and_process_banner, ImageError
from publisher import build_final_post, send_preview, publish_to_channel
from steam import extract_app_id, fetch_app_details, SteamError

logger = logging.getLogger("steam_post_bot")

STATE_IDLE = "idle"
STATE_AWAITING_LINK = "awaiting_link"
STATE_AWAITING_EDIT = "awaiting_edit"

# user_id -> {"state": str, "post_id": Optional[int], "pending_text": Optional[str]}
SESSIONS: Dict[int, dict] = {}


def _session(user_id: int) -> dict:
    return SESSIONS.setdefault(user_id, {"state": STATE_IDLE, "post_id": None, "pending_text": None})


def _reset_session(user_id: int) -> None:
    SESSIONS[user_id] = {"state": STATE_IDLE, "post_id": None, "pending_text": None}


def _preview_keyboard(post_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🟢 Опубликовать", callback_data=f"publish:{post_id}"),
                InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit:{post_id}"),
            ],
            [
                InlineKeyboardButton("🔄 Создать заново", callback_data=f"regenerate:{post_id}"),
                InlineKeyboardButton("❌ Отменить", callback_data=f"cancel:{post_id}"),
            ],
        ]
    )


def _is_authorized(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    db: Database = context.bot_data["db"]
    return db.is_admin(user_id)


async def _deny(update: Update) -> None:
    await update.effective_message.reply_text(
        "У вас нет доступа к этому боту. Обратитесь к владельцу канала."
    )


# ---------------------------------------------------------------- commands

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not _is_authorized(context, user_id):
        await _deny(update)
        return
    await update.effective_message.reply_text(
        "Привет! Пришлите Steam-ссылку и, при желании, текст о раздаче "
        "(например: срок окончания, инфо про значок коллекционера) — "
        "я подготовлю пост для канала.\n\n"
        "Команды: /help /admins /cancel"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not _is_authorized(context, user_id):
        await _deny(update)
        return
    await update.effective_message.reply_text(
        "Как пользоваться:\n\n"
        "1. Отправьте сообщение со Steam-ссылкой (можно с текстом или без).\n"
        "2. Если ссылки не было — пришлю запрос, скиньте её отдельным сообщением.\n"
        "3. Я получу данные и баннер игры и подготовлю пост через Gemini.\n"
        "4. Проверьте предпросмотр и нажмите одну из кнопок:\n"
        "   🟢 Опубликовать — отправить пост в канал\n"
        "   ✏️ Редактировать — прислать правку текстом, например "
        "\"сделай короче\" или \"убери про коллекционера\"\n"
        "   🔄 Создать заново — попросить Gemini переписать пост с нуля\n"
        "   ❌ Отменить — отменить черновик\n\n"
        "Команды:\n"
        "/admins — список администраторов бота\n"
        "/cancel — сбросить текущий диалог\n"
        "/addadmin <id> и /removeadmin <id> — только для владельца"
    )


async def cmd_admins(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not _is_authorized(context, user_id):
        await _deny(update)
        return
    db: Database = context.bot_data["db"]
    admins = db.list_admins()
    text = "Администраторы бота:\n" + "\n".join(f"- {a}" for a in admins)
    await update.effective_message.reply_text(text)


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not _is_authorized(context, user_id):
        await _deny(update)
        return
    session = _session(user_id)
    if session.get("post_id"):
        db: Database = context.bot_data["db"]
        db.update_status(session["post_id"], "cancelled")
    _reset_session(user_id)
    await update.effective_message.reply_text("Текущий диалог сброшен.")


async def cmd_addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    settings = context.bot_data["settings"]
    if user_id != settings.owner_id:
        await update.effective_message.reply_text(
            "Только владелец бота может добавлять администраторов."
        )
        return
    if not context.args:
        await update.effective_message.reply_text("Использование: /addadmin <telegram_user_id>")
        return
    try:
        new_admin_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("ID должен быть числом.")
        return
    db: Database = context.bot_data["db"]
    added = db.add_admin(new_admin_id, added_by=user_id)
    if added:
        await update.effective_message.reply_text(f"Пользователь {new_admin_id} добавлен в администраторы.")
    else:
        await update.effective_message.reply_text("Этот пользователь уже администратор.")


async def cmd_removeadmin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    settings = context.bot_data["settings"]
    if user_id != settings.owner_id:
        await update.effective_message.reply_text(
            "Только владелец бота может удалять администраторов."
        )
        return
    if not context.args:
        await update.effective_message.reply_text("Использование: /removeadmin <telegram_user_id>")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("ID должен быть числом.")
        return
    if target_id == settings.owner_id:
        await update.effective_message.reply_text("Нельзя удалить владельца бота.")
        return
    db: Database = context.bot_data["db"]
    removed = db.remove_admin(target_id)
    if removed:
        await update.effective_message.reply_text(f"Пользователь {target_id} удалён из администраторов.")
    else:
        await update.effective_message.reply_text("Этот пользователь не найден среди администраторов.")


# ---------------------------------------------------------------- messages

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not _is_authorized(context, user_id):
        await _deny(update)
        return

    message = update.effective_message
    text = (message.text or message.caption or "").strip()
    session = _session(user_id)

    if session["state"] == STATE_AWAITING_EDIT and session.get("post_id"):
        await _handle_edit_instruction(update, context, user_id, text)
        return

    if session["state"] == STATE_AWAITING_LINK:
        combined_text = (session.get("pending_text") or "") + "\n" + text
        app_id = extract_app_id(combined_text)
        if not app_id:
            await message.reply_text(
                "Steam-ссылка не найдена. Пришлите, пожалуйста, ссылку вида "
                "https://store.steampowered.com/app/12345/"
            )
            return
        _reset_session(user_id)
        await _process_new_submission(update, context, combined_text)
        return

    # обычное новое сообщение
    app_id = extract_app_id(text)
    if not app_id:
        session["state"] = STATE_AWAITING_LINK
        session["pending_text"] = text
        await message.reply_text(
            "Не нашёл в сообщении Steam-ссылку. Пришлите её, пожалуйста, "
            "отдельным сообщением (например https://store.steampowered.com/app/12345/)."
        )
        return

    await _process_new_submission(update, context, text)


async def _process_new_submission(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    message = update.effective_message
    user_id = update.effective_user.id
    db: Database = context.bot_data["db"]
    gemini: GeminiClient = context.bot_data["gemini"]
    settings = context.bot_data["settings"]

    app_id = extract_app_id(text)
    status_msg = await message.reply_text("Получаю данные из Steam...")

    try:
        info = fetch_app_details(app_id)
    except SteamError as e:
        logger.error("Steam error for app_id=%s: %s", app_id, e)
        await status_msg.edit_text(f"⚠️ Не удалось получить данные из Steam: {e}")
        return

    banner_path: Optional[str] = None
    if info.image_url:
        try:
            banner_path = fetch_and_process_banner(info.image_url, info.app_id, settings.tmp_dir)
        except ImageError as e:
            logger.error("Image error for app_id=%s: %s", app_id, e)
            await message.reply_text(
                "⚠️ Не удалось загрузить/обработать баннер игры, продолжаю без изображения."
            )
    else:
        await message.reply_text("⚠️ У Steam нет изображения для этой игры, продолжаю без баннера.")

    await status_msg.edit_text("Данные получены, готовлю текст через Gemini...")

    post_id = db.create_post(
        admin_id=user_id,
        steam_app_id=info.app_id,
        game_name=info.name,
        steam_url=info.steam_url,
        image_url=info.image_url,
        image_local_path=banner_path,
        original_text=text,
        draft_text=None,
        status="draft",
    )

    try:
        raw_text = gemini.create_post(
            game_name=info.name,
            steam_url=info.steam_url,
            original_text=text,
            developers=info.developers,
            publishers=info.publishers,
            release_date=info.release_date,
        )
    except GeminiError as e:
        logger.error("Gemini error for post_id=%s: %s", post_id, e)
        db.update_status(post_id, "draft")
        await status_msg.edit_text(
            "⚠️ Gemini временно недоступен, не удалось подготовить текст. "
            "Черновик сохранён — данные не потеряны, можно будет обработать его позже. "
            f"(ID черновика: {post_id})"
        )
        return

    db.update_draft_text(post_id, raw_text)

    await status_msg.delete()
    await _show_preview_or_publish(update, context, post_id, info.name, info.steam_url, raw_text, banner_path)


async def _show_preview_or_publish(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    post_id: int,
    game_name: str,
    steam_url: str,
    raw_text: str,
    banner_path: Optional[str],
) -> None:
    db: Database = context.bot_data["db"]
    settings = context.bot_data["settings"]
    final_text = build_final_post(game_name, steam_url, raw_text)

    if settings.auto_publish:
        try:
            await publish_to_channel(context.bot, settings.telegram_channel_id, banner_path, final_text)
        except Exception as e:
            logger.error("Publish error (auto_publish) for post_id=%s: %s", post_id, e, exc_info=True)
            await update.effective_message.reply_text(
                f"⚠️ Не удалось опубликовать пост автоматически: {e}. "
                f"Черновик сохранён (ID {post_id}), статус остался preview."
            )
            db.update_status(post_id, "preview")
            return
        db.update_status(post_id, "published")
        await update.effective_message.reply_text("✅ Пост автоматически опубликован в канал (AUTO_PUBLISH=true).")
        return

    db.update_status(post_id, "preview")
    await send_preview(
        context.bot,
        update.effective_chat.id,
        banner_path,
        final_text,
        _preview_keyboard(post_id),
    )


async def _handle_edit_instruction(
    update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, instruction: str
) -> None:
    db: Database = context.bot_data["db"]
    gemini: GeminiClient = context.bot_data["gemini"]
    session = _session(user_id)
    post_id = session["post_id"]

    post = db.get_post(post_id)
    if not post:
        await update.effective_message.reply_text("Черновик не найден, начните заново.")
        _reset_session(user_id)
        return

    status_msg = await update.effective_message.reply_text("Вношу правку через Gemini...")

    try:
        new_raw_text = gemini.revise_post(post.draft_text, instruction)
    except GeminiError as e:
        logger.error("Gemini revise error for post_id=%s: %s", post_id, e)
        await status_msg.edit_text(
            f"⚠️ Gemini временно недоступен, не удалось внести правку: {e}. "
            "Прошлая версия черновика сохранена, попробуйте ещё раз чуть позже."
        )
        return

    db.update_draft_text(post_id, new_raw_text)
    _reset_session(user_id)
    await status_msg.delete()

    await _show_preview_or_publish(
        update, context, post_id, post.game_name, post.steam_url, new_raw_text, post.image_local_path
    )


# ---------------------------------------------------------------- buttons

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.from_user.id

    if not _is_authorized(context, user_id):
        await query.answer("Нет доступа.", show_alert=True)
        return

    action, _, post_id_str = query.data.partition(":")
    post_id = int(post_id_str)

    db: Database = context.bot_data["db"]
    post = db.get_post(post_id)
    if not post:
        await query.answer("Черновик не найден.", show_alert=True)
        return

    if action == "publish":
        await query.answer("Публикую...")
        settings = context.bot_data["settings"]
        final_text = build_final_post(post.game_name, post.steam_url, post.draft_text)
        try:
            await publish_to_channel(
                context.bot, settings.telegram_channel_id, post.image_local_path, final_text
            )
        except Exception as e:
            logger.error("Publish error for post_id=%s: %s", post_id, e, exc_info=True)
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"⚠️ Не удалось опубликовать пост: {e}. Черновик сохранён, попробуйте ещё раз.",
            )
            return
        db.update_status(post_id, "published")
        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(chat_id=query.message.chat_id, text="✅ Пост опубликован в канал.")

    elif action == "edit":
        await query.answer()
        session = _session(user_id)
        session["state"] = STATE_AWAITING_EDIT
        session["post_id"] = post_id
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="Пришлите текстом, что исправить (например: \"сделай короче\" "
                 "или \"убери информацию про коллекционера\").",
        )

    elif action == "regenerate":
        await query.answer("Создаю заново...")
        gemini: GeminiClient = context.bot_data["gemini"]
        try:
            new_raw_text = gemini.create_post(
                game_name=post.game_name,
                steam_url=post.steam_url,
                original_text=post.original_text,
            )
        except GeminiError as e:
            logger.error("Gemini regenerate error for post_id=%s: %s", post_id, e)
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"⚠️ Gemini временно недоступен: {e}. Прошлая версия черновика сохранена.",
            )
            return
        db.update_draft_text(post_id, new_raw_text)
        final_text = build_final_post(post.game_name, post.steam_url, new_raw_text)
        await send_preview(
            context.bot, query.message.chat_id, post.image_local_path, final_text, _preview_keyboard(post_id)
        )

    elif action == "cancel":
        await query.answer("Отменено.")
        db.update_status(post_id, "cancelled")
        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(chat_id=query.message.chat_id, text="❌ Черновик отменён.")
