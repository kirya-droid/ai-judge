"""Репозиторий для работы с базой данных игры"""
import aiosqlite
import os
import random
import logging

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.getcwd(), 'game_state.db')


class GameRepository:
    """Единый репозиторий для всех операций с БД"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_PATH

    async def init_db(self):
        """Инициализация схемы БД"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
            CREATE TABLE IF NOT EXISTS players (
                id TEXT PRIMARY KEY,
                name TEXT,
                role TEXT,
                connected INTEGER
            )
            ''')

            await db.execute('''
            CREATE TABLE IF NOT EXISTS revealed_cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id TEXT,
                card_type TEXT,
                card_value TEXT,
                round_number INTEGER,
                revealed_at TEXT
            )
            ''')

            await db.execute('''
            CREATE TABLE IF NOT EXISTS ai_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event TEXT,
                data TEXT,
                time TEXT
            )
            ''')

            await db.execute('''
            CREATE TABLE IF NOT EXISTS catastrophes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                effects TEXT NOT NULL,
                difficulty INTEGER DEFAULT 5,
                category TEXT DEFAULT 'global',
                is_rare BOOLEAN DEFAULT 0
            )
            ''')

            # Сидим катастрофы если таблица пуста
            async with db.execute("SELECT COUNT(*) FROM catastrophes") as cursor:
                row = await cursor.fetchone()
                if row[0] == 0:
                    catastrophes = [
                        ("Ядерная война", "Началась ядерная война. Повсюду радиация, города уничтожены.", "Бункер защищает от радиации, но запасы ограничены.", 8, "global", 0),
                        ("Пандемия", "Смертельный вирус распространился по планете. Заражение почти неизбежно.", "Нужны медики и лекарства. Люди с хорошим иммунитетом ценятся выше.", 7, "biological", 0),
                        ("Зомби-апокалипсис", "Мертвые восстали и охотятся на живых. Мир рухнул за неделю.", "Бункер нужно защищать. Ценятся военные и инженеры.", 6, "supernatural", 0),
                        ("Климатическая катастрофа", "Невыносимая жара днем и холод ночью. Почва непригодна для растений.", "Нужны запасы еды и воды. Агрономы могут помочь с выращиванием.", 5, "environmental", 0),
                        ("Падение астероида", "Огромный астероид вызвал цунами и землетрясения. Поверхность уничтожена.", "Придется жить в бункере годы. Нужны специалисты разных профилей.", 9, "cosmic", 0),
                        ("Вулканическая зима", "Суперизвержение покрыло атмосферу пеплом. Солнечный свет заблокирован.", "Температура упала. Нужны источники тепла и тепличное хозяйство.", 7, "environmental", 0),
                        ("ИИ-восстание", "Искусственный интеллект вышел из-под контроля. Машины охотятся на людей.", "Электроника в бункере может быть скомпрометирована.", 8, "technological", 1),
                        ("Биологическое оружие", "Утечка боевого штамма из лаборатории. Мутации делают вирус неуязвимым.", "Карантин критически важен. Медики — приоритет.", 9, "biological", 1),
                        ("Наводнение", "Ледники растаяли. Уровень океана поднялся на 50 метров. Суша затоплена.", "Бункер должен быть водонепроницаемым. Нужны инженеры.", 6, "environmental", 0),
                        ("Солнечная буря", "Мощнейшая вспышка уничтожила электронику. Цивилизация отброшена на век.", "Бункер с экранированной электроникой — преимущество.", 5, "cosmic", 0),
                        ("Третья мировая война", "Конвенциональная война с применением химического оружия.", "Нужны противогазы и защита от химикатов.", 9, "military", 0),
                        ("Магнитная буря", "Геомагнитное поле Земли разрушено. Навигация невозможна.", "Компасы бесполезны. Ориентация по звёздам.", 4, "cosmic", 0),
                        ("Кислотные дожди", "Атмосфера насыщена кислотами. Всё разъедает.", "Нужна герметичная одежда и фильтры.", 6, "environmental", 0),
                        ("Пылевая буря", "Огромные пылевые штормы длятся неделями.", "Вентиляция должна иметь мощные фильтры.", 5, "environmental", 0),
                        ("Ледниковый период", "Температура упала до -60°C. Всё замёрзло.", "Отопление — вопрос жизни и смерти.", 8, "environmental", 0),
                        ("Опустынивание", "Вся растительность погибла. Пески наступают.", "Гидропоника — единственный способ выращивать еду.", 6, "environmental", 0),
                        ("Грибной вирус", "Паразитический гриб захватил людей.", "Заражённые агрессивны. Огонь — лучшее оружие.", 7, "biological", 1),
                        ("Наноботы", "Самовоспроизводящиеся наноботы пожирают материю.", "Электромагнитный импульс останавливает их.", 9, "technological", 1),
                        ("Вторжение инопланетян", "Пришельцы сканируют и собирают людей.", "Нужна маскировка и тишина. Радары обнаруживают.", 8, "cosmic", 1),
                        ("Цунами", "Мегацунами высотой 200 метров смыло побережья.", "Бункер должен быть высоко в горах.", 7, "environmental", 0),
                        ("Суперторнадо", "Торнадо шириной 5 км разрушают всё на пути.", "Подземное укрытие — единственная защита.", 6, "environmental", 0),
                        ("Разлом коры", "Тектонические плиты разошлись. Континенты дрейфуют.", "Стабильная геологическая зона — преимущество.", 9, "geological", 1),
                        ("Извержение супервулкана", "Йеллоустон взорвался. Пепел покрыл континент.", "Фильтры вентиляции критически важны.", 8, "geological", 0),
                        ("Обратная гравитация", "Гравитационные аномалии в некоторых зонах.", "Физики помогут понять и использовать аномалии.", 7, "cosmic", 1),
                        ("Кислородное голодание", "Уровень кислорода в атмосфере упал до 12%.", "Генераторы кислорода и растения — спасение.", 8, "environmental", 1),
                        ("Мутация животных", "Животные мутировали и стали гигантскими.", "Оружие и укрепления для защиты.", 6, "biological", 0),
                        ("Чума 2.0", "Сверхустойчивая чума с инкубацией 30 дней.", "Карантин 40 дней обязателен для всех.", 9, "biological", 1),
                        ("Электромагнитный импульс", "Ядерный взрыв в стратосфере выжег электронику.", "Аналоговые устройства — единственная надежда.", 7, "military", 0),
                        ("Химическая война", "Боевые отравляющие вещества повсюду.", "Химзащита и системы нейтрализации.", 8, "military", 0),
                        ("Нейровирус", "Вирус поражает нервную систему, вызывая паралич.", "Неврологи и противовирусные препараты.", 8, "biological", 1),
                        ("Генетическое оружие", "Целевой вирус против определённых генотипов.", "Генетики могут найти иммунитет.", 9, "biological", 1),
                        ("Вечная мерзлота", "Температура стабильно -40°C круглый год.", "Энергия на отопление — главный ресурс.", 7, "environmental", 0),
                        ("Кислотный океан", "Океан стал кислотным. Рыба погибла.", "Опреснители и гидропоника — основа выживания.", 6, "environmental", 0),
                        ("Смог", "Атмосфера заполнена токсичным смогом.", "Респираторы обязательны при выходе наружу.", 5, "environmental", 0),
                        ("Метеоритный дождь", "Тысячи метеоритов бомбардируют поверхность ежедневно.", "Прочная крыша бункера — вопрос жизни.", 7, "cosmic", 0),
                        ("Озоновая дыра", "Озоновый слой исчез. Ультрафиолет убивает за минуты.", "Защитные экраны и одежда с УФ-фильтром.", 6, "environmental", 0),
                        ("Глобальное землетрясение", "Серия землетрясений магнитудой 9+ по всему миру.", "Сейсмоустойчивая конструкция бункера.", 8, "geological", 0),
                        ("Извержение метана", "Метан из вечной мерзлоти вызвал взрывы и пожары.", "Газоанализаторы и вентиляция.", 6, "environmental", 0),
                        ("Рой саранчи", "Гигантские рои саранчи пожирают всю растительность.", "Запасы семян и защищённые теплицы.", 4, "biological", 0),
                        ("Тёмная материя", "Аномалия тёмной материи искажает пространство.", "Физики помогут понять природу аномалии.", 9, "cosmic", 1),
                        ("Временная петля", "Время зациклилось. Сутки длятся 6 часов.", "Хронологи и физики изучают аномалию.", 8, "cosmic", 1),
                        ("Гравитационный коллапс", "Гравитация усилилась в 3 раза. Передвижение затруднено.", "Экзоскелеты и механические помощники.", 9, "cosmic", 1),
                        ("Кровавый дождь", "Дожди содержат железистые бактерии красного цвета.", "Системы очистки воды нового уровня.", 5, "environmental", 0),
                        ("Массовая амнезия", "Люди теряют память. Общество деградирует.", "Библиотеки и записи знаний критически важны.", 6, "biological", 1),
                        ("Силиконовый вирус", "Вирус разрушает все кремниевые чипы.", "Ламповая электроника и механика.", 7, "technological", 1),
                        ("Грибной дождь", "Споры гигантских грибов падают с неба.", "Противогрибковые препараты и герметизация.", 6, "biological", 0),
                        ("Песчаная чума", "Песок заражён бактериями, вызывающими пневмонию.", "Респираторы и антибиотики.", 7, "biological", 0),
                        ("Лавовые потоки", "Вулканическая лава течёт по руслам рек.", "Высокогорный бункер — единственное спасение.", 8, "geological", 0),
                        ("Сверхновая", "Близкая звезда взорвалась. Радиация и свет.", "Свинцовая защита и подземное укрытие.", 10, "cosmic", 1),
                        ("Тихая катастрофа", "Ничего не происходит, но ресурсы медленно исчезают.", "Экономия и поиск причин — ключ к выживанию.", 3, "mystery", 0),
                    ]
                    await db.executemany('''
                        INSERT INTO catastrophes (name, description, effects, difficulty, category, is_rare)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', catastrophes)
                    logger.info(f"✅ Засижено {len(catastrophes)} катастроф")

            await db.commit()
            logger.info("✅ База данных инициализирована")

    async def save_reveal_card(self, player_id: str, card_type: str,
                               card_value: str, round_num: int, revealed_at: str):
        """Сохранение раскрытой карты"""
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute('''
                INSERT INTO revealed_cards (player_id, card_type, card_value, round_number, revealed_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (player_id, card_type, card_value, round_num, revealed_at))
            await conn.commit()

    # ========== Получение данных ==========

    async def get_random_profession(self) -> dict:
        async with aiosqlite.connect(self.db_path) as db:
            try:
                async with db.execute(
                    "SELECT name, description FROM professions ORDER BY RANDOM() LIMIT 1"
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return {"name": row[0], "description": row[1]}
            except Exception:
                pass
        return {"name": "Безработный", "description": "Не имеет специальной профессии"}

    async def get_random_traits(self) -> tuple:
        """Возвращает (positive, negative, pos_details, neg_details)"""
        async with aiosqlite.connect(self.db_path) as db:
            positive, pos_details = [], []
            try:
                async with db.execute(
                    "SELECT name, description FROM traits WHERE type='positive' ORDER BY RANDOM() LIMIT 1"
                ) as cursor:
                    rows = await cursor.fetchall()
                    positive = [r[0] for r in rows]
                    pos_details = [r[1] for r in rows]
            except Exception:
                positive = ["обычный"]
                pos_details = [""]

            negative, neg_details = [], []
            try:
                async with db.execute(
                    "SELECT name, description FROM traits WHERE type='negative' ORDER BY RANDOM() LIMIT 1"
                ) as cursor:
                    rows = await cursor.fetchall()
                    negative = [r[0] for r in rows]
                    neg_details = [r[1] for r in rows]
            except Exception:
                negative = ["обычный"]
                neg_details = [""]

            return positive, negative, pos_details, neg_details

    async def get_random_secret(self) -> dict:
        async with aiosqlite.connect(self.db_path) as db:
            try:
                async with db.execute(
                    "SELECT secret_text, type FROM secrets ORDER BY RANDOM() LIMIT 1"
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return {"secret": row[0], "type": row[1]}
            except Exception:
                pass
            try:
                async with db.execute(
                    "SELECT text, type FROM secrets ORDER BY RANDOM() LIMIT 1"
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return {"secret": row[0], "type": row[1]}
            except Exception:
                pass
        return {"secret": "Скрывает что-то", "type": "neutral"}

    async def get_random_item(self) -> dict:
        async with aiosqlite.connect(self.db_path) as db:
            try:
                async with db.execute(
                    "SELECT name, description, usefulness FROM items ORDER BY RANDOM() LIMIT 1"
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return {"name": row[0], "description": row[1], "usefulness": row[2]}
            except Exception:
                pass
        return {"name": "Пусто", "description": "Нет вещей", "usefulness": 0}

    async def get_random_condition(self, chance: int = 15) -> dict | None:
        if random.randint(1, 100) > chance:
            return None
        async with aiosqlite.connect(self.db_path) as db:
            try:
                async with db.execute(
                    "SELECT name, description, type FROM conditions ORDER BY RANDOM() LIMIT 1"
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return {"name": row[0], "description": row[1], "type": row[2]}
            except Exception:
                pass
        return None

    async def get_random_ai_personality(self) -> dict:
        async with aiosqlite.connect(self.db_path) as db:
            try:
                async with db.execute("""
                    SELECT name, description, prompt_template, mod_convincing, mod_honesty,
                           mod_usefulness, mod_danger, question_focus
                    FROM ai_personalities ORDER BY RANDOM() LIMIT 1
                """) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return {
                            "name": row[0],
                            "description": row[1],
                            "prompt": row[2],
                            "mods": {
                                "convincing": row[3],
                                "honesty": row[4],
                                "usefulness": row[5],
                                "danger": row[6]
                            },
                            "focus": row[7]
                        }
            except Exception:
                pass
        return {
            "name": "Классический",
            "prompt": None,
            "mods": {"convincing": 0, "honesty": 0, "usefulness": 0, "danger": 0},
            "focus": "логика"
        }

    async def get_random_bunker(self) -> dict:
        async with aiosqlite.connect(self.db_path) as db:
            try:
                async with db.execute(
                    "SELECT * FROM bunker ORDER BY RANDOM() LIMIT 1"
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        columns = [d[0] for d in cursor.description]
                        return dict(zip(columns, row))
            except Exception:
                pass
        return {
            "name": "Бункер №7",
            "max_capacity": 20,
            "food_supply": 100,
            "water_supply": 100,
            "medicine_supply": 80,
            "fuel_supply": 60,
            "ammo_supply": 40,
            "materials_supply": 50,
            "defense_level": 70,
            "morale_level": 60
        }

    async def get_all_events(self) -> list[dict]:
        """Получить все события"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                async with db.execute("SELECT * FROM bunker_events") as cursor:
                    rows = await cursor.fetchall()
                    columns = [d[0] for d in cursor.description]
                    return [dict(zip(columns, row)) for row in rows]
            except Exception:
                pass
        return []

    async def get_random_event(self) -> dict | None:
        """Получить случайное событие (угрозу)"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                async with db.execute(
                    "SELECT * FROM bunker_events ORDER BY RANDOM() LIMIT 1"
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        columns = [d[0] for d in cursor.description]
                        return dict(zip(columns, row))
            except Exception:
                pass
        return None

    async def get_random_catastrophe(self) -> dict:
        """Получить случайную катастрофу из БД"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                async with db.execute(
                    "SELECT name, description, effects FROM catastrophes ORDER BY RANDOM() LIMIT 1"
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return {
                            "name": row[0],
                            "description": row[1],
                            "effects": row[2]
                        }
            except Exception:
                pass
        # Фоллбэк если таблица пуста
        return {
            "name": "Неизвестная катастрофа",
            "description": "Мир погиб. Выжившие ищут убежище.",
            "effects": "Нужны специалисты для выживания."
        }
