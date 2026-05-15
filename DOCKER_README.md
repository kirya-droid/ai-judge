# 🐳 Docker-контейнеризация проекта БУНКЕР

## Файлы для контейнеризации

В проект добавлены следующие файлы:

- **Dockerfile** — описание образа контейнера
- **docker-compose.yml** — конфигурация для запуска через Docker Compose
- **.env.example** — шаблон файла с переменными окружения
- **.dockerignore** — исключения для сборки Docker

## Быстрый старт

### 1. Подготовка переменных окружения

Скопируйте файл `.env.example` в `.env` и укажите ваш API ключ:

```bash
cp .env.example .env
```

Отредактируйте `.env` и добавьте ваш `DEEPSEEK_API_KEY`.

### 2. Запуск через Docker Compose (рекомендуется)

```bash
# Сборка и запуск
docker-compose up --build -d

# Просмотр логов
docker-compose logs -f

# Остановка
docker-compose down
```

### 3. Запуск через Docker

```bash
# Сборка образа
docker build -t bunker-game .

# Запуск контейнера
docker run -d \
  -p 8001:8001 \
  -e DEEPSEEK_API_KEY=your_key_here \
  -e LOG_LEVEL=INFO \
  -v bunker-data:/app \
  --name bunker-game-server \
  bunker-game
```

## Доступ к приложению

После запуска приложение будет доступно по адресу:
- **Лобби:** http://localhost:8001/
- **Health check:** http://localhost:8001/health

## Тома данных

Docker Compose создаёт том `bunker-data` для сохранения:
- Базы данных (`game_state.db`)
- Логов сервера (`game_server.log`)
- Лога игр (`game_log.json`)

Данные сохраняются между перезапусками контейнера.

## Переменные окружения

| Переменная | Описание | Значение по умолчанию |
|------------|----------|----------------------|
| `DEEPSEEK_API_KEY` | API ключ для AI | (пусто) |
| `LOG_LEVEL` | Уровень логирования | `INFO` |

## Команды управления

```bash
# Пересборка и перезапуск
docker-compose up --build -d

# Остановка и удаление контейнера
docker-compose down

# Остановка и удаление контейнера с томами
docker-compose down -v

# Просмотр состояния
docker-compose ps

# Логи в реальном времени
docker-compose logs -f
```
