# Экспортируем только классы, экземпляры создаются в ws_router
from .ai_service import AIService
from .game_state import GameState
from .phase_handler import PhaseHandler
from .room_manager import RoomManager
from .persistent_game_service import PersistentGameService

__all__ = ["AIService", "GameState", "PhaseHandler", "RoomManager", "PersistentGameService"]
