"""WebSocket роутер для обработки подключений игроков"""
import json
import asyncio
import random
import logging
import copy
from datetime import datetime
from typing import Optional
from fastapi import WebSocket, WebSocketDisconnect
from models.player import Player
from services.ai_service import AIService
from services.game_state import GameState
from services.phase_handler import PhaseHandler
from services.room_manager import get_room_manager, GameRoom
from repositories.game_repo import GameRepository

logger = logging.getLogger(__name__)


async def _verify_turn(player: Player, current_player: Optional[Player]) -> bool:
    """Проверка, чей сейчас ход"""
    if current_player and current_player.id != player.id:
        await player.websocket.send_json({
            "type": "system_message",
            "text": "⏳ Сейчас не ваша очередь!"
        })
        return False
    return True


async def handle_websocket(websocket: WebSocket, room_code: str, player_name: str):
    """Обработка WebSocket подключения к конкретной комнате"""
    rm = get_room_manager()
    room = rm.get_room(room_code.upper())

    if not room:
        await websocket.close(code=4004, reason="Комната не найдена")
        return

    gs = room.game_state

    logger.info(f"[WS] Подключение к {room.code}: {player_name}")

    try:
        await websocket.accept()
        logger.info(f"[WS] WebSocket принят: {player_name} в комнате {room.code}")
    except Exception as e:
        logger.error(f"[WS] Ошибка при принятии WebSocket: {e}")
        return

    # Проверяем что комната не заполнена
    if room.is_full() and player_name not in [p.name for p in gs.players.values()]:
        await websocket.send_json({
            "type": "system_message",
            "text": "⚠️ Комната заполнена"
        })
        await websocket.close()
        return

    # Генерируем ID
    player_id = f"player_{len(gs.players) + 1}_{random.randint(1000, 9999)}"

    # Проверяем существующего игрока с таким именем
    existing = None
    for pid, p in gs.players.items():
        if p.name == player_name:
            existing = pid
            break

    if existing:
        logger.info(f"[WS] Игрок {player_name} уже подключен, переподключение")
        old_player = gs.players[existing]
        if old_player.websocket:
            try:
                await old_player.websocket.close()
            except Exception:
                pass
        del gs.players[existing]

    try:
        player = Player(player_id, player_name)
        player.websocket = websocket
        gs.add_player(player)
        await player.initialize(room.repo)
        logger.info(f"[WS] Игрок создан: {player_name} (ID: {player_id}) в комнате {room.code}")
    except Exception as e:
        logger.error(f"[WS] Ошибка при создании игрока: {e}", exc_info=True)
        try:
            await websocket.close()
        except Exception:
            pass
        return

    # Отменяем удаление комнаты если было
    rm.cancel_cleanup(room.code)

    # Отправляем начальное состояние
    try:
        game_state_data = gs.get_game_state(player_name)
        await websocket.send_json({"type": "game_state", "game": game_state_data})

        await room.broadcast({
            "type": "player_joined",
            "player_id": player.id,
            "player_name": player.name
        })
        logger.info(f"[WS] Игрок {player_name} успешно подключен к {room.code}")
    except Exception as e:
        logger.error(f"[WS] Ошибка при отправке начальных сообщений: {e}", exc_info=True)
        try:
            await websocket.close()
        except Exception:
            pass
        return

    # Основной цикл обработки сообщений
    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=300.0)
                message = json.loads(data)
                await handle_message(room, player, message)

            except asyncio.TimeoutError:
                try:
                    await websocket.send_json({"type": "pong"})
                except Exception:
                    break
            except json.JSONDecodeError:
                logger.warning(f"[WS] Неверный JSON от {player_name}")
                continue
            except Exception as e:
                msg = str(e)
                if "Cannot call \"receive\" once a disconnect message has been received" in msg:
                    logger.info(f"[WS] Дисконнект для {player_name}")
                    break
                if "WebSocket is not connected" in msg or "need to call" in msg.lower():
                    logger.info(f"[WS] WebSocket не подключён для {player_name}")
                    break
                logger.error(f"[WS] Ошибка: {e}")
                continue

    except WebSocketDisconnect:
        logger.info(f"[WS] Игрок {player_name} отключился из {room.code}")
    except Exception as e:
        logger.error(f"[WS] Критическая ошибка для {player_name}: {e}", exc_info=True)
    finally:
        if player_id and player_id in gs.players:
            gs.remove_player(player_id)
            await room.broadcast({"type": "player_left", "player_id": player_id})
            await room.broadcast({
                "type": "system_message",
                "text": f"📡 {player_name} покинул игру"
            })

        # Если комната пуста — запланировать удаление
        if room.is_empty():
            rm.schedule_cleanup(room.code)


