"""
Gemini используется ТОЛЬКО для редактирования текста поста. Ему всегда
передаются уже проверенные программой данные (название, Steam URL и т.д.) —
он никогда не выбирает и не придумывает их сам. Ссылка добавляется в
publisher.py программно, а не Gemini.
"""
import logging
import os
import time

import requests

logger = logging.getLogger("steam_post_bot")

GEMINI_ENDPOINT_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)

PROMPT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts", "post_editor.txt")


class GeminiError(Exception):
    pass


def _load_system_prompt() -> str:
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read().strip()


def _build_verified_data_block(
    game_name: str,
    steam_url: str,
    original_text: str,
    developers: str = None,
    publishers: str = None,
    release_date: str = None,
) -> str:
    lines = [
        f"Название игры: {game_name}",
        f"Steam URL (только для справки, в тексте не воспроизводить): {steam_url}",
    ]
    if developers:
        lines.append(f"Разработчик: {developers}")
    if publishers:
        lines.append(f"Издатель: {publishers}")
    if release_date:
        lines.append(f"Дата релиза: {release_date}")
    lines.append("")
    lines.append("Исходный текст/информация о раздаче от администратора:")
    lines.append(original_text or "(текст не предоставлен)")
    return "\n".join(lines)


class GeminiClient:
    def __init__(self, api_key: str, model: str, timeout: int = 30, max_retries: int = 3):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.system_prompt = _load_system_prompt()

    def create_post(
        self,
        game_name: str,
        steam_url: str,
        original_text: str,
        developers: str = None,
        publishers: str = None,
        release_date: str = None,
    ) -> str:
        user_content = _build_verified_data_block(
            game_name, steam_url, original_text, developers, publishers, release_date
        )
        return self._call(user_content)

    def revise_post(self, previous_text: str, instruction: str) -> str:
        user_content = (
            "Вот уже готовый пост:\n\n"
            f"{previous_text}\n\n"
            "Внеси в него следующую правку, не добавляя фактов, которых не было "
            f"в исходных данных:\n{instruction}"
        )
        return self._call(user_content)

    def _call(self, user_content: str) -> str:
        url = GEMINI_ENDPOINT_TEMPLATE.format(model=self.model)
        payload = {
            "system_instruction": {"parts": [{"text": self.system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_content}]}],
        }
        headers = {"Content-Type": "application/json"}
        params = {"key": self.api_key}

        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = requests.post(
                    url, params=params, headers=headers, json=payload, timeout=self.timeout
                )
                if resp.status_code == 200:
                    return self._extract_text(resp.json())

                if resp.status_code in (429, 500, 502, 503, 504):
                    last_error = GeminiError(
                        f"Gemini временная ошибка {resp.status_code}"
                    )
                    logger.warning(
                        "Gemini API %s (попытка %s/%s)", resp.status_code, attempt, self.max_retries
                    )
                    time.sleep(attempt * 2)
                    continue

                raise GeminiError(f"Gemini вернул ошибку {resp.status_code}: {resp.text[:300]}")

            except requests.exceptions.Timeout:
                last_error = GeminiError("Таймаут запроса к Gemini API")
                time.sleep(attempt * 2)
            except requests.exceptions.RequestException as e:
                last_error = GeminiError(f"Сетевая ошибка при обращении к Gemini: {e}")
                time.sleep(attempt * 2)

        raise last_error or GeminiError("Не удалось получить ответ от Gemini API")

    @staticmethod
    def _extract_text(data: dict) -> str:
        try:
            candidates = data["candidates"]
            parts = candidates[0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts).strip()
            if not text:
                raise KeyError("empty text")
            return text
        except (KeyError, IndexError, TypeError) as e:
            raise GeminiError(f"Неожиданный формат ответа Gemini: {e}")
