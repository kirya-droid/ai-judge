# Базовый образ Python
FROM python:3.11-slim

# Устанавливаем curl для healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Рабочая директория в контейнере
WORKDIR /app

# Устанавливаем переменные окружения
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Копируем requirements.txt и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь проект
COPY . .

# Создаем директорию для логов (если нужно)
RUN mkdir -p /app/logs

# Порт, который слушает приложение
EXPOSE 8001

# Команда запуска
CMD ["python", "main.py"]
