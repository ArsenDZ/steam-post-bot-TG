"""
Загрузка официального изображения Steam (header/capsule/background) и
приведение его к 1920x1080 БЕЗ искажения пропорций: масштабирование "cover"
+ аккуратная центральная обрезка лишнего. Водяные знаки не добавляются,
никакие изображения не генерируются искусственно.
"""
import logging
import os
import time
import uuid

import requests
from PIL import Image, ImageOps

logger = logging.getLogger("steam_post_bot")

TARGET_SIZE = (1920, 1080)


class ImageError(Exception):
    pass


def fetch_and_process_banner(
    image_url: str, app_id: str, tmp_dir: str, timeout: int = 20, max_retries: int = 3
) -> str:
    """
    Скачивает изображение по image_url и сохраняет обработанную версию
    1920x1080 в tmp_dir. Возвращает путь к готовому файлу.
    """
    os.makedirs(tmp_dir, exist_ok=True)

    raw_bytes = _download(image_url, timeout, max_retries)

    try:
        img = Image.open(_bytes_io(raw_bytes))
        img = img.convert("RGB")
    except Exception as e:
        raise ImageError(f"Не удалось открыть изображение: {e}")

    # "cover" — масштабируем так, чтобы полностью закрыть 1920x1080, и
    # центрированно обрезаем излишек. Пропорции самой картинки не искажаются.
    fitted = ImageOps.fit(img, TARGET_SIZE, method=Image.LANCZOS, centering=(0.5, 0.5))

    filename = f"banner_{app_id}_{uuid.uuid4().hex[:8]}.jpg"
    out_path = os.path.join(tmp_dir, filename)
    fitted.save(out_path, "JPEG", quality=92)

    return out_path


def _bytes_io(raw_bytes: bytes):
    import io
    return io.BytesIO(raw_bytes)


def _download(url: str, timeout: int, max_retries: int) -> bytes:
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, timeout=timeout)
            if resp.status_code == 200:
                return resp.content
            if resp.status_code in (429, 500, 502, 503, 504):
                logger.warning(
                    "Ошибка %s при загрузке изображения (попытка %s/%s)",
                    resp.status_code, attempt, max_retries,
                )
                time.sleep(attempt * 2)
                continue
            raise ImageError(f"Не удалось загрузить изображение: HTTP {resp.status_code}")
        except requests.exceptions.Timeout:
            last_error = ImageError("Таймаут загрузки изображения")
            time.sleep(attempt * 2)
        except requests.exceptions.RequestException as e:
            last_error = ImageError(f"Сетевая ошибка при загрузке изображения: {e}")
            time.sleep(attempt * 2)

    raise last_error or ImageError("Не удалось загрузить изображение")
