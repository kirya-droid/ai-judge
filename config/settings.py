"""Настройки приложения"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем .env из корня проекта
BASE_DIR = Path(__file__).parent.parent
env_path = BASE_DIR / ".env"
load_dotenv(env_path)

# Настройки AI
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
AI_AVAILABLE = bool(DEEPSEEK_API_KEY)

# Настройки игры
MAX_ROUNDS = 5
DEFAULT_BUNKER_CAPACITY = 25

# Логирование
LOG_LEVEL = "DEBUG"
LOG_FILE = str(BASE_DIR / "game_server.log")

# Пути
DB_PATH = str(BASE_DIR / "game_state.db")
GAME_LOG_FILE = str(BASE_DIR / "game_log.json")
