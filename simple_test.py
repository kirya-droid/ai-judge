"""
Простой тест игры БУНКЕР
Просто подключается и ждёт пока игра завершится
"""
import asyncio
import websockets
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

WS_URL = "ws://127.0.0.1:8001/ws/"


async def test_game():
    """Тест игры"""
    logger.info("=" * 60)
    logger.info("🎮 ЗАПУСК ТЕСТА БУНКЕР")
    logger.info("=" * 60)
    
    # Подключаемся
    async with websockets.connect(f"{WS_URL}TestBot") as ws:
        logger.info("✅ Подключился")
        
        # Ждём пока игра завершится
        phase = "lobby"
        round_num = 0
        
        async for message in ws:
            data = json.loads(message)
            msg_type = data.get("type")
            
            if msg_type == "game_state":
                game = data.get("game", {})
                phase = game.get("current_phase", phase)
                round_num = game.get("round_number", round_num)
                
            elif msg_type == "phase_changed":
                phase = data.get("phase")
                phase_name = data.get("phase_name")
                logger.info(f"🔄 Фаза: {phase_name}")
                
            elif msg_type == "ai_final_decision":
                decision = data.get("decision", {})
                logger.info(f"⚖️ AI РЕШЕНИЕ: {decision.get('decision')}")
                logger.info(f"   Причина: {decision.get('reasoning', '')[:100]}...")
                
            elif msg_type == "voting_completed":
                logger.info(f"📢 Выбыл: {data.get('eliminated')}")
                
            elif msg_type == "game_finished":
                verdict = data.get("verdict", {})
                logger.info("🏆 ИГРА ЗАВЕРШЕНА!")
                logger.info(f"   {verdict.get('message', '')[:200]}...")
                return True
                
            elif msg_type == "system_message":
                text = data.get("text", "")
                if "побед" in text.lower() or "выбыл" in text.lower():
                    logger.info(f"📢 {text}")
        
        return False


if __name__ == "__main__":
    try:
        result = asyncio.run(test_game())
        logger.info(f"\n✅ ТЕСТ ЗАВЕРШЁН: {'УСПЕХ' if result else 'ПРОВАЛ'}")
    except KeyboardInterrupt:
        logger.info("\n⚠️ Тест прерван")
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}", exc_info=True)
