"""Менеджер игровых комнат"""
import asyncio
import logging
import string
import random
from typing import Optional
from services.game_state import GameState
from services.ai_service import AIService
from services.phase_handler import PhaseHandler
from repositories.game_repo import GameRepository

logger = logging.getLogger(__name__)

MAX_PLAYERS_PER_ROOM = 12
ROOM_CODE_LENGTH = 4
ROOM_CODE_CHARS = string.ascii_uppercase


def generate_room_code() -> str:
    """Генерирует короткий код комнаты типа ABCD"""
    return ''.join(random.choices(ROOM_CODE_CHARS, k=ROOM_CODE_LENGTH))


class RoomManager:
    """Управление игровыми комнатами"""

    def __init__(self, repo: GameRepository):
        self.repo = repo
        self.rooms: dict[str, 'GameRoom'] = {}
        self._cleanup_tasks: dict[str, asyncio.Task] = {}
        self._create_lock = asyncio.Lock()

    def create_room(self, host_name: str) -> 'GameRoom':
        """Создать новую комнату (вызывать через await create_room_async для атомарности)"""
        # Генерируем уникальный код
        for _ in range(100):
            code = generate_room_code()
            if code not in self.rooms:
                break
        else:
            raise RuntimeError("Не удалось создать уникальный код комнаты")

        room = GameRoom(code, host_name, self.repo)
        self.rooms[code] = room
        logger.info(f"🏠 Комната создана: {code} (хост: {host_name})")
        return room

    async def create_room_async(self, host_name: str) -> 'GameRoom':
        """Атомарное создание комнаты (без race condition)"""
        async with self._create_lock:
            return self.create_room(host_name)

    def get_room(self, code: str) -> Optional['GameRoom']:
        """Получить комнату по коду"""
        return self.rooms.get(code)

    def list_rooms(self) -> list[dict]:
        """Список активных комнат для отображения в лобби"""
        result = []
        for code, room in self.rooms.items():
            if room.game_state.current_phase == "lobby":
                result.append({
                    "code": code,
                    "host": room.host_name,
                    "players": len(room.game_state.players),
                    "max_players": MAX_PLAYERS_PER_ROOM,
                    "phase": room.game_state.current_phase,
                })
        return result

    def remove_room(self, code: str):
        """Удалить комнату"""
        if code in self.rooms:
            room = self.rooms[code]
            # Отменяем задачу очистки если есть
            if code in self._cleanup_tasks and not self._cleanup_tasks[code].done():
                self._cleanup_tasks[code].cancel()
            del self.rooms[code]
            logger.info(f"🏠 Комната удалена: {code}")

    def schedule_cleanup(self, code: str, delay: int = 0):
        """Запланировать удаление комнаты через delay секунд (по умолчанию — мгновенно)"""
        async def cleanup():
            if delay > 0:
                await asyncio.sleep(delay)
            if code in self.rooms:
                room = self.rooms[code]
                if not room.game_state.players:
                    self.remove_room(code)

        if code in self._cleanup_tasks and not self._cleanup_tasks[code].done():
            self._cleanup_tasks[code].cancel()
        self._cleanup_tasks[code] = asyncio.create_task(cleanup())

    def cancel_cleanup(self, code: str):
        """Отменить удаление комнаты"""
        if code in self._cleanup_tasks and not self._cleanup_tasks[code].done():
            self._cleanup_tasks[code].cancel()
            del self._cleanup_tasks[code]


class GameRoom:
    """Игровая комната"""

    def __init__(self, code: str, host_name: str, repo: GameRepository):
        self.code = code
        self.host_name = host_name
        self.repo = repo
        self.game_state = GameState()
        self.ai_service = AIService()
        self.phase_handler: Optional[PhaseHandler] = None
        self.broadcast = None
        self.voting_timer: Optional[asyncio.Task] = None
        self.voting_timer_active = False

        # Создаём broadcast и phase_handler
        self.broadcast = self._make_broadcast()
        self.phase_handler = PhaseHandler(
            self.game_state,
            self.ai_service,
            self.broadcast,
            repo=repo,
            start_voting_timer_callback=lambda: start_voting_timer(self)
        )

    async def initialize(self):
        """Асинхронная инициализация — выбор AI-личности"""
        self.game_state.ai_personality = await self.repo.get_random_ai_personality()
        self.ai_service.set_personality(self.game_state.ai_personality)
        logger.info(f"[ROOM {self.code}] AI-личность: {self.game_state.ai_personality['name']}")

    def _make_broadcast(self):
        """Создаёт функцию broadcast, привязанную к этой комнате"""
        room = self

        async def broadcast_impl(message: dict, exclude_viewer: str = None):
            import copy
            gs = room.game_state
            if not gs.players:
                return

            disconnected = []
            for player in list(gs.players.values()):
                if player.websocket:
                    try:
                        send_message = copy.deepcopy(message)
                        # Для этих типов всегда отправляем game state
                        if message.get("type") in ["player_joined", "player_ready", "game_state_update"]:
                            send_message["game"] = gs.get_game_state(player.name)
                        await player.websocket.send_json(send_message)
                    except Exception as e:
                        logger.warning(f"Ошибка отправки {player.name}: {e}")
                        disconnected.append(player.id)

            for pid in disconnected:
                if pid in gs.players:
                    gs.remove_player(pid)

        return broadcast_impl

    def is_full(self) -> bool:
        return len(self.game_state.players) >= MAX_PLAYERS_PER_ROOM

    def is_empty(self) -> bool:
        return len(self.game_state.players) == 0

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "host": self.host_name,
            "players": len(self.game_state.players),
            "max_players": MAX_PLAYERS_PER_ROOM,
            "phase": self.game_state.current_phase,
            "player_names": [p.name for p in self.game_state.players.values()],
        }


# Глобальный RoomManager — будет инициализирован в main.py
_room_manager: Optional[RoomManager] = None


def get_room_manager() -> RoomManager:
    global _room_manager
    if _room_manager is None:
        raise RuntimeError("RoomManager не инициализирован")
    return _room_manager


def init_room_manager(repo: GameRepository) -> RoomManager:
    global _room_manager
    _room_manager = RoomManager(repo)
    return _room_manager
