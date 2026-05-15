"""Управление состоянием игры"""
import logging
import random
from collections import deque
from typing import Dict, List, Optional
from models.player import Player
from config.settings import MAX_ROUNDS

logger = logging.getLogger(__name__)

PHASES = {
    "lobby": "ОЖИДАНИЕ",
    "round_start": "НАЧАЛО РАУНДА",
    "reveal_card": "РАСКРЫТИЕ КАРТ",
    "discussion": "ОБСУЖДЕНИЕ",
    "final_word": "ФИНАЛЬНОЕ СЛОВО",
    "voting": "ГОЛОСОВАНИЕ",
    "reveal": "РАСКРЫТИЕ КАРТЫ ВЫБЫВШЕГО",
    "results": "РЕЗУЛЬТАТЫ"
}


class GameState:
    """Класс для управления состоянием игры"""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """Сброс состояния"""
        self.players: Dict[str, Player] = {}
        self.ai_thoughts: List[dict] = []
        self.game_started = False
        self.current_phase = "lobby"
        self.current_round = 0
        self.max_rounds = MAX_ROUNDS
        
        # Порядки игроков
        self.discussion_order: List[Player] = []
        self.presentation_order: List[Player] = []
        self.reveal_order: List[Player] = []
        self.current_speaker_index = 0
        self.current_reveal_index = 0
        
        # Бункер
        self.bunker_spots = 0
        self.bunker_capacity = 0
        self.players_in_bunker: List[Player] = []
        self.players_eliminated: List[Player] = []
        
        # Карты
        self.current_catastrophe = None
        self.current_bunker_card = None
        self.current_threat_card = None
        self.threat_history: List[dict] = []
        
        # AI
        self.ai_personality = None

        # Бункер (инициализируется при старте игры)
        self.current_bunker = None

        # Голосования
        self.voting_results = {}
        
        # Лог игры (ограничен 1000 записями)
        self.game_log: deque = deque(maxlen=1000)
        
        logger.info("🔄 Состояние игры сброшено")
    
    def soft_reset(self):
        """Мягкий сброс между играми (сохраняет игроков)"""
        for p in self.players.values():
            p.ready = False
            p.vote = None
            p.in_bunker = False
            p.eliminated = False
            p.presentation_text = ""
            p.sick = False
            p.skipping_vote = False
            p.character.secret_revealed = False
            p.character.profession_revealed = False
            p.character.condition_revealed = False
            p.character.dossier_revealed = False
            p.character.traits_revealed = []
        
        self.ai_thoughts.clear()
        self.game_started = False
        self.current_phase = "lobby"
        self.current_round = 0
        self.discussion_order.clear()
        self.presentation_order.clear()
        self.reveal_order.clear()
        self.current_reveal_index = 0
        self.current_speaker_index = 0
        self.bunker_spots = 0
        self.bunker_capacity = 0
        self.players_in_bunker.clear()
        self.players_eliminated.clear()
        self.voting_results.clear()
        self.current_catastrophe = None
        self.current_bunker_card = None
        self.current_threat_card = None
        self.threat_history.clear()
        self.game_log.clear()
        self.current_bunker = None
        
        logger.info("🔄 Мягкий сброс состояния")
    
    def hard_reset_if_no_players(self):
        """Полный сброс если нет игроков"""
        if not self.players:
            self.reset()
    
    def get_phase_name(self, phase: str = None) -> str:
        """Получение названия фазы"""
        phase = phase or self.current_phase
        return PHASES.get(phase, phase)
    
    def get_active_players(self) -> List[Player]:
        """Получение активных игроков (не выбывших)"""
        return [p for p in self.players.values() if not p.eliminated]
    
    def get_alive_candidates(self) -> List[Player]:
        """Получение живых кандидатов (не в бункере и не выбывшие)"""
        return [p for p in self.players.values() 
                if not p.eliminated and not p.in_bunker]
    
    def get_current_speaker(self) -> Optional[Player]:
        """Получение текущего говорящего"""
        if self.discussion_order and self.current_speaker_index < len(self.discussion_order):
            return self.discussion_order[self.current_speaker_index]
        return None
    
    def get_current_reveal_player(self) -> Optional[Player]:
        """Получение игрока который должен раскрыть карту"""
        if self.reveal_order and self.current_reveal_index < len(self.reveal_order):
            return self.reveal_order[self.current_reveal_index]
        return None
    
    def next_speaker(self) -> Optional[Player]:
        """Переход к следующему говорящему"""
        if self.discussion_order and self.current_speaker_index < len(self.discussion_order) - 1:
            self.current_speaker_index += 1
            return self.discussion_order[self.current_speaker_index]
        return None
    
    def next_reveal_player(self) -> Optional[Player]:
        """Переход к следующему игроку для раскрытия"""
        if self.reveal_order and self.current_reveal_index < len(self.reveal_order) - 1:
            self.current_reveal_index += 1
            return self.reveal_order[self.current_reveal_index]
        return None
    
    def is_discussion_complete(self) -> bool:
        """Проверка завершено ли обсуждение"""
        return self.current_speaker_index >= len(self.discussion_order) - 1
    
    def is_reveal_complete(self) -> bool:
        """Проверка завершено ли раскрытие карт"""
        return self.current_reveal_index >= len(self.reveal_order) - 1
    
    def get_bunker_data(self) -> Optional[dict]:
        """Получение данных о бункере"""
        if not self.current_bunker:
            return None
        
        return {
            "name": self.current_bunker.get('name', 'Неизвестный бункер'),
            "max_capacity": self.current_bunker.get('max_capacity', 25),
            "food_supply": self.current_bunker.get('food_supply', 100),
            "water_supply": self.current_bunker.get('water_supply', 100),
            "medicine_supply": self.current_bunker.get('medicine_supply', 80),
            "morale_level": self.current_bunker.get('morale_level', 70),
            "special_features": self.current_bunker.get('special_features', 'Стандартный бункер')
        }
    
    def get_game_state(self, viewer_name: str = None) -> dict:
        """Получение полного состояния игры для клиента"""
        from config.settings import AI_AVAILABLE
        
        active_players = self.get_active_players()
        eliminated_players = [p for p in self.players.values() if p.eliminated]
        
        current_speaker = self.get_current_speaker()
        current_reveal_player = self.get_current_reveal_player()
        
        # Определяем текущего игрока для фазы раскрытия
        current_reveal_name = None
        if self.current_phase == "reveal_card" and current_reveal_player:
            current_reveal_name = current_reveal_player.name
        
        return {
            "players": [p.to_dict(viewer_name) for p in active_players],
            "eliminated_players": [p.to_dict(viewer_name) for p in eliminated_players],
            "players_in_bunker": [p.name for p in self.players_in_bunker],
            "ai_thoughts": self.ai_thoughts[-10:],
            "ai_available": AI_AVAILABLE,
            "ai_personality": self.ai_personality.get("name", "Классический") if self.ai_personality else "Классический",
            "ai_personality_desc": self.ai_personality.get("description", "") if self.ai_personality else "",
            "game_started": self.game_started,
            "current_phase": self.current_phase,
            "phase_name": self.get_phase_name(),
            "current_speaker": current_speaker.name if current_speaker else None,
            "current_reveal_player": current_reveal_name,
            "players_count": len(active_players),
            "bunker_spots": self.bunker_spots,
            "bunker_capacity": self.bunker_capacity,
            "catastrophe": self.current_catastrophe,
            "bunker": self.get_bunker_data(),
            "current_threat": self.current_threat_card,
            "threat_history": self.threat_history,
            "round_number": self.current_round,
            "max_rounds": self.max_rounds
        }
    
    def add_player(self, player: Player):
        """Добавление игрока"""
        self.players[player.id] = player
        logger.info(f"✅ Игрок добавлен: {player.name} (ID: {player.id})")
    
    def remove_player(self, player_id: str):
        """Удаление игрока"""
        if player_id in self.players:
            player = self.players[player_id]
            # Удаляем из порядков
            if player in self.discussion_order:
                self.discussion_order.remove(player)
            if player in self.presentation_order:
                self.presentation_order.remove(player)
            if player in self.reveal_order:
                self.reveal_order.remove(player)
            
            del self.players[player_id]
            logger.info(f"✅ Игрок удалён: {player.name}")
            self.hard_reset_if_no_players()
    
    def get_context_for_ai(self) -> dict:
        """Получение контекста для AI"""
        return {
            'bunker': self.current_bunker if hasattr(self, 'current_bunker') else None,
            'catastrophe': self.current_catastrophe,
            'threat': self.current_threat_card,
            'threat_history': self.threat_history,
            'round': self.current_round
        }
