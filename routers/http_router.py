"""HTTP API для управления комнатами"""
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.room_manager import get_room_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["rooms"])


class CreateRoomRequest(BaseModel):
    host_name: str


class RoomInfo(BaseModel):
    code: str
    host: str
    players: int
    max_players: int
    phase: str
    player_names: list[str]


@router.get("/rooms", response_model=list[dict])
async def list_rooms():
    """Список активных комнат в лобби"""
    rm = get_room_manager()
    return rm.list_rooms()


@router.post("/rooms", response_model=RoomInfo)
async def create_room(req: CreateRoomRequest):
    """Создать новую комнату"""
    if not req.host_name or len(req.host_name.strip()) < 2:
        raise HTTPException(status_code=400, detail="Имя хоста должно быть минимум 2 символа")

    rm = get_room_manager()
    room = await rm.create_room_async(req.host_name.strip())
    await room.initialize()
    return room.to_dict()


@router.get("/rooms/{room_code}", response_model=RoomInfo)
async def get_room(room_code: str):
    """Информация о конкретной комнате"""
    rm = get_room_manager()
    room = rm.get_room(room_code.upper())
    if not room:
        raise HTTPException(status_code=404, detail=f"Комната {room_code} не найдена")
    return room.to_dict()
