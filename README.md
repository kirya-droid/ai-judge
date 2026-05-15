# БУНКЕР - Многопользовательская веб-игра

Классическая игра "Бункер" с AI-судьёй на базе DeepSeek.

## 📁 Структура проекта

```
Bunker/
├── main.py              # Точка входа (FastAPI приложение)
├── db.py                # Работа с SQLite (данные из БД)
├── config/              # Конфигурация
│   ├── __init__.py
│   └── settings.py      # Настройки приложения
├── models/              # Модели данных
│   ├── __init__.py
│   ├── character.py     # Класс Character (персонаж игрока)
│   └── player.py        # Класс Player (игрок)
├── services/            # Бизнес-логика
│   ├── __init__.py
│   ├── ai_service.py    # AI сервис (DeepSeek API)
│   ├── game_state.py    # Управление состоянием игры
│   └── phase_handler.py # Обработчик игровых фаз
├── routers/             # HTTP/WebSocket роутеры
│   ├── __init__.py
│   └── ws_router.py     # WebSocket обработчик
├── static/              # Клиентская часть
│   ├── index.html
│   ├── css/style.css
│   └── js/game.js
├── .env                 # Переменные окружения (API ключи)
├── requirements.txt     # Зависимости Python
└── game_state.db        # SQLite база данных
```

## 🚀 Запуск

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Настройка API ключа

Создайте файл `.env` с содержимым:
```
DEEPSEEK_API_KEY=ваш_ключ_api
```

### 3. Запуск сервера

```bash
python main.py
```

Или через uvicorn напрямую:
```bash
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

### 4. Открыть в браузере

```
http://127.0.0.1:8000
```

## 🎮 Игровой процесс

### Фазы игры:

1. **Лобби** - игроки подключаются и нажимают "ГОТОВ"
2. **Начало игры** - генерируются бункер, катастрофа, AI-личность
3. **Раунды** (макс. 5):
   - **Раскрытие карт** - каждый игрок раскрывает 1 карту
   - **Обсуждение** - игроки выступают, AI задаёт вопросы
   - **Финальное слово** - каждый говорит зачем его оставить
   - **Голосование** - AI принимает финальное решение
   - **Раскрытие карты выбывшего**
4. **Финал** - когда места в бункере заполнены

### 🔥 Исправление очереди ходов

**Проблема (старая версия):** После вопроса AI игра сразу переходила к следующему игроку.

**Решение (новая версия):**
- После вопроса AI игрок остаётся в очереди
- Появляется кнопка "✅ ОТВЕТИЛ" 
- Игрок может ответить на вопрос (отправить ещё сообщение)
- По нажатию "Ответил" ход переходит к следующему

## 📡 API

### WebSocket
- `WS /ws/{player_name}` - подключение к игре

### HTTP
- `GET /` - главная страница
- `GET /health` - проверка здоровья сервера

## 🛠️ Модульная архитектура

### config/settings.py
```python
from config.settings import DEEPSEEK_API_KEY, AI_AVAILABLE, MAX_ROUNDS
```

### models
```python
from models import Character, Player

character = Character("Имя")
await character.initialize()

player = Player("id", "Имя")
await player.initialize()
```

### services
```python
from services import AIService, GameState, PhaseHandler

ai_service = AIService()
game_state = GameState()
phase_handler = PhaseHandler(game_state, ai_service, broadcast)

# AI анализ
analysis = await ai_service.analyze_speech(player, text, round_num, context)

# Обработка фаз
await phase_handler.start_new_round()
await phase_handler.handle_discussion_speech(player, text)
```

## 🧪 Тестирование

Проверка синтаксиса:
```bash
py -m py_compile main.py
py -m py_compile config/*.py models/*.py services/*.py routers/*.py
```

## 📝 Зависимости

- **fastapi** - веб-фреймворк
- **uvicorn** - ASGI сервер
- **websockets** - WebSocket поддержка
- **openai** - AI (DeepSeek API)
- **python-dotenv** - переменные окружения
- **aiosqlite** - асинхронная работа с SQLite

## 🎨 Стилистика

Интерфейс выполнен в стиле Pip-Boy из Fallout:
- Зелёный терминальный текст
- Эффект scanlines
- Анимации мерцания и пульсации

## 📄 Лицензия

Учебный проект.