async def handle_message(room: GameRoom, player: Player, message: dict):
    """Обработка отдельного сообщения от игрока"""
    gs = room.game_state
    msg_type = message.get("type")

    if msg_type == "ready":
        logger.info(f"[READY] Игрок {player.name} нажал готов")
        await handle_ready(room, player)

    elif msg_type == "reveal_card" and gs.current_phase == "reveal_card":
        await handle_reveal_card(room, player, message)

    elif msg_type == "speech" and gs.current_phase in ["discussion", "final_word"]:
        await handle_speech(room, player, message)

    elif msg_type == "vote" and gs.current_phase == "voting":
        await handle_vote(room, player, message)

    elif msg_type == "question" and gs.current_phase == "discussion":
        await handle_player_question(room, player, message)

    elif msg_type == "choose_reveal" and gs.current_phase == "reveal":
        await handle_choose_reveal(room, player, message)

    elif msg_type == "skip_reveal" and gs.current_phase == "reveal":
        logger.info(f"[REVEAL] {player.name} пропустил раскрытие")
        await room.broadcast({
            "type": "system_message",
            "text": f"🔇 {player.name} ничего не раскрыл."
        })
        await room.phase_handler.check_game_end()

    elif msg_type == "ping":
        await player.websocket.send_json({"type": "pong"})

    elif msg_type == "typing_start":
        await room.broadcast({
            "type": "player_typing",
            "player_id": player.id,
            "player_name": player.name
        }, exclude_viewer=player.name)

    elif msg_type == "typing_stop":
        await room.broadcast({
            "type": "player_stop_typing",
            "player_id": player.id,
            "player_name": player.name
        }, exclude_viewer=player.name)

    elif msg_type == "recording_start":
        await room.broadcast({
            "type": "player_recording",
            "player_id": player.id,
            "player_name": player.name
        }, exclude_viewer=player.name)

    elif msg_type == "recording_stop":
        await room.broadcast({
            "type": "player_stop_recording",
            "player_id": player.id,
            "player_name": player.name
        }, exclude_viewer=player.name)

    elif msg_type == "reset_game":
        if gs.current_phase != "lobby":
            await player.websocket.send_json({
                "type": "system_message",
                "text": "⚠️ Сброс игры возможен только в лобби"
            })
            return
        logger.info(f"[GAME] Игрок {player.name} запросил сброс игры")
        gs.soft_reset()
        await room.broadcast({"type": "system_message", "text": "🔁 Игра сброшена"})


async def handle_ready(room: GameRoom, player: Player):
    """Обработка готовности игрока"""
    player.ready = not player.ready
    gs = room.game_state

    await room.broadcast({
        "type": "player_ready",
        "player_id": player.id,
        "player_name": player.name,
        "ready": player.ready
    })

    active_players = gs.get_active_players()
    all_ready = all(p.ready for p in active_players) and len(active_players) >= 2

    if all_ready and not gs.game_started and gs.current_phase == "lobby":
        logger.info("[GAME] Все игроки готовы, начинаем игру")
        await start_game(room)


async def start_game(room: GameRoom):
    """Начало игры"""
    gs = room.game_state
    repo = room.repo

    gs.game_started = True
    gs.current_round = 0

    # 1. Тянем карту бункера
    gs.current_bunker = await repo.get_random_bunker()
    logger.info(f"[GAME] Получен бункер: {gs.current_bunker}")

    gs.bunker_capacity = gs.current_bunker.get('max_capacity', 20)
    gs.bunker_spots = gs.bunker_capacity // 2

    for resource in ['food_supply', 'water_supply', 'medicine_supply', 'morale_level']:
        if resource not in gs.current_bunker:
            gs.current_bunker[resource] = 100 if resource in ['food_supply', 'water_supply'] else 80

    gs.current_bunker_card = {
        "name": gs.current_bunker.get('name'),
        "max_capacity": gs.bunker_capacity,
        "food_supply": gs.current_bunker.get('food_supply'),
        "water_supply": gs.current_bunker.get('water_supply'),
        "medicine_supply": gs.current_bunker.get('medicine_supply'),
        "morale_level": gs.current_bunker.get('morale_level'),
        "special_features": gs.current_bunker.get('special_features', '')
    }

    # 2. Тянем карту катастрофы из БД
    gs.current_catastrophe = await repo.get_random_catastrophe()

    await room.broadcast({"type": "game_started"})
    await room.broadcast({"type": "bunker_card", "bunker": gs.current_bunker_card})
    await room.broadcast({"type": "catastrophe_card", "catastrophe": gs.current_catastrophe})

    await room.broadcast({
        "type": "system_message",
        "text": f"🌍 КАТАСТРОФА: {gs.current_catastrophe['name']}"
    })
    await room.broadcast({
        "type": "system_message",
        "text": f"🏭 БУНКЕР: {gs.current_bunker_card['name']}. Мест: {gs.bunker_spots}/{gs.bunker_capacity}"
    })

    await room.phase_handler.start_new_round()


