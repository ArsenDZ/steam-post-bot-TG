"""
Точка входа. Собирает Application, регистрирует обработчики, запускает polling.
"""
import logging

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from config import load_settings
from logger_setup import setup_logging
from database import Database
from gemini import GeminiClient
import telegram_bot as tb


def main():
    settings = load_settings()
    logger = setup_logging(settings.log_file, settings.log_level)
    logger.info("Запуск steam-post-bot. AUTO_PUBLISH=%s", settings.auto_publish)

    db = Database(settings.database_path)
    # OWNER_ID и стартовый список ADMIN_IDS из .env сеются в SQLite один раз;
    # дальше администраторов можно менять командами /addadmin, /removeadmin.
    db.seed_admins([settings.owner_id, *settings.initial_admin_ids])

    gemini = GeminiClient(settings.gemini_api_key, settings.gemini_model)

    application = Application.builder().token(settings.telegram_bot_token).build()
    application.bot_data["db"] = db
    application.bot_data["gemini"] = gemini
    application.bot_data["settings"] = settings

    application.add_handler(CommandHandler("start", tb.cmd_start))
    application.add_handler(CommandHandler("help", tb.cmd_help))
    application.add_handler(CommandHandler("admins", tb.cmd_admins))
    application.add_handler(CommandHandler("cancel", tb.cmd_cancel))
    application.add_handler(CommandHandler("addadmin", tb.cmd_addadmin))
    application.add_handler(CommandHandler("removeadmin", tb.cmd_removeadmin))

    application.add_handler(
        MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, tb.handle_message)
    )
    application.add_handler(CallbackQueryHandler(tb.handle_callback))

    logger.info("Бот запущен, жду сообщений...")
    application.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
