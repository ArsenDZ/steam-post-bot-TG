import os
import unittest

from config import load_settings


class GeminiModelCompatibilityTests(unittest.TestCase):
    def test_load_settings_normalizes_deprecated_model(self):
        previous = {key: os.environ.get(key) for key in (
            "TELEGRAM_BOT_TOKEN",
            "TELEGRAM_CHANNEL_ID",
            "OWNER_ID",
            "ADMIN_IDS",
            "GEMINI_API_KEY",
            "GEMINI_MODEL",
            "AUTO_PUBLISH",
            "DATABASE_PATH",
            "LOG_FILE",
            "LOG_LEVEL",
            "TMP_DIR",
        )}

        try:
            os.environ["TELEGRAM_BOT_TOKEN"] = "token"
            os.environ["TELEGRAM_CHANNEL_ID"] = "-100123"
            os.environ["OWNER_ID"] = "1"
            os.environ["ADMIN_IDS"] = "2,3"
            os.environ["GEMINI_API_KEY"] = "key"
            os.environ["GEMINI_MODEL"] = "gemini-2.0-flash"
            os.environ["AUTO_PUBLISH"] = "false"
            os.environ["DATABASE_PATH"] = "data/bot.db"
            os.environ["LOG_FILE"] = "logs/bot.log"
            os.environ["LOG_LEVEL"] = "INFO"
            os.environ["TMP_DIR"] = "tmp"

            settings = load_settings()
            self.assertEqual("gemini-3.6-flash", settings.gemini_model)
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
