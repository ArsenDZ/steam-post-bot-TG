# Steam Post Bot — Web Edition

Генератор постов для Telegram-канала о раздачах игр в Steam с веб-интерфейсом.

## Архитектура

```
┌─────────────────────┐
│   Next.js Фронтенд  │  (Vercel)
│   Веб-интерфейс     │
└──────────┬──────────┘
           │ HTTP
           ▼
┌─────────────────────┐
│   FastAPI Backend   │  (Vercel Functions или отдельный сервер)
│   /api/process      │  (Steam → Gemini → preview)
│   /api/publish      │  (опубликовать в канал)
└──────────┬──────────┘
           │ Telegram API
           ▼
┌─────────────────────┐
│  Telegram Bot API   │
│   Публикация в      │
│   канал             │
└─────────────────────┘
```

## Деплой на Vercel

### Шаг 1: Настройка Backend (FastAPI)

Вариант A: Использовать Vercel для Python (потребует платный план)
Вариант B: Развернуть на отдельном сервере (BotHost, VPS, Oracle, etc.)

Если развёртываешь на отдельном сервере:

```bash
# На сервере
git clone https://github.com/YOUR_USERNAME/steam-post-bot.git
cd steam-post-bot

# Установи зависимости
python -m venv venv
source venv/bin/activate  # на Windows: venv\Scripts\activate
pip install -r requirements.txt

# Настрой .env с твоими ключами
cp .env.example .env
# Редактируй .env с реальными значениями
nano .env

# Запусти API
uvicorn api:app --host 0.0.0.0 --port 8000
```

**Или используй systemd (для постоянного запуска):**

```bash
sudo nano /etc/systemd/system/steam-post-bot-api.service
```

```ini
[Unit]
Description=Steam Post Bot API
After=network-online.target

[Service]
Type=simple
User=YOUR_USER
WorkingDirectory=/home/YOUR_USER/steam-post-bot
ExecStart=/home/YOUR_USER/steam-post-bot/venv/bin/uvicorn api:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=15
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable steam-post-bot-api
sudo systemctl start steam-post-bot-api
```

### Шаг 2: Настройка Frontend (Next.js)

```bash
cd web

# Загрузи проект на GitHub
git add .
git commit -m "Initial commit"
git push origin main

# Подключи на Vercel через web-интерфейс
# https://vercel.com/import
```

**Переменные окружения на Vercel:**

```
NEXT_PUBLIC_API_URL=https://api.example.com  # URL твоего API
```

После добавления Vercel автоматически соберёт и развернёт приложение.

## Локальная разработка

### Backend

```bash
# Установи зависимости
pip install -r requirements.txt

# Настрой .env
cp .env.example .env
nano .env

# Запусти сервер
uvicorn api:app --reload
```

API будет доступен на `http://localhost:8000`

### Frontend

```bash
cd web

# Установи зависимости
npm install

# Запусти dev-сервер
npm run dev
```

Фронтенд будет доступен на `http://localhost:3000`

## Структура проекта

```
steam-post-bot/
├── main.py              # Telegram-бот (polling)
├── telegram_bot.py      # Обработчики Telegram
├── api.py               # FastAPI для веб-интерфейса
├── post_processor.py    # Вынесённая логика обработки (Steam → Gemini)
├── config.py            # Конфиг из .env
├── database.py          # SQLite
├── gemini.py            # Работа с Gemini API
├── steam.py             # Парсинг Steam
├── image.py             # Обработка баннеров
├── publisher.py         # Публикация в Telegram
├── logger_setup.py      # Логирование
├── requirements.txt     # Python-зависимости
├── data/                # SQLite база (создаётся автоматически)
├── logs/                # Логи
├── tmp/                 # Временные файлы
├── prompts/
│   └── post_editor.txt  # Промпт для Gemini
├── systemd/
│   └── steam-post-bot.service  # Запуск бота через systemd
└── web/                 # Next.js фронтенд
    ├── package.json
    ├── tsconfig.json
    ├── next.config.js
    ├── .env.local       # Переменные для фронтенда
    ├── app/
    │   ├── page.tsx
    │   └── layout.tsx
    └── components/
        ├── PostForm.tsx
        └── PreviewCard.tsx
```

## API Endpoints

### POST /api/process

Обрабатывает Steam-ссылку и генерирует пост через Gemini.

**Request:**
```json
{
  "steam_link": "https://store.steampowered.com/app/2019300/",
  "comment": "Кнопка внизу страницы, даёт +1",
  "user_id": 123456
}
```

**Response:**
```json
{
  "post_id": 1,
  "game_name": "Dokimon Quest",
  "final_text": "🎮 В Steam...",
  "banner_path": "/tmp/2019300.jpg"
}
```

### POST /api/publish

Публикует пост в Telegram-канал.

**Request:**
```json
{
  "post_id": 1,
  "user_id": 123456
}
```

**Response:**
```json
{
  "status": "published",
  "post_id": 1
}
```

### GET /api/health

Health check.

## Переменные окружения (.env)

```env
# Telegram
TELEGRAM_BOT_TOKEN=YOUR_TOKEN
TELEGRAM_CHANNEL_ID=-1001234567890

# Owner и администраторы
OWNER_ID=123456
ADMIN_IDS=123456,789012

# Gemini
GEMINI_API_KEY=YOUR_API_KEY
GEMINI_MODEL=gemini-3.6-flash

# Приложение
AUTO_PUBLISH=false
DATABASE_PATH=data/bot.db
LOG_FILE=logs/bot.log
LOG_LEVEL=INFO
TMP_DIR=tmp
```

## Важные моменты

1. **AUTO_PUBLISH=false** — посты требуют подтверждения перед публикацией
2. **Безопасность .env** — никогда не коммитьте `.env` в Git
3. **NEXT_PUBLIC_API_URL** — публичный URL твоего API на фронтенде
4. **Telegram Bot добавлен в канал** — с правами администратора
5. **Баннеры хранятся локально** — в папке `tmp/`

## Troubleshooting

**API возвращает ошибку Steam:**
- Проверь, правильная ли ссылка на игру
- Возможно, игра недоступна в твоём регионе

**Gemini возвращает ошибку:**
- Проверь API-ключ в `.env`
- Проверь квоту на Gemini

**Пост не публикуется в канал:**
- Проверь `TELEGRAM_BOT_TOKEN`
- Проверь `TELEGRAM_CHANNEL_ID`
- Убедись, что бот добавлен администратором в канал

## Лицензия

MIT
