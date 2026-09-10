# Архитектура Steam Post Bot — Web Edition

## Что было сделано

Система разделена на две части:

### 1. Backend (Python + FastAPI)

**Новые файлы:**
- `post_processor.py` — вынесённая логика обработки (Steam → Gemini → preview)
- `api.py` — FastAPI приложение с эндпоинтами для веб-интерфейса

**Что делает:**
- Получает запрос с веб-интерфейса (ссылка на Steam + комментарий)
- Обрабатывает через `post_processor.py`:
  - Парсит данные из Steam
  - Загружает баннер
  - Отправляет в Gemini для генерации текста
  - Сохраняет в БД
- Возвращает preview (финальный текст + баннер) в JSON
- При подтверждении от фронтенда публикует пост в Telegram-канал

**Деплой на:**
- Vercel Functions (если используешь Python runtime)
- Отдельный сервер (BotHost, VPS, Oracle Cloud, etc.)
- Heroku
- DigitalOcean App Platform

### 2. Frontend (Next.js + React)

**Расположение:** папка `web/`

**Новые файлы:**
- `web/components/PostForm.tsx` — форма для ввода Steam-ссылки и комментария
- `web/components/PreviewCard.tsx` — карточка предпросмотра с кнопками
- `web/app/page.tsx` — главная страница
- `web/app/layout.tsx` — layout приложения

**Что делает:**
- Форма для админа: введи ссылку на Steam и комментарий
- Отправляет запрос на API (`/api/process`)
- Показывает preview (текст + баннер)
- Две кнопки:
  - **Опубликовать** — отправляет запрос на `/api/publish`
  - **Отменить** — возвращает к форме

**Деплой на:**
- Vercel (рекомендуется, просто нажал кнопку)
- Netlify
- GitHub Pages (статический хостинг)
- Любой веб-сервер

## Поток данных

```
┌─────────────────────────────────────────────────────────────────┐
│ Админ открывает веб-интерфейс в браузере (Vercel)              │
└────────────────────────────┬────────────────────────────────────┘
                             │
                      Заполняет форму
                    (Steam link + comment)
                             │
                             ▼
         ┌───────────────────────────────────────┐
         │ Next.js отправляет POST /api/process  │
         └────────────┬────────────────────────┬─┘
                      │                        │
                 ✅ Success                ❌ Error
                      │                        │
                      ▼                        ▼
            ┌──────────────────┐     Показывает ошибку
            │  FastAPI Backend │     в интерфейсе
            │                  │
            │ 1. Steam парсинг │
            │ 2. Gemini обработка
            │ 3. Сохранение БД │
            │ 4. Готовит JSON  │
            └────────┬─────────┘
                     │
           ┌─────────┴─────────┐
           ▼                   ▼
    ✅ POST /api/process  ❌ Ошибка
    возвращает JSON         ошибки
           │                   │
           ▼                   ▼
    Frontend показывает    Показывает
    Preview + кнопки       сообщение
           │
      ┌────┴─────────────────┐
      │ Админ видит:         │
      │ - Баннер игры        │
      │ - Текст поста        │
      │ - 2 кнопки:          │
      │   📱 Опубликовать    │
      │   ❌ Отменить        │
      └────┬──────────┬──────┘
           │          │
     Нажимает      Нажимает
     публикацию    отмену
           │          │
           ▼          ▼
    POST /api/     Возврат
    publish        к форме
           │
    ┌──────▼──────────────┐
    │ API отправляет      │
    │ пост в Telegram     │
    │ канал               │
    │ (через telegram.Bot)│
    └─────────────────────┘
           │
           ▼
    ✅ Пост в канале
```

## Структура БД (не изменилась)

```sql
posts (
  id INTEGER PRIMARY KEY,
  admin_id INTEGER,
  steam_app_id INTEGER,
  game_name TEXT,
  steam_url TEXT,
  image_url TEXT,
  image_local_path TEXT,
  original_text TEXT,      -- исходный комментарий админа
  draft_text TEXT,         -- финальный текст (от Gemini)
  status TEXT,             -- 'draft' | 'preview' | 'published' | 'cancelled'
  created_at TEXT,
  published_at TEXT,
)

admins (
  user_id INTEGER PRIMARY KEY,
)
```

## Безопасность

1. **API-ключи** хранятся только на сервере в `.env`
2. **Фронтенд не видит ключей** — переменные `NEXT_PUBLIC_*` видны, но там только URL API
3. **Аутентификация** может быть добавлена позже (токены, OAuth, и т.д.)
4. **CORS** настроен на `*` для простоты, позже можно ограничить доменом Vercel

## Скорость деплоя

**Шаг 1: Загрузи на GitHub** (5 минут)
```bash
git add .
git commit -m "Add web frontend and API"
git push origin main
```

**Шаг 2: Frontend на Vercel** (2 минуты)
- Зайди на https://vercel.com/import
- Выбери `web/` папку
- Добавь переменную `NEXT_PUBLIC_API_URL`
- Vercel автоматически соберёт и развернёт

**Шаг 3: Backend на сервер** (10 минут)
- SSH на твой сервер
- `git clone ...`
- `pip install -r requirements.txt`
- `uvicorn api:app --host 0.0.0.0 --port 8000`

## API Endpoints

### POST /api/process
```bash
curl -X POST http://localhost:8000/api/process \
  -H "Content-Type: application/json" \
  -d '{
    "steam_link": "https://store.steampowered.com/app/2019300/",
    "comment": "Кнопка раздачи внизу",
    "user_id": 123456
  }'
```

Response:
```json
{
  "post_id": 1,
  "game_name": "Dokimon Quest",
  "final_text": "🎮 В Steam...",
  "banner_path": "/tmp/2019300.jpg"
}
```

### POST /api/publish
```bash
curl -X POST http://localhost:8000/api/publish \
  -H "Content-Type: application/json" \
  -d '{"post_id": 1, "user_id": 123456}'
```

Response:
```json
{
  "status": "published",
  "post_id": 1
}
```

### GET /api/health
```bash
curl http://localhost:8000/api/health
```

## Следующие шаги

1. **Тестирование локально**
   ```bash
   # Terminal 1: Backend
   cd steam-post-bot
   uvicorn api:app --reload
   
   # Terminal 2: Frontend
   cd web
   npm run dev
   ```

2. **Деплой на Vercel**
   - Загрузи на GitHub
   - Импортируй `web/` в Vercel

3. **Деплой Backend**
   - Выбери сервер (BotHost, VPS, etc.)
   - Установи Python и зависимости
   - Запусти `uvicorn api:app --host 0.0.0.0 --port 8000`
   - Используй systemd для автозапуска

4. **Настройка переменной окружения на Vercel**
   ```
   NEXT_PUBLIC_API_URL=https://api.example.com
   ```

5. **Добавить аутентификацию** (опционально)
   - Токены для API
   - Login на фронтенде
   - Проверка администраторов

## Трубулшутинг

**Frontend не подключается к API?**
- Проверь `NEXT_PUBLIC_API_URL` в Vercel переменных окружения
- Проверь CORS на backend (должен быть `*` или твой домен Vercel)

**Gemini возвращает ошибку?**
- Проверь API-ключ в `.env`
- Проверь квоту на Gemini Dashboard

**Пост не публикуется?**
- Проверь `TELEGRAM_BOT_TOKEN` и `TELEGRAM_CHANNEL_ID`
- Убедись, что бот добавлен администратором в канал

---

**Вопросы?** Проверь `DEPLOY.md` для подробных инструкций.
