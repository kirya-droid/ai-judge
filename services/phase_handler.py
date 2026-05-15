"""Обработчик игровых фаз"""
import asyncio
import random
import logging
from typing import Optional, Callable, Awaitable
from repositories.game_repo import GameRepository
from config.settings import MAX_ROUNDS

logger = logging.getLogger(__name__)


class PhaseHandler:
    """Обработчик игровых фаз"""

    def __init__(self, game_state, ai_service, broadcast_func,
                 repo: GameRepository = None,
                 start_voting_timer_callback: Callable[[], Awaitable[None]] = None):
        self.game_state = game_state
        self.ai_service = ai_service
        self.broadcast = broadcast_func
        self.repo = repo
        self.start_voting_timer_callback = start_voting_timer_callback
    
    async def start_new_round(self):
        """Начало нового раунда"""
        gs = self.game_state
        gs.current_round += 1
        gs.current_phase = "round_start"
        
        # Тянем карту угрозы
        threat = await self._get_random_threat_with_check()
        gs.current_threat_card = threat
        gs.threat_history.append(threat)
        
        # Применяем эффекты к бункеру
        if hasattr(gs, 'current_bunker') and gs.current_bunker and threat:
            self._apply_threat_effects(threat)
        
        # Определяем порядок
        active_players = gs.get_alive_candidates()
        random.shuffle(active_players)
        gs.reveal_order = active_players.copy()
        gs.discussion_order = active_players.copy()
        gs.current_reveal_index = 0
        gs.current_speaker_index = 0
        
        # Уведомления
        await self.broadcast({
            "type": "round_started",
            "round": gs.current_round,
            "threat_card": gs.current_threat_card,
            "bunker": gs.get_bunker_data()
        })
        
        await self.broadcast({
            "type": "threat_card",
            "threat": gs.current_threat_card,
            "round": gs.current_round,
            "bunker": gs.get_bunker_data()
        })
        
        await self.broadcast({
            "type": "system_message",
            "text": f"⚠️ УГРОЗА РАУНДА {gs.current_round}: {threat['name']} - {threat['description']}"
        })
        
        # Начинаем с фазы раскрытия
        gs.current_phase = "reveal_card"
        
        await self.broadcast({
            "type": "phase_changed",
            "phase": gs.current_phase,
            "phase_name": "РАСКРЫТИЕ КАРТ"
        })
        
        # Уведомляем первого игрока
        await self._notify_reveal_turn()
    
    async def _notify_reveal_turn(self):
        """Уведомление игрока о ходе раскрытия"""
        gs = self.game_state
        current_player = gs.get_current_reveal_player()
        
        if current_player:
            await self.broadcast({
                "type": "your_reveal_turn",
                "player_id": current_player.id,
                "player_name": current_player.name
            })
            await self.broadcast({
                "type": "system_message",
                "text": f"📢 {current_player.name} должен раскрыть одну карту!"
            })
    
    async def next_reveal_turn(self):
        """Переход к следующему раскрытию"""
        gs = self.game_state
        next_player = gs.next_reveal_player()
        
        # Если все раскрыли - переходим к обсуждению
        if next_player is None:
            gs.current_phase = "discussion"
            gs.current_speaker_index = 0
            
            await self.broadcast({
                "type": "phase_changed",
                "phase": gs.current_phase,
                "phase_name": "ОБСУЖДЕНИЕ"
            })
            
            # Первый игрок начинает обсуждение
            first_speaker = gs.get_current_speaker()
            if first_speaker:
                await self.broadcast({
                    "type": "next_turn",
                    "player_id": first_speaker.id,
                    "player_name": first_speaker.name
                })
                await self.broadcast({
                    "type": "system_message",
                    "text": f"🎤 {first_speaker.name} начинает обсуждение!"
                })
            return
        
        # Уведомляем следующего
        await self.broadcast({
            "type": "your_reveal_turn",
            "player_id": next_player.id,
            "player_name": next_player.name
        })
        await self.broadcast({
            "type": "system_message",
            "text": f"📢 {next_player.name} должен раскрыть одну карту!"
        })
    
    async def handle_discussion_speech(self, player, speech_text: str):
        """
        Обработка выступления в фазе обсуждения

        Returns:
            bool: True если нужно перейти к следующему игроку, False если игрок продолжает
        """
        gs = self.game_state
        current_speaker = gs.get_current_speaker()
        
        logger.info(f"[DISCUSSION] {player.name} говорит. Текущий говорящий: {current_speaker.name if current_speaker else None}, раунд {gs.current_round}")

        # Проверяем, это ответ на вопрос AI или новое выступление?
        # Игрок может ответить только если сейчас его очередь и AI задал ему вопрос в ЭТОМ раунде
        is_answer_to_ai = False
        
        if current_speaker and current_speaker.id == player.id:
            # Смотрим последние 5 AI thoughts - может быть вопрос к этому игроку в текущем раунде
            for thought in reversed(gs.ai_thoughts[-5:]):
                if (thought.get('player') == player.name and 
                    thought.get('question') and 
                    thought.get('phase') == 'discussion' and
                    thought.get('round') == gs.current_round):
                    # Это вопрос к текущему игроку в текущем раунде
                    is_answer_to_ai = True
                    logger.info(f"[DISCUSSION] {player.name} отвечает на вопрос AI: {thought.get('question')}")
                    break

        if is_answer_to_ai:
            # Игрок ответил на вопрос AI - AI анализирует ответ
            logger.info(f"[DISCUSSION] AI анализирует ответ {player.name}")
            await self.broadcast({"type": "ai_thinking", "text": "🧠 AI анализирует ответ..."})
            await asyncio.sleep(1)
            
            # AI анализирует ответ (без нового вопроса)
            context = gs.get_context_for_ai()
            analysis = await self.ai_service.analyze_speech(
                player, speech_text, gs.current_round, context
            )
            
            ai_thought = {
                "phase": "discussion",
                "round": gs.current_round,
                "player": player.name,
                "thought": f"Ответ на вопрос: {analysis['thought']}" if analysis else "Интересный ответ...",
                "question": None,  # Не задаём второй вопрос
                "ai_name": gs.ai_personality['name'] if gs.ai_personality else "AI"
            }
            gs.ai_thoughts.append(ai_thought)
            
            await self.broadcast({"type": "speech_analyzed", "ai_thought": ai_thought})
            
            await self.broadcast({
                "type": "system_message",
                "text": f"✅ {player.name} ответил на вопрос AI"
            })
            
            # Переходим к следующему
            if gs.is_discussion_complete():
                if gs.current_round == 1:
                    await self.broadcast({
                        "type": "system_message",
                        "text": "РАУНД 1 - ТОЛЬКО ЗНАКОМСТВО! Голосования не будет."
                    })
                    await asyncio.sleep(2)
                    await self.start_new_round()
                else:
                    await self.start_final_word_phase()
            else:
                gs.current_speaker_index += 1
                next_player = gs.get_current_speaker()
                if next_player:
                    await self.broadcast({
                        "type": "next_turn",
                        "player_id": next_player.id,
                        "player_name": next_player.name
                    })
                    await self.broadcast({
                        "type": "system_message",
                        "text": f"🎤 {next_player.name} начинает обсуждение!"
                    })
            return True

        # Это новое выступление - AI анализирует и задаёт вопрос
        logger.info(f"[DISCUSSION] {player.name} - новое выступление, AI анализирует")
        await self.broadcast({"type": "ai_thinking", "text": "🧠 AI анализирует..."})
        await asyncio.sleep(1)

        context = gs.get_context_for_ai()
        analysis = await self.ai_service.analyze_speech(
            player, speech_text, gs.current_round, context
        )

        ai_thought = {
            "phase": "discussion",
            "round": gs.current_round,
            "player": player.name,
            "thought": analysis["thought"] if analysis else "Интересно...",
            "question": analysis["question"] if analysis else "Расскажи подробнее?",
            "ai_name": gs.ai_personality['name'] if gs.ai_personality else "AI"
        }
        gs.ai_thoughts.append(ai_thought)

        await self.broadcast({"type": "speech_analyzed", "ai_thought": ai_thought})

        # НЕ переходим к следующему - даём возможность ответить
        await self.broadcast({
            "type": "system_message",
            "text": f"🤖 AI задал вопрос {player.name}. Ожидается ответ..."
        })

        # Игрок остаётся в очереди чтобы ответить
        return False

    async def start_final_word_phase(self):
        """Начало фазы финального слова"""
        gs = self.game_state
        gs.current_phase = "final_word"
        gs.current_speaker_index = 0
        
        # Сбрасываем порядок - начинаем с первого игрока
        gs.discussion_order = gs.get_alive_candidates().copy()
        random.shuffle(gs.discussion_order)
        gs.current_speaker_index = 0
        
        logger.info(f"[FINAL_WORD] Начинаем финальное слово. Порядок: {[p.name for p in gs.discussion_order]}")

        await self.broadcast({
            "type": "phase_changed",
            "phase": gs.current_phase,
            "phase_name": "ФИНАЛЬНОЕ СЛОВО"
        })

        await self.broadcast({
            "type": "system_message",
            "text": "🎤 ФИНАЛЬНОЕ СЛОВО - каждый игрок говорит зачем его оставить в бункере!"
        })

        first_speaker = gs.get_current_speaker()
        if first_speaker:
            logger.info(f"[FINAL_WORD] Первый говорящий: {first_speaker.name}")
            await self.broadcast({
                "type": "next_turn",
                "player_id": first_speaker.id,
                "player_name": first_speaker.name
            })
            await self.broadcast({
                "type": "system_message",
                "text": f"🎤 {first_speaker.name} начинает финальное слово!"
            })
        else:
            logger.error("[FINAL_WORD] Нет игроков для финального слова!")
            logger.error(f"[FINAL_WORD] discussion_order: {gs.discussion_order}")
            logger.error(f"[FINAL_WORD] alive_candidates: {gs.get_alive_candidates()}")
    
    async def start_actual_voting(self):
        """Начало голосования"""
        gs = self.game_state
        gs.current_phase = "voting"

        await self.broadcast({
            "type": "phase_changed",
            "phase": gs.current_phase,
            "phase_name": "ГОЛОСОВАНИЕ"
        })

        await self.broadcast({
            "type": "system_message",
            "text": "🗳️ ГОЛОСОВАНИЕ - выберите кого исключить!"
        })
        
        # Запускаем таймер голосования на 30 секунд
        await self.broadcast({
            "type": "voting_timer_started",
            "duration": 30
        })
        
        # Запускаем таймер на сервере через callback (без циклического импорта)
        if self.start_voting_timer_callback:
            await self.start_voting_timer_callback()

        # AI рекомендация будет после голосования
    
    async def process_voting(self):
        """Обработка результатов голосования"""
        gs = self.game_state
        active_players = gs.get_alive_candidates()

        logger.info(f"[VOTING] Начинаем обработку. Активные игроки: {[p.name for p in active_players]}")

        # Подсчёт голосов
        vote_counts = {}
        for player in active_players:
            if player.vote:
                vote_counts[player.vote] = vote_counts.get(player.vote, 0) + 1

        logger.info(f"[VOTING] Голоса: {vote_counts}")

        # Определение кандидата по голосам игроков
        players_choice = None
        if vote_counts:
            max_votes = max(vote_counts.values())
            candidates = [pid for pid, votes in vote_counts.items() if votes == max_votes]
            eliminated_id = random.choice(candidates)
            players_choice = gs.players[eliminated_id]
            logger.info(f"[VOTING] Игроки выбрали: {players_choice.name} ({max_votes} голосов)")
        elif active_players:
            players_choice = random.choice(active_players)
            logger.info(f"[VOTING] Нет голосов - выбираем случайно: {players_choice.name}")

        # AI финальное решение
        ai_decision = None
        if self.ai_service.available and players_choice:
            context = gs.get_context_for_ai()
            ai_decision = await self.ai_service.make_final_decision(
                active_players, vote_counts, gs.current_round, context
            )

            if ai_decision:
                logger.info(f"[VOTING] AI решение: {ai_decision}")
                # AI может переписать решение — точное сравнение имён
                ai_chosen_name = ai_decision.get("decision", "").strip()
                for p in active_players:
                    if ai_chosen_name.lower() == p.name.lower():
                        players_choice = p
                        logger.info(f"[VOTING] AI изменил решение на: {players_choice.name}")
                        break

                await self.broadcast({
                    "type": "ai_final_decision",
                    "decision": ai_decision
                })
            else:
                logger.warning("[VOTING] AI не вернул решение")
        else:
            logger.info(f"[VOTING] AI недоступен или нет игроков для решения")

        # Guard: если некого исключать — выходим
        if players_choice is None:
            logger.error("[VOTING] Некого исключать — нет активных игроков")
            await self.check_game_end()
            return

        # Игрок выбывает
        players_choice.eliminated = True
        gs.players_eliminated.append(players_choice)

        logger.info(f"[VOTING] Выбывает: {players_choice.name}")

        # Сброс голосов
        for p in gs.players.values():
            p.vote = None

        # Переход к фазе раскрытия
        gs.current_phase = "reveal"

        players_choice.character.can_reveal_options = players_choice.character.get_reveal_options()

        await self.broadcast({
            "type": "voting_completed",
            "eliminated": players_choice.name,
            "phase": gs.current_phase
        })

        # Предлагаем раскрыть карту
        if players_choice.character.can_reveal_options:
            if players_choice.websocket:
                try:
                    await players_choice.websocket.send_json({
                        "type": "choose_reveal",
                        "options": players_choice.character.can_reveal_options
                    })
                except Exception as e:
                    logger.warning(f"[REVEAL] Ошибка отправки choose_reveal: {e}")

            await self.broadcast({
                "type": "system_message",
                "text": f"📢 {players_choice.name} выбыл! Раскрой одну карту за 30 сек или она будет выбрана случайно."
            })

            # Ждём 30 секунд на раскрытие карты
            await asyncio.sleep(30)

            # Проверяем не раскрыл ли уже игрок карту (фаза могла измениться)
            if gs.current_phase == "reveal":
                logger.info(f"[REVEAL_TIMEOUT] {players_choice.name} не раскрыл карту за 30 сек")
                await self.broadcast({
                    "type": "system_message",
                    "text": f"🔇 {players_choice.name} не раскрыл карту (время вышло)"
                })
                await self.check_game_end()
        else:
            logger.info(f"[REVEAL] У {players_choice.name} нет карт для раскрытия")
            await self.check_game_end()
    
    async def check_game_end(self):
        """Проверка окончания игры"""
        gs = self.game_state
        in_bunker_count = len(gs.players_in_bunker)
        active_players = gs.get_alive_candidates()

        # ПРОВЕРКА 1: Если места заполнены - игра окончена
        if in_bunker_count >= gs.bunker_spots:
            await self.finish_game()
            return

        # ПРОВЕРКА 2: Если остался 1 игрок - он победил (независимо от мест)
        if len(active_players) == 1:
            logger.info(f"🏆 Остался 1 игрок: {active_players[0].name} - ПОБЕДА!")
            active_players[0].in_bunker = True
            gs.players_in_bunker.append(active_players[0])
            await self.finish_game()
            return

        # ПРОВЕРКА 3: Если игроков <= мест - все проходят
        spots_left = gs.bunker_spots - in_bunker_count
        if len(active_players) <= spots_left:
            logger.info(f"🏆 Игроков ({len(active_players)}) <= мест ({spots_left}) - все проходят!")
            for player in active_players:
                player.in_bunker = True
                gs.players_in_bunker.append(player)
            await self.finish_game()
            return

        # ПРОВЕРКА 4: Продолжаем игру если есть раунды
        if gs.current_round < gs.max_rounds:
            await self.start_new_round()
        else:
            await self.finish_game()
    
    async def finish_game(self):
        """Завершение игры"""
        gs = self.game_state
        gs.current_phase = "results"
        
        verdict_text = "🏆 РЕЗУЛЬТАТЫ ИГРЫ 🏆\n\n"
        verdict_text += f"🚪 МЕСТ В БУНКЕРЕ: {gs.bunker_spots}/{gs.bunker_capacity}\n\n"
        
        if gs.current_catastrophe:
            verdict_text += f"🌍 КАТАСТРОФА: {gs.current_catastrophe['name']}\n"
            verdict_text += f"{gs.current_catastrophe['description']}\n\n"
        
        if hasattr(gs, 'current_bunker') and gs.current_bunker:
            verdict_text += f"🏭 БУНКЕР: {gs.current_bunker.get('name')}\n"
            verdict_text += f"   Еда: {gs.current_bunker.get('food_supply', 0)}%\n"
            verdict_text += f"   Вода: {gs.current_bunker.get('water_supply', 0)}%\n"
            verdict_text += f"   Лекарства: {gs.current_bunker.get('medicine_supply', 0)}%\n"
            verdict_text += f"   Мораль: {gs.current_bunker.get('morale_level', 0)}%\n\n"
        
        verdict_text += "✅ ВЫЖИВШИЕ В БУНКЕРЕ:\n"
        for p in gs.players_in_bunker:
            verdict_text += f"  • {p.name}"
            if p.character.profession_revealed:
                verdict_text += f" - {p.character.profession}"
            if p.character.condition_revealed and p.character.condition:
                verdict_text += f" ({p.character.condition['name']})"
            verdict_text += "\n"
        
        verdict_text += "\n❌ ПОГИБШИЕ:\n"
        for p in gs.players_eliminated:
            verdict_text += f"  • {p.name}"
            if p.character.profession_revealed:
                verdict_text += f" - {p.character.profession}"
            verdict_text += f"\n    Секрет: {p.character.secret['secret']}\n"
        
        survivors_list = [
            {"name": p.name, "profession": p.character.profession if p.character.profession_revealed else "???"}
            for p in gs.players_in_bunker
        ]
        eliminated_list = [
            {"name": p.name, "secret": p.character.secret.get('secret')}
            for p in gs.players_eliminated
        ]
        
        await self.broadcast({
            "type": "game_finished",
            "verdict": {
                "message": verdict_text,
                "survivors": survivors_list,
                "eliminated": eliminated_list
            }
        })
    
    def _apply_threat_effects(self, threat: dict):
        """Применение эффектов угрозы к бункеру"""
        gs = self.game_state
        if not hasattr(gs, 'current_bunker') or not gs.current_bunker:
            return
        
        effects = threat.get("effects", {})
        for resource, change in effects.items():
            if resource in gs.current_bunker:
                gs.current_bunker[resource] = max(0, gs.current_bunker.get(resource, 100) + change)
        
        logger.info(f"⚠️ Применена угроза {threat['name']}, ресурсы: {gs.current_bunker}")
    
    async def _get_random_threat_with_check(self) -> dict:
        """Получение случайной угрозы с проверкой повторов"""
        if not self.repo:
            return self._default_threat()

        all_threats = await self.repo.get_all_events()
        used_names = {t.get('name') for t in self.game_state.threat_history}
        available = [t for t in all_threats if t.get('event_name') not in used_names]

        if available:
            threat = random.choice(available)
        elif all_threats:
            threat = random.choice(all_threats)
        else:
            return self._default_threat()

        return self._format_threat(threat)

    def _format_threat(self, threat: dict) -> dict:
        """Форматирование угрозы"""
        return {
            "name": threat.get('event_name', 'Неизвестная угроза'),
            "description": threat.get('event_description', ''),
            "effects": {
                "food_supply": threat.get('food_effect', 0),
                "water_supply": threat.get('water_effect', 0),
                "medicine_supply": threat.get('medicine_effect', 0),
                "fuel_supply": threat.get('fuel_effect', 0),
                "ammo_supply": threat.get('ammo_effect', 0),
                "materials_supply": threat.get('materials_effect', 0),
                "defense_level": threat.get('defense_effect', 0),
                "morale_level": threat.get('morale_effect', 0)
            },
            "is_positive": threat.get('is_positive', False)
        }

    def _default_threat(self) -> dict:
        """Дефолтная угроза"""
        return {
            "name": "Нехватка ресурсов",
            "description": "Запасы еды и воды заканчиваются быстрее, чем ожидалось.",
            "effects": {
                "food_supply": -15,
                "water_supply": -15,
                "medicine_supply": -5,
                "morale_level": -5
            },
            "is_positive": False
        }