async def handle_reveal_card(room: GameRoom, player: Player, message: dict):
    """Обработка раскрытия карты"""
    gs = room.game_state

    current_reveal_player = gs.get_current_reveal_player()
    if not await _verify_turn(player, current_reveal_player):
        return

    option_type = message.get("option")
    if not option_type:
        await player.websocket.send_json({
            "type": "system_message",
            "text": "⚠️ Выберите карту для раскрытия"
        })
        return

    reveal_result = player.character.reveal_option(option_type)
    if not reveal_result:
        await player.websocket.send_json({
            "type": "system_message",
            "text": "⚠️ Ошибка раскрытия карты"
        })
        return

    logger.info(f"[REVEAL] {player.name} раскрыл {reveal_result['type']}: {reveal_result.get('value', '')}")

    # Сохраняем через репозиторий
    await room.repo.save_reveal_card(
        player.id,
        reveal_result["type"],
        json.dumps(reveal_result["value"], ensure_ascii=False),
        gs.current_round,
        datetime.utcnow().isoformat()
    )

    await room.broadcast({
        "type": "reveal",
        "player_name": player.name,
        "reveal_data": reveal_result,
        "round": gs.current_round
    })
    await room.broadcast({"type": "game_state_update"})
    await room.phase_handler.next_reveal_turn()


async def handle_speech(room: GameRoom, player: Player, message: dict):
    """Обработка речи игрока"""
    gs = room.game_state

    speech_text = message.get("text", "").strip()
    if len(speech_text) < 5:
        await player.websocket.send_json({
            "type": "system_message",
            "text": "⚠️ Слишком коротко"
        })
        return

    current_speaker = gs.get_current_speaker()
    if not await _verify_turn(player, current_speaker):
        return

    logger.info(f"[SPEECH] {player.name} говорит в фазе {gs.current_phase}")

    if gs.current_phase == "final_word":
        await handle_final_word_speech(room, player, speech_text)
    elif gs.current_phase == "discussion":
        await room.broadcast({
            "type": "speech",
            "player": player.to_dict(player.name),
            "text": speech_text,
            "round": gs.current_round
        })
        await room.phase_handler.handle_discussion_speech(player, speech_text)


async def handle_final_word_speech(room: GameRoom, player: Player, speech_text: str):
    """Обработка речи в фазе финального слова"""
    gs = room.game_state
    current_speaker = gs.get_current_speaker()

    logger.info(f"[FINAL_WORD] {player.name} говорит. Текущий: {current_speaker.name if current_speaker else None}")

    if not await _verify_turn(player, current_speaker):
        logger.warning(f"[FINAL_WORD] {player.name} говорит не в свою очередь!")
        return

    await room.broadcast({
        "type": "speech",
        "player": player.to_dict(player.name),
        "text": speech_text,
        "round": gs.current_round
    })

    logger.info(f"[FINAL_WORD] AI анализирует речь {player.name}")
    await room.broadcast({"type": "ai_thinking", "text": "🧠 AI анализирует..."})
    await asyncio.sleep(1)

    context = gs.get_context_for_ai()
    analysis = await room.phase_handler.ai_service.analyze_speech(
        player, speech_text, gs.current_round, context
    )

    ai_thought = {
        "phase": "final_word",
        "round": gs.current_round,
        "player": player.name,
        "thought": f"Финальное слово: {analysis['thought']}" if analysis else "Интересно...",
        "question": None,
        "ai_name": gs.ai_personality['name'] if gs.ai_personality else "AI"
    }
    gs.ai_thoughts.append(ai_thought)

    await room.broadcast({"type": "speech_analyzed", "ai_thought": ai_thought})

    if gs.is_discussion_complete():
        logger.info("[FINAL_WORD] Все сказали - начинаем голосование")
        await room.phase_handler.start_actual_voting()
    else:
        gs.current_speaker_index += 1
        next_player = gs.get_current_speaker()
        if next_player:
            await room.broadcast({
                "type": "next_turn",
                "player_id": next_player.id,
                "player_name": next_player.name
            })
            await room.broadcast({
                "type": "system_message",
                "text": f"🎤 {next_player.name} говорит финальное слово!"
            })


