"""
FastAPI для веб-интерфейса.
Получает запросы с веба, обрабатывает через post_processor, возвращает preview.
Публикует посты в канал после подтверждения админа с веба.
"""
import logging
import os
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio

from config import load_settings
from logger_setup import setup_logging
from database import Database
from gemini import GeminiClient
from steam import extract_app_id, SteamError
from post_processor import process_steam_link, PostProcessorError
from publisher import publish_to_channel
from telegram import Bot

# Инициализация
settings = load_settings()
logger = setup_logging(settings.log_file, settings.log_level)

app = FastAPI(title="Steam Post Bot API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Глобальные объекты
db = Database(settings.database_path)
gemini = GeminiClient(settings.gemini_api_key, settings.gemini_model)
telegram_bot = Bot(token=settings.telegram_bot_token)


class ProcessRequest(BaseModel):
    steam_link: str
    comment: str
    user_id: int = settings.owner_id  # По умолчанию owner


class PublishRequest(BaseModel):
    post_id: int
    user_id: int = settings.owner_id


class ProcessResponse(BaseModel):
    post_id: int
    game_name: str
    final_text: str
    banner_path: Optional[str]


@app.post("/api/process", response_model=ProcessResponse)
async def process_post(req: ProcessRequest):
    """
    Обрабатывает Steam-ссылку:
    1. Получает данные из Steam
    2. Генерирует текст через Gemini
    3. Возвращает preview с post_id для дальнейшей публикации
    """
    try:
        # Извлекаем App ID из ссылки
        app_id = extract_app_id(req.steam_link)
        logger.info("API: Обработка app_id=%s от user_id=%s", app_id, req.user_id)
        
        # Обрабатываем через post_processor
        post_id, post, final_text, banner_path = await process_steam_link(
            db=db,
            gemini=gemini,
            user_id=req.user_id,
            steam_app_id=app_id,
            original_text=req.comment,
            tmp_dir=settings.tmp_dir,
        )
        
        logger.info("API: Успешно обработан post_id=%s", post_id)
        
        return ProcessResponse(
            post_id=post_id,
            game_name=post.game_name,
            final_text=final_text,
            banner_path=banner_path,
        )
    
    except ValueError as e:
        logger.error("API: Ошибка парсинга: %s", e)
        raise HTTPException(status_code=400, detail=str(e))
    except SteamError as e:
        logger.error("API: Ошибка Steam: %s", e)
        raise HTTPException(status_code=400, detail=f"Steam error: {e}")
    except PostProcessorError as e:
        logger.error("API: Ошибка обработки: %s", e)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("API: Неожиданная ошибка: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error")


@app.post("/api/publish")
async def publish_post(req: PublishRequest):
    """
    Публикует пост в Telegram-канал.
    """
    try:
        post = db.get_post(req.post_id)
        if not post:
            raise HTTPException(status_code=404, detail=f"Post {req.post_id} not found")
        
        if post.status == "published":
            raise HTTPException(status_code=400, detail="Post already published")
        
        logger.info("API: Публикация post_id=%s", req.post_id)
        
        # Публикуем в канал
        await publish_to_channel(
            bot=telegram_bot,
            channel_id=settings.telegram_channel_id,
            banner_path=post.image_local_path,
            final_text=post.draft_text,  # final_text уже с ссылкой
        )
        
        # Обновляем статус
        db.update_status(req.post_id, "published")
        
        logger.info("API: Пост опубликован post_id=%s", req.post_id)
        
        return {"status": "published", "post_id": req.post_id}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("API: Ошибка публикации: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Publish error")


@app.get("/api/health")
async def health():
    """Health check."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
