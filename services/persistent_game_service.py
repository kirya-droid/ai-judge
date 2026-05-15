"""Персистентный сервис управления игрой с хранением в SQLite"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
import aiosqlite

from models.player import Player
from repositories.game_repo import GameRepository

logger = logging.getLogger(__name__)


class PersistentGameService:
    """Сервис для персистентного хранения состояния игры"""
    
    def __init__(self, repo: GameRepository):
        self.repo = repo
        self.db_path = repo.db_path
        self._lock = asyncio.Lock()
        
    async def init_db(self):
        """Инициализация таблиц для хранения состояния игр"""
        async with aiosqlite.connect(self.db_path) as db:
            # Таблица для хранения состояния комнат
            await db.execute('''
                CREATE TABLE IF NOT EXISTS game_rooms (
                    room_code TEXT PRIMARY KEY,
                    host_name TEXT NOT NULL,
                    phase TEXT DEFAULT 'lobby',
                    current_round INTEGER DEFAULT 0,
                    max_rounds INTEGER DEFAULT 5,
                    catastrophe TEXT,
                    bunker_card TEXT,
                    threat_card TEXT,
                    ai_personality TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            ''')
            
            # Таблица для хранения игроков в комнате
            await db.execute('''
                CREATE TABLE IF NOT EXISTS room_players (
                    id TEXT PRIMARY KEY,
                    room_code TEXT NOT NULL,
                    name TEXT NOT NULL,
                    role TEXT,
                    ready INTEGER DEFAULT 0,
                    in_bunker INTEGER DEFAULT 0,
                    eliminated INTEGER DEFAULT 0,
                    vote TEXT,
                    presentation_text TEXT,
                    sick INTEGER DEFAULT 0,
                    skipping_vote INTEGER DEFAULT 0,
                    websocket_connected INTEGER DEFAULT 0,
                    FOREIGN KEY (room_code) REFERENCES game_rooms(room_code) ON DELETE CASCADE
                )
            ''')
            
            # Таблица для порядка обсуждения
            await db.execute('''
                CREATE TABLE IF NOT EXISTS discussion_order (
                    room_code TEXT NOT NULL,
                    player_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    PRIMARY KEY (room_code, player_id),
                    FOREIGN KEY (room_code) REFERENCES game_rooms(room_code) ON DELETE CASCADE,
                    FOREIGN KEY (player_id) REFERENCES room_players(id) ON DELETE CASCADE
                )
            ''')
            
            # Таблица для логов игры
            await db.execute('''
                CREATE TABLE IF NOT EXISTS game_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_code TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    data TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (room_code) REFERENCES game_rooms(room_code) ON DELETE CASCADE
                )
            ''')
            
            await db.commit()
            logger.info("✅ PersistentGameService инициализирован")
    
    async def save_room(self, room_code: str, host_name: str, 
                       phase: str = "lobby", current_round: int = 0,
                       catastrophe: str = None, bunker_card: str = None,
                       threat_card: str = None, ai_personality: str = None):
        """Сохранение состояния комнаты"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    INSERT OR REPLACE INTO game_rooms 
                    (room_code, host_name, phase, current_round, max_rounds, 
                     catastrophe, bunker_card, threat_card, ai_personality, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (room_code, host_name, phase, current_round, 5,
                      json.dumps(catastrophe) if catastrophe else None,
                      json.dumps(bunker_card) if bunker_card else None,
                      json.dumps(threat_card) if threat_card else None,
                      json.dumps(ai_personality) if ai_personality else None,
                      datetime.now().isoformat()))
                await db.commit()
    
    async def save_player(self, player: Player, room_code: str):
        """Сохранение игрока в комнате"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    INSERT OR REPLACE INTO room_players
                    (id, room_code, name, role, ready, in_bunker, eliminated,
                     vote, presentation_text, sick, skipping_vote, websocket_connected)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (player.id, room_code, player.name, player.role,
                      1 if player.ready else 0,
                      1 if player.in_bunker else 0,
                      1 if player.eliminated else 0,
                      player.vote, player.presentation_text,
                      1 if player.sick else 0,
                      1 if player.skipping_vote else 0,
                      1 if player.websocket is not None else 0))
                await db.commit()
    
    async def save_discussion_order(self, room_code: str, order: List[Player]):
        """Сохранение порядка обсуждения"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                # Удаляем старый порядок
                await db.execute('DELETE FROM discussion_order WHERE room_code = ?', (room_code,))
                
                # Добавляем новый
                for i, player in enumerate(order):
                    await db.execute('''
                        INSERT INTO discussion_order (room_code, player_id, position)
                        VALUES (?, ?, ?)
                    ''', (room_code, player.id, i))
                
                await db.commit()
    
    async def log_event(self, room_code: str, event_type: str, data: dict):
        """Логирование события игры"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT INTO game_logs (room_code, event_type, data)
                VALUES (?, ?, ?)
            ''', (room_code, event_type, json.dumps(data)))
            await db.commit()
    
    async def get_room_state(self, room_code: str) -> Optional[dict]:
        """Получение состояния комнаты"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                'SELECT * FROM game_rooms WHERE room_code = ?', (room_code,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return dict(row)
        return None
    
    async def get_room_players(self, room_code: str) -> List[dict]:
        """Получение списка игроков в комнате"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                'SELECT * FROM room_players WHERE room_code = ?', (room_code,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def delete_room(self, room_code: str):
        """Удаление комнаты и всех связанных данных"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('DELETE FROM game_rooms WHERE room_code = ?', (room_code,))
                await db.commit()
    
    async def cleanup_empty_rooms(self):
        """Очистка пустых комнат"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                DELETE FROM game_rooms 
                WHERE room_code NOT IN (SELECT DISTINCT room_code FROM room_players)
            ''')
            await db.commit()
