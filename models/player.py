"""Модель игрока"""
import logging
from .character import Character

logger = logging.getLogger(__name__)


class Player:
    def __init__(self, player_id: str, name: str):
        self.id = player_id
        self.name = name
        self.character = Character(name)
        self.presentation_text = ""
        self.websocket = None
        self.ready = False
        self.vote = None
        self.in_bunker = False
        self.eliminated = False
        self.sick = False
        self.skipping_vote = False

    async def initialize(self, repo):
        """Инициализация игрока и его персонажа

        Args:
            repo: GameRepository — источник данных
        """
        await self.character.initialize(repo)

    def to_dict(self, viewer_name: str = None):
        """Конвертация в словарь для отправки клиенту"""
        return {
            "id": self.id,
            "name": self.name,
            "character": self.character.to_dict(viewer_name),
            "ready": self.ready,
            "in_bunker": self.in_bunker,
            "eliminated": self.eliminated,
            "sick": self.sick,
            "skipping_vote": self.skipping_vote
        }