async def start_voting_timer(room: GameRoom):
    """Запуск таймера голосования"""
    logger.info(f"[VOTE_TIMER] Попытка запуска. active={room.voting_timer_active}")
    if not room.voting_timer_active:
        room.voting_timer_active = True
        room.voting_timer = asyncio.create_task(_voting_timeout(room))
        logger.info("[VOTE_TIMER] Таймер запущен (30 сек)")
    else:
        logger.info("[VOTE_TIMER] Таймер уже запущен, пропускаем")


async def handle_vote(room: GameRoom, player: Player, message: dict):
    """Обработка голоса"""
    gs = room.game_state

    logger.debug(f"[VOTE] Игрок: {player.name}, фаза: {gs.current_phase}")

    target_id = message.get("target_id")
    if target_id and target_id in gs.players:
        target_player = gs.players[target_id]

        if (not target_player.eliminated and
            not target_player.in_bunker and
            target_player.id != player.id):

            player.vote = target_id
            logger.info(f"[VOTE] {player.name} голосует за {target_player.name}")

            await room.broadcast({
                "type": "vote_cast",
                "player_id": player.id,
                "player_name": player.name,
                "target_id": target_id
            })

            active_players = gs.get_alive_candidates()
            all_voted = all(p.vote is not None for p in active_players)

            logger.debug(f"[VOTE] Проголосовало: {sum(1 for p in active_players if p.vote is not None)}/{len(active_players)}")

            if all_voted:
                logger.info("[VOTE] Все проголосовали - начинаем обработку")
                if room.voting_timer:
                    room.voting_timer.cancel()
                    room.voting_timer = None
                room.voting_timer_active = False
                await room.phase_handler.process_voting()
            else:
                logger.debug(f"[VOTE] Ждём ещё голосов...")


async def _voting_timeout(room: GameRoom):
    """Таймер голосования — 30 секунд"""
    gs = room.game_state

    logger.info(f"[VOTE_TIMEOUT] Таймер начался")

    for remaining in range(30, 0, -1):
        await asyncio.sleep(1)
        if not room.voting_timer_active:
            logger.info(f"[VOTE_TIMEOUT] Таймер отменён на {remaining} сек")
            return
        await room.broadcast({
            "type": "voting_timer_update",
            "remaining": remaining
        })

    logger.info("[VOTE_TIMEOUT] Время вышло")

    active_players = gs.get_alive_candidates()
    all_voted = all(p.vote is not None for p in active_players)

    if not all_voted:
        logger.info("[VOTE_TIMEOUT] AI голосует за тех кто не проголосовал")
        for p in active_players:
            if p.vote is None:
                candidates = [ap for ap in active_players if ap.id != p.id]
                if candidates:
                    p.vote = random.choice(candidates).id

    room.voting_timer_active = False
    room.voting_timer = None

    await room.phase_handler.process_voting()


async def handle_player_question(room: GameRoom, player: Player, message: dict):
    """Обработка вопроса игрока другому игроку"""
    gs = room.game_state
    target_id = message.get("target_id")
    question_text = message.get("text", "").strip()

    if target_id and target_id in gs.players and question_text:
        target_player = gs.players[target_id]
        if not target_player.eliminated and not target_player.in_bunker:
            logger.info(f"[QUESTION] {player.name} спрашивает {target_player.name}: {question_text[:50]}")
            await room.broadcast({
                "type": "question",
                "from_player": player.name,
                "to_player": target_player.name,
                "text": question_text
            })


async def handle_choose_reveal(room: GameRoom, player: Player, message: dict):
    """Обработка раскрытия карты выбывшим игроком"""
    gs = room.game_state

    if not player.eliminated:
        return

    # Не раскрываем если игра уже закончена
    if gs.current_phase == "results":
        return

    option_type = message.get("option")
    if option_type:
        reveal_result = player.character.reveal_option(option_type)

        if reveal_result:
            logger.info(f"[REVEAL] {player.name} (выбывший) раскрыл {reveal_result['type']}")
            await room.repo.save_reveal_card(
                player.id,
                reveal_result["type"],
                json.dumps(reveal_result["value"], ensure_ascii=False),
                gs.current_round,
                datetime.utcnow().isoformat()
            )

            await room.broadcast({
                "type": "reveal",
                "player_name": player.name,
                "reveal_data": reveal_result
            })

    await room.phase_handler.check_game_end()
