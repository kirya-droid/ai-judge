"""Сервис для работы с AI (DeepSeek)"""
import json
import logging
import random
import openai
from config.settings import DEEPSEEK_API_KEY, AI_AVAILABLE

logger = logging.getLogger(__name__)

# Настройка AI
if DEEPSEEK_API_KEY:
    openai.api_key = DEEPSEEK_API_KEY
    openai.api_base = "https://api.deepseek.com/v1"


class AIService:
    """Сервис для взаимодействия с AI"""

    def __init__(self):
        self.available = AI_AVAILABLE
        self.personality = None

    def set_personality(self, personality: dict):
        """Установить личность AI"""
        self.personality = personality
        logger.info(f"[AI] Личность установлена: {personality.get('name', 'Неизвестно')}")

    def _get_personality_prompt(self) -> str:
        """Добавить инструкцию личности в промпт"""
        if not self.personality or not self.personality.get('prompt'):
            return ""
        return f"\n\nТВОЯ ЛИЧНОСТЬ: {self.personality['prompt']}"

    async def analyze_speech(self, player, speech_text: str, round_num: int,
                             context: dict = None) -> dict:
        """
        Анализ выступления игрока

        Args:
            player: Игрок чье выступление анализируем
            speech_text: Текст выступления
            round_num: Номер раунда
            context: Контекст (ситуация в бункере, текущая угроза)

        Returns:
            dict с полями thought и question
        """
        if not speech_text or len(speech_text.strip()) < 5:
            return {"thought": "Слишком короткое выступление",
                    "question": "Что еще можешь сказать?"}

        # Собираем ВСЮ раскрытую информацию
        revealed_info = []
        
        if player.character.profession_revealed:
            revealed_info.append(f"• Профессия: {player.character.profession} ({player.character.profession_desc})")

        if player.character.dossier_revealed:
            revealed_info.append(f"• Возраст: {player.character.age} лет")
            revealed_info.append(f"• Пол: {player.character.gender}")
            if player.character.orientation:
                revealed_info.append(f"• Ориентация: {player.character.orientation}")
        
        if player.character.condition_revealed and player.character.condition:
            revealed_info.append(f"• Здоровье: {player.character.condition['name']} - {player.character.condition.get('description', '')}")
            
        # Раскрытые черты характера
        if player.character.traits_revealed:
            for trait_ref in player.character.traits_revealed:
                if trait_ref.startswith("positive_"):
                    idx = int(trait_ref.split("_")[1])
                    if idx < len(player.character.positive_traits):
                        trait = player.character.positive_traits[idx]
                        desc = player.character.positive_traits_details[idx] if idx < len(player.character.positive_traits_details) else ""
                        revealed_info.append(f"• Положительная черта: {trait} ({desc})")
                elif trait_ref.startswith("negative_"):
                    idx = int(trait_ref.split("_")[1])
                    if idx < len(player.character.negative_traits):
                        trait = player.character.negative_traits[idx]
                        desc = player.character.negative_traits_details[idx] if idx < len(player.character.negative_traits_details) else ""
                        revealed_info.append(f"• Отрицательная черта: {trait} ({desc})")
                        
        if player.character.luggage_revealed and player.character.luggage:
            revealed_info.append(f"• Багаж: {player.character.luggage.get('name', '')} - {player.character.luggage.get('description', '')}")
            
        if player.character.secret_revealed and player.character.secret:
            revealed_info.append(f"• Секрет: {player.character.secret.get('secret', '')}")

        revealed_str = "\n".join(revealed_info) if revealed_info else "Ничего не раскрыто"

        # Формируем контекст
        context_str = self._format_context(context)

        prompt = f"""Ты AI-судья в бункере. Раунд {round_num}.

Контекст игры:
{context_str}

Игрок: {player.name}
Раскрытая информация о игроке:
{revealed_str}

Выступление игрока (записано с микрофона, поэтому может быть без знаков препинания и с оговорками - это НОРМАЛЬНО, не критикуй за это):
"{speech_text}"

ВАЖНО:
1. Речь записана с микрофона - отсутствие запятых и пунктуации НЕ является недостатком
2. Оценивай СОДЕРЖАНИЕ речи, а не форму подачи
3. Учитывай ВСЮ раскрытую информацию: профессию, черты характера, возраст, здоровье, багаж, секреты
4. Не зацикливайся только на профессии - рассматривай все навыки и качества игрока
5. Если игрок упоминает параметры бункера (ресурсы, вместимость, особенности) или катастрофу - учитывай это в оценке
6. Дай полезную оценку и задай вопрос который поможет раскрыть игрока с новой стороны

Ответь в формате JSON: {{"thought": "твоя мысль об игроке (2-3 предложения)", "question": "уточняющий вопрос по раскрытой информации или выступлению"}}{self._get_personality_prompt()}"""

        return await self._call_ai(prompt)

    async def analyze_reveal(self, player, reveal_data: dict, round_num: int,
                            context: dict = None) -> dict:
        """
        Анализ раскрытой карты игрока
        
        Args:
            player: Игрок который раскрыл карту
            reveal_data: Данные раскрытой карты
            round_num: Номер раунда
            context: Контекст ситуации
        
        Returns:
            dict с полями thought и question или None если AI недоступен
        """
        if not self.available:
            return None

        reveal_type = reveal_data.get('type', '')
        reveal_value = reveal_data.get('value', '')
        context_str = self._format_context(context)

        prompt = f"""Ты AI-судья в бункере. Раунд {round_num}. {context_str}
Игрок: {player.name}
Игрок раскрыл: {reveal_type} = {reveal_value}

Задай 1 интересный вопрос по этой информации.
Ответь в формате JSON: {{"thought": "реакция", "question": "вопрос"}}{self._get_personality_prompt()}"""

        return await self._call_ai(prompt)

    async def get_vote_recommendation(self, candidates: list, spots_left: int,
                                      context: dict = None) -> dict:
        """
        Рекомендация AI по голосованию

        Args:
            candidates: Список кандидатов на исключение
            spots_left: Количество оставшихся мест

        Returns:
            dict с полями recommendation и reasoning
        """
        if not self.available or not candidates:
            return None

        context_str = self._format_context(context)

        candidates_info = []
        for p in candidates:
            revealed = []
            
            # Профессия с описанием
            if p.character.profession_revealed:
                revealed.append(f"профессия: {p.character.profession} ({p.character.profession_desc})")

            # Возраст и пол
            if p.character.dossier_revealed:
                revealed.append(f"возраст: {p.character.age} лет")
                revealed.append(f"пол: {p.character.gender}")
                if p.character.orientation:
                    revealed.append(f"ориентация: {p.character.orientation}")
                
            # Здоровье
            if p.character.condition_revealed and p.character.condition:
                revealed.append(f"здоровье: {p.character.condition['name']} - {p.character.condition.get('description', '')}")
            
            # Черты характера
            for trait_ref in p.character.traits_revealed:
                if trait_ref.startswith("positive_"):
                    idx = int(trait_ref.split("_")[1])
                    if idx < len(p.character.positive_traits):
                        trait = p.character.positive_traits[idx]
                        desc = p.character.positive_traits_details[idx] if idx < len(p.character.positive_traits_details) else ""
                        revealed.append(f"черта: +{trait} ({desc})")
                elif trait_ref.startswith("negative_"):
                    idx = int(trait_ref.split("_")[1])
                    if idx < len(p.character.negative_traits):
                        trait = p.character.negative_traits[idx]
                        desc = p.character.negative_traits_details[idx] if idx < len(p.character.negative_traits_details) else ""
                        revealed.append(f"черта: -{trait} ({desc})")
            
            # Багаж
            if p.character.luggage_revealed and p.character.luggage:
                revealed.append(f"багаж: {p.character.luggage.get('name', '')} - {p.character.luggage.get('description', '')}")
            
            # Секрет
            if p.character.secret_revealed and p.character.secret:
                revealed.append(f"секрет: {p.character.secret.get('secret', '')}")

            info = f"- {p.name}"
            if revealed:
                info += f" ({'; '.join(revealed)})"
            else:
                info += " (нет раскрытой информации)"
            candidates_info.append(info)

        prompt = f"""Ты AI-советник в бункере.

Контекст игры:
{context_str}

Осталось мест: {spots_left}

Кандидаты на исключение (учитывай ВСЮ раскрытую информацию - профессии, черты, навыки, предметы, здоровье):
{chr(10).join(candidates_info)}

Кого стоит исключить и почему? 
ВАЖНО:
1. Не зацикливайся только на профессии
2. Рассматривай все раскрытые навыки, черты характера, предметы
3. Оценивай полезность игрока для выживания группы
4. Учитывай как положительные так и отрицательные качества
5. Учитывай параметры бункера (ресурсы, особенности) - кто лучше подойдёт
6. Учитывай катастрофу - какие навыки полезнее для выживания

Ответь в формате JSON: {{"recommendation": "имя", "reasoning": "подробное объяснение с учётом всех раскрытых данных и контекста бункера"}}{self._get_personality_prompt()}"""

        return await self._call_ai(prompt)

    async def make_final_decision(self, candidates: list, vote_counts: dict,
                                  round_num: int, context: dict = None) -> dict:
        """
        Финальное решение AI об исключении

        Args:
            candidates: Кандидаты на исключение (объекты Player)
            vote_counts: Голоса игроков {player_id: count}
            round_num: Номер раунда
            context: Контекст (бункер, катастрофа, угрозы)

        Returns:
            dict с полями decision и reasoning
        """
        if not self.available:
            return None

        # Создаём подробный список кандидатов со ВСЕЙ раскрытой информацией
        candidates_info = []
        for p in candidates:
            revealed = []
            
            # Профессия с описанием
            if p.character.profession_revealed:
                revealed.append(f"профессия: {p.character.profession} ({p.character.profession_desc})")

            # Возраст и пол
            if p.character.dossier_revealed:
                revealed.append(f"возраст: {p.character.age} лет")
                revealed.append(f"пол: {p.character.gender}")
                if p.character.orientation:
                    revealed.append(f"ориентация: {p.character.orientation}")
                
            # Здоровье
            if p.character.condition_revealed and p.character.condition:
                revealed.append(f"здоровье: {p.character.condition['name']} - {p.character.condition.get('description', '')}")
            
            # Черты характера
            for trait_ref in p.character.traits_revealed:
                if trait_ref.startswith("positive_"):
                    idx = int(trait_ref.split("_")[1])
                    if idx < len(p.character.positive_traits):
                        trait = p.character.positive_traits[idx]
                        desc = p.character.positive_traits_details[idx] if idx < len(p.character.positive_traits_details) else ""
                        revealed.append(f"черта: +{trait} ({desc})")
                elif trait_ref.startswith("negative_"):
                    idx = int(trait_ref.split("_")[1])
                    if idx < len(p.character.negative_traits):
                        trait = p.character.negative_traits[idx]
                        desc = p.character.negative_traits_details[idx] if idx < len(p.character.negative_traits_details) else ""
                        revealed.append(f"черта: -{trait} ({desc})")
            
            # Багаж
            if p.character.luggage_revealed and p.character.luggage:
                revealed.append(f"багаж: {p.character.luggage.get('name', '')} - {p.character.luggage.get('description', '')}")
            
            # Секрет
            if p.character.secret_revealed and p.character.secret:
                revealed.append(f"секрет: {p.character.secret.get('secret', '')}")

            # Получаем количество голосов против этого игрока
            votes = vote_counts.get(p.id, 0)

            info = f"- {p.name}"
            if revealed:
                info += f" ({'; '.join(revealed)})"
            else:
                info += " (нет раскрытой информации)"
            if votes > 0:
                info += f" - голосов против: {votes}"
            candidates_info.append(info)

        # Формируем контекст
        context_str = self._format_context(context)

        prompt = f"""Ты AI-судья в бункере. Раунд {round_num}.

Контекст игры:
{context_str}

Результаты голосования игроков:
{chr(10).join(candidates_info)}

Прими ФИНАЛЬНОЕ решение - кого исключить из бункера.

ВАЖНО:
1. Учитывай ВСЮ раскрытую информацию: профессии, черты характера, навыки, предметы, здоровье
2. Не зацикливайся только на профессии - рассматривай все качества игрока
3. Взвешивай полезные и вредные черты характера
4. Учитывай голоса игроков и текущую ситуацию в бункере
5. Учитывай параметры бункера (ресурсы, вместимость, особенности) - какие игроки будут полезнее
6. Учитывай катастрофу и события - кто лучше приспособлен к выживанию
7. В обосновании укажи какие именно раскрытые данные и параметры бункера повлияли на решение

В ответе укажи ТОЧНОЕ ИМЯ игрока (как написано выше) и подробное обоснование.

Ответь СТРОГО в формате JSON: {{"decision": "ИМЯ_ИГРОКА", "reasoning": "подробное обоснование с учётом всех раскрытых данных, параметров бункера и катастрофы"}}{self._get_personality_prompt()}"""

        result = await self._call_ai(prompt)

        # Валидация результата — точное сравнение имён
        if result:
            decision = result.get("decision", "").strip()
            valid = any(decision.lower() == p.name.lower() for p in candidates)
            if not valid:
                logger.warning(f"AI вернул неверное имя: {decision}")
                # Возвращаем None чтобы использовать выбор игроков
                return None

        return result

    def _format_context(self, context: dict) -> str:
        """Форматирование контекста для промпта"""
        if not context:
            return ""

        ctx_parts = []

        # КАТАСТРОФА - глобальное событие
        if context.get('catastrophe'):
            catastrophe = context['catastrophe']
            ctx_parts.append(f"🌍 КАТАСТРОФА: {catastrophe.get('name', 'Неизвестная катастрофа')} - {catastrophe.get('description', '')}")

        # БУНКЕР - детальные параметры
        if context.get('bunker'):
            bunker = context['bunker']
            bunker_name = bunker.get('name', 'Неизвестный бункер')
            max_capacity = bunker.get('max_capacity', 25)
            spots = max_capacity // 2
            
            food = bunker.get('food_supply', 100)
            water = bunker.get('water_supply', 100)
            medicine = bunker.get('medicine_supply', 80)
            morale = bunker.get('morale_level', 70)
            
            # Рассчитываем среднее
            avg_resources = (food + water + medicine + morale) / 4
            
            special = bunker.get('special_features', '')
            
            ctx_parts.append(f"🏭 БУНКЕР '{bunker_name}':")
            ctx_parts.append(f"   Вместимость: {max_capacity} чел, мест для игроков: {spots}")
            ctx_parts.append(f"   Ресурсы - Еда: {food}%, Вода: {water}%, Лекарства: {medicine}%, Мораль: {morale}%")
            
            if avg_resources > 70:
                ctx_parts.append("   Состояние: ХОРОШЕЕ - ресурсов достаточно")
            elif avg_resources > 40:
                ctx_parts.append("   Состояние: СРЕДНЕЕ - ресурсы на исходе")
            else:
                ctx_parts.append("   Состояние: КРИТИЧЕСКОЕ - мало ресурсов!")
            
            if special:
                ctx_parts.append(f"   Особенности: {special}")

        # УГРОЗЫ - текущая и история
        threats_info = []
        if context.get('threat'):
            threat = context['threat']
            threat_type = "✅ ПОЛОЖИТЕЛЬНОЕ" if threat.get('is_positive') else "⚠️ ОТРИЦАТЕЛЬНОЕ"
            threats_info.append(f"{threat_type} событие: {threat.get('name', '')} - {threat.get('description', '')}")
        
        if context.get('threat_history') and len(context['threat_history']) > 0:
            history = context['threat_history']
            if len(history) > 1:
                threats_info.append(f"Всего событий в игре: {len(history)}")
        
        if threats_info:
            ctx_parts.append("📊 СОБЫТИЯ: " + "; ".join(threats_info))

        # Раунд
        if context.get('round'):
            ctx_parts.append(f"📍 Текущий раунд: {context['round']}")

        return "\n".join(ctx_parts)

    async def _call_ai(self, prompt: str) -> dict:
        """Вызов AI API"""
        if not self.available:
            logger.warning("[AI] AI недоступен")
            return None

        try:
            logger.info(f"[AI] Отправка промпта: {prompt[:100]}...")
            response = await openai.ChatCompletion.acreate(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,
                max_tokens=500
            )
            raw_content = response.choices[0].message.content
            logger.info(f"[AI] Сырой ответ: {raw_content[:200]}...")
            
            # Пытаемся распарсить JSON
            try:
                result = json.loads(raw_content)
                logger.info(f"[AI] Успешный ответ: {result}")
                return result
            except json.JSONDecodeError as e:
                logger.error(f"[AI] JSON Decode Error: {e}")
                logger.error(f"[AI] Сырой контент: {raw_content}")
                
                # Пытаемся исправить JSON
                import re
                json_match = re.search(r'\{.*\}', raw_content, re.DOTALL)
                if json_match:
                    try:
                        result = json.loads(json_match.group())
                        logger.info(f"[AI] Исправленный JSON: {result}")
                        return result
                    except json.JSONDecodeError:
                        pass
                
                # Возвращаем дефолтный ответ
                logger.warning("[AI] Возвращаем дефолтный ответ")
                return {
                    "thought": "AI не смог обработать ответ",
                    "question": "Расскажите подробнее о своих навыках?"
                }
                
        except Exception as e:
            logger.error(f"[AI] Критическая ошибка: {e}", exc_info=True)
            return None
