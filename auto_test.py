"""
Автотесты для игры БУНКЕР
Автоматически проходит всю игру от начала до конца
"""
import asyncio
import websockets
import json
import logging
import random
from typing import List, Dict

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

WS_URL = "ws://127.0.0.1:8001/ws/"

# Имена тестовых игроков
TEST_PLAYERS = ["Тест1", "Тест2", "Тест3", "Тест4"]


class BotPlayer:
    """Бот-игрок для автотестов"""
    
    def __init__(self, name: str):
        self.name = name
        self.ws = None
        self.player_id = None
        self.ready = False
        self.current_phase = "lobby"
        self.is_my_turn = False
        self.messages = []
        
    async def connect(self):
        """Подключение к серверу"""
        try:
            self.ws = await websockets.connect(f"{WS_URL}{self.name}")
            logger.info(f"✅ {self.name} подключился")
            
            # Читаем сообщения в фоне
            asyncio.create_task(self.receive_messages())
            return True
        except Exception as e:
            logger.error(f"❌ {self.name} ошибка подключения: {e}")
            return False
    
    async def receive_messages(self):
        """Получение сообщений от сервера"""
        try:
            async for message in self.ws:
                data = json.loads(message)
                await self.handle_message(data)
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"🔌 {self.name} отключился")
        except Exception as e:
            logger.error(f"❌ {self.name} ошибка получения: {e}")
    
    async def handle_message(self, data: dict):
        """Обработка входящих сообщений"""
        msg_type = data.get("type")
        
        if msg_type == "game_state":
            game = data.get("game", {})
            self.current_phase = game.get("current_phase", "lobby")
            logger.debug(f"📊 {self.name} фаза: {self.current_phase}")
            
        elif msg_type == "phase_changed":
            self.current_phase = data.get("phase")
            phase_name = data.get("phase_name")
            logger.info(f"🔄 {self.name} фаза: {phase_name}")
            
        elif msg_type == "next_turn":
            if data.get("player_name") == self.name:
                self.is_my_turn = True
                logger.info(f"🎤 {self.name} мой ход!")
                
        elif msg_type == "your_reveal_turn":
            if data.get("player_id") == self.player_id:
                self.is_my_turn = True
                logger.info(f"🃏 {self.name} моя очередь раскрывать карту!")
                
        elif msg_type == "speech_analyzed":
            # AI проанализировал речь и задал вопрос
            ai_thought = data.get("ai_thought", {})
            question = ai_thought.get("question")
            player = ai_thought.get("player")
            
            if question and player == self.name and self.current_phase == "discussion":
                logger.info(f"❓ AI задал вопрос {self.name}: {question}")
                # Отвечаем на вопрос
                asyncio.create_task(self.answer_question(question))
                
        elif msg_type == "voting_timer_started":
            logger.info(f"⏳ {self.name} таймер голосования запущен: {data.get('duration')} сек")
            
        elif msg_type == "voting_timer_update":
            remaining = data.get("remaining")
            if remaining <= 5:
                logger.warning(f"⏰ {self.name} осталось {remaining} сек на голосование!")
                
        elif msg_type == "ai_final_decision":
            decision = data.get("decision", {})
            logger.info(f"⚖️ AI РЕШЕНИЕ: {decision.get('decision')} - {decision.get('reasoning', '')[:100]}...")
            
        elif msg_type == "game_finished":
            verdict = data.get("verdict", {})
            logger.info(f"🏆 ИГРА ЗАВЕРШЕНА: {verdict.get('message', '')[:200]}...")
            
        elif msg_type == "system_message":
            text = data.get("text")
            if "выбыл" in text.lower() or "побед" in text.lower():
                logger.info(f"📢 {self.name}: {text}")
                
        self.messages.append(data)
    
    async def send(self, data: dict):
        """Отправка сообщения"""
        if self.ws:
            await self.ws.send(json.dumps(data))
    
    async def set_ready(self):
        """Нажать кнопку ГОТОВ"""
        await asyncio.sleep(0.5)
        await self.send({"type": "ready"})
        self.ready = True
        logger.info(f"✅ {self.name} готов")
        
    async def reveal_card(self):
        """Раскрыть случайную карту"""
        await asyncio.sleep(1)
        # Выбираем случайную опцию
        options = ["profession", "age", "gender", "positive_0", "negative_0", "condition", "secret", "luggage"]
        option = random.choice(options)
        await self.send({"type": "reveal_card", "option": option})
        logger.info(f"🃏 {self.name} раскрыл {option}")
        
    async def speak(self):
        """Выступить с речью"""
        await asyncio.sleep(1.5)
        speeches = [
            "Я полезный игрок потому что у меня есть важные навыки для выживания в бункере",
            "Прошу оставить меня в бункере я могу принести пользу группе своими умениями",
            "У меня есть опыт который поможет нам выжить в этих сложных условиях",
            "Я готов работать на благо группы и делиться ресурсами с остальными",
            "Мои навыки критически важны для долгосрочного выживания бункера и группы"
        ]
        text = random.choice(speeches)
        await self.send({"type": "speech", "text": text})
        logger.info(f"🗣️ {self.name}: {text[:50]}...")
        
    async def answer_question(self, question: str):
        """Ответить на вопрос AI"""
        await asyncio.sleep(2)
        answers = [
            "Да я понимаю свою ответственность и готов доказать свою полезность",
            "Это сложный вопрос но я считаю что мой вклад будет значительным",
            "Я думаю что мои навыки перевешивают возможные риски",
            "Спасибо за вопрос я рад возможности объяснить свою позицию",
            "Я понимаю ваши опасения но уверен что принесу пользу группе"
        ]
        text = random.choice(answers)
        await self.send({"type": "speech", "text": text})
        logger.info(f"💬 {self.name} отвечает на вопрос AI: {text[:50]}...")
        
    async def vote(self, targets: List[str]):
        """Проголосовать за случайного игрока"""
        await asyncio.sleep(random.uniform(2, 5))
        if targets:
            target = random.choice(targets)
            await self.send({"type": "vote", "target_id": target})
            logger.info(f"🗳️ {self.name} голосует за {target}")
            
    async def choose_reveal(self):
        """Раскрыть карту после выбывания"""
        await asyncio.sleep(2)
        options = ["profession", "secret", "luggage"]
        option = random.choice(options)
        await self.send({"type": "choose_reveal", "option": option})
        logger.info(f"🃏 {self.name} раскрыл посмертно: {option}")
        
    async def skip_reveal(self):
        """Пропустить раскрытие карты"""
        await self.send({"type": "skip_reveal"})
        logger.info(f"🔇 {self.name} пропустил раскрытие карты")
        
    async def close(self):
        """Закрыть соединение"""
        if self.ws:
            await self.ws.close()


