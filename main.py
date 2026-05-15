"""
БУНКЕР — многопользовательская веб-игра
Точка входа приложения
"""
import logging
import sys
import io

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from config.settings import LOG_LEVEL
from repositories.game_repo import GameRepository
from services.room_manager import init_room_manager

# ============ НАСТРОЙКА ЛОГИРОВАНИЯ ============
log_handler = logging.FileHandler('game_server.log', mode='a', encoding='utf-8')
log_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, "INFO"),
    handlers=[console_handler, log_handler]
)
logger = logging.getLogger(__name__)


# ============ LIFESPAN ============
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Инициализация при запуске"""
    logger.info("Запуск сервера Бункер...")
    try:
        repo = GameRepository()
        await repo.init_db()
        logger.info("SQLite инициализирован")
    except Exception as e:
        logger.error(f"Ошибка инициализации БД: {e}")

    # Инициализируем RoomManager
    init_room_manager(repo)
    logger.info("RoomManager инициализирован")

    yield
    logger.info("Сервер остановлен")


app = FastAPI(title="Бункер", version="4.0.0", lifespan=lifespan)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Статические файлы
app.mount("/static", StaticFiles(directory="static"), name="static")

# Импорт роутеров
from routers.ws_router import handle_websocket
from routers.http_router import router as http_router

app.include_router(http_router)


# ============ HTTP РОУТЫ ============
@app.get("/", response_class=HTMLResponse)
async def get_lobby():
    """Страница лобби"""
    return FileResponse("static/lobby.html")


@app.get("/game/{room_code}", response_class=HTMLResponse)
async def get_game():
    """Страница игры"""
    return FileResponse("static/game.html")


@app.get("/health")
async def health_check():
    from services.room_manager import get_room_manager
    rm = get_room_manager()
    rooms = rm.list_rooms()
    return {
        "status": "ok",
        "active_rooms": len(rooms),
        "total_players": sum(r["players"] for r in rooms),
    }


# ============ WEBSOCKET ============
@app.websocket("/ws/{room_code}/{player_name}")
async def websocket_endpoint(websocket: WebSocket, room_code: str, player_name: str):
    await handle_websocket(websocket, room_code, player_name)


# ============ ЗАПУСК ============
if __name__ == "__main__":
    from config.settings import AI_AVAILABLE, DEEPSEEK_API_KEY
    import uvicorn

    print("=" * 50)
    print("БУНКЕР v4.0 — СЕРВЕР ЗАПУЩЕН")
    print("=" * 50)
    print(f"AI статус: {'ПОДКЛЮЧЁН' if AI_AVAILABLE else 'ОТКЛЮЧЁН'}")
    if AI_AVAILABLE and DEEPSEEK_API_KEY:
        print(f"API ключ: {DEEPSEEK_API_KEY[:8]}...")
    print("Лобби: http://127.0.0.1:8001/")
    print("reload: ОТКЛЮЧЁН")
    print("=" * 50)

    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="info")