async def wait_for_phase(players: List[BotPlayer], phase: str, timeout: int = 60):
    """Ждать пока все игроки не перейдут в нужную фазу"""
    start = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start < timeout:
        phases = [p.current_phase for p in players]
        if all(p == phase for p in phases):
            return True
        await asyncio.sleep(0.5)
    return False


async def wait_for_turn(players: List[BotPlayer], timeout: int = 30):
    """Ждать пока у кого-то не будет ход"""
    start = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start < timeout:
        for p in players:
            if p.is_my_turn:
                return p
        await asyncio.sleep(0.5)
    return None


async def get_vote_targets(players: List[BotPlayer]) -> List[str]:
    """Получить список ID игроков за которых можно голосовать"""
    # Ждём обновления состояния
    await asyncio.sleep(1)
    targets = []
    for p in players:
        # Голосуем за всех активных (не выбывших и не в бункере)
        if p.player_id:
            targets.append(p.player_id)
    return targets


async def run_test_game():
    """Запуск тестовой игры"""
    logger.info("=" * 60)
    logger.info("🎮 ЗАПУСК АВТОТЕСТА БУНКЕР")
    logger.info("=" * 60)
    
    # Создаём и подключаем ботов
    bots = [BotPlayer(name) for name in TEST_PLAYERS]
    
    connected = []
    for bot in bots:
        if await bot.connect():
            connected.append(bot)
        await asyncio.sleep(0.3)
    
    if len(connected) < 2:
        logger.error("❌ Недостаточно игроков для старта (нужно минимум 2)")
        return
    
    logger.info(f"✅ Подключено {len(connected)} игроков")
    
    # Ждём немного чтобы все получили начальное состояние
    await asyncio.sleep(2)
    
    # Все нажимают ГОТОВ
    logger.info("\n📋 ФАЗА: ГОТОВНОСТЬ")
    for bot in connected:
        await bot.set_ready()
        await asyncio.sleep(0.3)
    
    # Ждём начала игры
    logger.info("\n⏳ Ожидание начала игры...")
    if not await wait_for_phase(connected, "reveal_card", timeout=30):
        logger.error("❌ Игра не началась")
        return
    
    logger.info("✅ Игра началась!")
    
    # Игровой цикл
    round_num = 0
    max_rounds = 5
    
    while round_num < max_rounds:
        round_num += 1
        logger.info(f"\n{'='*40}")
        logger.info(f"🔴 РАУНД {round_num}")
        logger.info(f"{'='*40}")
        
        # Фаза раскрытия карт
        logger.info("\n🃏 ФАЗА: РАСКРЫТИЕ КАРТ")
        for bot in connected:
            if bot.current_phase == "reveal_card":
                # Имитируем раскрытие
                await bot.reveal_card()
                await asyncio.sleep(1)
        
        # Ждём перехода к обсуждению
        await asyncio.sleep(2)
        
        # Фаза обсуждения
        logger.info("\n🗣️ ФАЗА: ОБСУЖДЕНИЕ")
        for bot in connected:
            if bot.current_phase == "discussion":
                await bot.speak()
                await asyncio.sleep(3)  # Ждём пока AI задаст вопрос и бот ответит
        
        # Ждём пока все ответят на вопросы AI
        logger.info("⏳ Ожидание ответов на вопросы AI...")
        await asyncio.sleep(5)
        
        # Финальное слово
        logger.info("\n🎤 ФАЗА: ФИНАЛЬНОЕ СЛОВО")
        for bot in connected:
            if bot.current_phase == "final_word":
                await bot.speak()
                await asyncio.sleep(2)
        
        # Голосование
        logger.info("\n🗳️ ФАЗА: ГОЛОСОВАНИЕ")
        # Ждём пока запустится таймер
        await asyncio.sleep(2)
        
        # Все голосуют
        for bot in connected:
            if bot.current_phase == "voting":
                # Голосуем за случайного (не за себя)
                targets = [b.player_id or b.name for b in connected if b != bot]
                await bot.vote(targets)
                await asyncio.sleep(1)
        
        # Ждём результатов голосования
        logger.info("\n⏳ Ожидание результатов голосования...")
        await asyncio.sleep(5)
        
        # Проверяем не закончилась ли игра
        if any(b.current_phase == "results" for b in connected):
            logger.info("🏆 ИГРА ЗАВЕРШЕНА!")
            break
            
        if any(b.current_phase == "reveal" for b in connected):
            logger.info("\n🃏 ФАЗА: РАСКРЫТИЕ КАРТЫ ВЫБЫВШЕГО")
            await asyncio.sleep(3)
        
        # Переход к следующему раунду
        await asyncio.sleep(2)
    
    # Ждём завершения игры
    logger.info("\n⏳ Ожидание завершения игры...")
    await asyncio.sleep(10)
    
    # Закрываем соединения
    for bot in connected:
        await bot.close()
    
    logger.info("\n" + "=" * 60)
    logger.info("✅ АВТОТЕСТ ЗАВЕРШЁН")
    logger.info("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(run_test_game())
    except KeyboardInterrupt:
        logger.info("\n⚠️ Тест прерван пользователем")
    except Exception as e:
        logger.error(f"❌ Ошибка теста: {e}", exc_info=True)
