"""Модель персонажа игрока — чистая data-модель без БД"""
import random
import logging

logger = logging.getLogger(__name__)


class Character:
    def __init__(self, name: str):
        self.name = name
        self.age = random.randint(18, 70)
        self.gender = random.choice(["Мужской", "Женский"])
        # Ориентация — у ~30% игроков, иначе None (скрыта)
        self.orientation = self._random_orientation()
        self.profession = "Загрузка..."
        self.profession_desc = ""
        self.positive_traits = []
        self.negative_traits = []
        self.positive_traits_details = []
        self.negative_traits_details = []
        self.secret = {"secret": "Загрузка...", "type": "neutral"}
        self.luggage = {}
        self.condition = None

        # Статусы раскрытия
        self.secret_revealed = False
        self.profession_revealed = False
        self.condition_revealed = False
        self.traits_revealed = []
        self.dossier_revealed = False  # объединённая карта: возраст + пол + ориентация
        self.luggage_revealed = False
        self.can_reveal_options = []

    def _random_orientation(self) -> str | None:
        """Ориентация — у 30% игроков"""
        if random.random() > 0.3:
            return None
        return random.choice([
            "Гетеросексуал",
            "Гетеросексуал",
            "Гетеросексуал",
            "Бисексуал",
            "Бисексуал",
            "Гомосексуал",
            "Асексуал",
            "Пансексуал",
        ])

    async def initialize(self, repo):
        """Инициализация персонажа данными из репозитория

        Args:
            repo: GameRepository — источник данных для персонажа
        """
        try:
            prof_data = await repo.get_random_profession()
            self.profession = prof_data["name"]
            self.profession_desc = prof_data["description"]

            # Параллельные запросы для ускорения
            import asyncio
            traits_task = repo.get_random_traits()
            secret_task = repo.get_random_secret()
            luggage_task = repo.get_random_item()
            condition_task = repo.get_random_condition(chance=15)

            traits_result, self.secret, self.luggage, self.condition = await asyncio.gather(
                traits_task, secret_task, luggage_task, condition_task
            )

            positive, negative, pos_details, neg_details = traits_result
            self.positive_traits = positive if positive else ["обычный"]
            self.negative_traits = negative if negative else ["обычный"]
            self.positive_traits_details = pos_details if pos_details else [""]
            self.negative_traits_details = neg_details if neg_details else [""]

            logger.info(f"✅ Персонаж {self.name} инициализирован: {self.profession}")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации персонажа {self.name}: {e}")
            self._set_default_values()

    def _set_default_values(self):
        """Установка значений по умолчанию при ошибке"""
        self.profession = "Безработный"
        self.profession_desc = "Не имеет специальной профессии"
        self.positive_traits = ["обычный"]
        self.negative_traits = ["обычный"]
        self.secret = {"secret": "Нет секретов", "type": "neutral"}
        self.luggage = {"name": "Пусто", "description": "Нет вещей"}

    def get_reveal_options(self):
        """Получение доступных опций для раскрытия"""
        options = []
        if not self.profession_revealed:
            options.append({"type": "profession", "name": "Профессия", "emoji": "⚕️"})

        if not self.dossier_revealed:
            dossier_parts = [f"{self.age} лет", self.gender]
            if self.orientation:
                dossier_parts.append(self.orientation)
            options.append({
                "type": "dossier",
                "name": f"Досье: {', '.join(dossier_parts)}",
                "emoji": "🪪"
            })

        for i, trait in enumerate(self.positive_traits):
            if f"positive_{i}" not in self.traits_revealed:
                options.append({"type": f"positive_{i}", "name": f"Черта: {trait}", "emoji": "✅"})
                break

        for i, trait in enumerate(self.negative_traits):
            if f"negative_{i}" not in self.traits_revealed:
                options.append({"type": f"negative_{i}", "name": f"Черта: {trait}", "emoji": "⚠️"})
                break

        if self.condition and not self.condition_revealed:
            options.append({"type": "condition", "name": "Здоровье", "emoji": "💊"})

        if not self.secret_revealed:
            options.append({"type": "secret", "name": "Секрет", "emoji": "🔒"})

        if self.luggage and not self.luggage_revealed:
            options.append({"type": "luggage", "name": "Багаж", "emoji": "🎒"})

        return options

    def reveal_option(self, option_type: str):
        """Раскрытие выбранной опции"""
        if option_type == "profession":
            self.profession_revealed = True
            logger.info(f"🔓 Раскрыта профессия: {self.profession}")
            return {"type": "profession", "value": self.profession, "description": self.profession_desc}

        elif option_type == "dossier":
            self.dossier_revealed = True
            value = {"age": self.age, "gender": self.gender}
            if self.orientation:
                value["orientation"] = self.orientation
            logger.info(f"🪪 Раскрыто досье: {self.age} лет, {self.gender}" + (f", {self.orientation}" if self.orientation else ""))
            return {"type": "dossier", "value": value}

        elif option_type.startswith("positive_"):
            index = int(option_type.split("_")[1])
            self.traits_revealed.append(option_type)
            logger.info(f"✅ Раскрыта черта: {self.positive_traits[index]}")
            return {"type": "positive_trait", "value": self.positive_traits[index], "index": index}

        elif option_type.startswith("negative_"):
            index = int(option_type.split("_")[1])
            self.traits_revealed.append(option_type)
            logger.info(f"⚠️ Раскрыта черта: {self.negative_traits[index]}")
            return {"type": "negative_trait", "value": self.negative_traits[index], "index": index}

        elif option_type == "condition":
            self.condition_revealed = True
            logger.info(f"💊 Раскрыто здоровье: {self.condition}")
            return {"type": "condition", "value": self.condition}

        elif option_type == "secret":
            self.secret_revealed = True
            logger.info(f"🔓 Раскрыт секрет: {self.secret}")
            return {"type": "secret", "value": self.secret}

        elif option_type == "luggage":
            self.luggage_revealed = True
            logger.info(f"🎒 Показан багаж: {self.luggage}")
            return {"type": "luggage", "value": self.luggage}

        return None

    def to_dict(self, viewer_name: str = None):
        """Конвертация в словарь для отправки клиенту"""
        is_owner = (viewer_name == self.name)
        result = {}

        # Досье: возраст + пол + ориентация (раскрываются вместе)
        if is_owner or self.dossier_revealed:
            result["age"] = self.age
            result["gender"] = self.gender
            if self.orientation:
                result["orientation"] = self.orientation
        else:
            result["age"] = "???"
            result["gender"] = "???"

        # Профессия
        if self.profession_revealed or is_owner:
            result["profession"] = self.profession
            result["profession_desc"] = self.profession_desc
        else:
            result["profession"] = "???"
            result["profession_desc"] = "Скрыто"

        # Черты характера
        if is_owner:
            result["positive_traits"] = self.positive_traits
            result["negative_traits"] = self.negative_traits
        else:
            revealed_pos = []
            for i, trait in enumerate(self.positive_traits):
                if f"positive_{i}" in self.traits_revealed:
                    revealed_pos.append(trait)
                else:
                    revealed_pos.append("???")
            result["positive_traits"] = revealed_pos

            revealed_neg = []
            for i, trait in enumerate(self.negative_traits):
                if f"negative_{i}" in self.traits_revealed:
                    revealed_neg.append(trait)
                else:
                    revealed_neg.append("???")
            result["negative_traits"] = revealed_neg

        # Багаж
        if is_owner:
            result["luggage"] = self.luggage
        elif self.luggage_revealed:
            result["luggage"] = self.luggage
        else:
            result["luggage"] = {"name": "???", "description": "Скрыто"}

        # Раскрытые черты для клиента
        if is_owner:
            result["traits_revealed"] = self.traits_revealed

        result["luggage_revealed"] = self.luggage_revealed

        # Здоровье
        if hasattr(self, 'condition') and self.condition:
            if self.condition_revealed or is_owner:
                result["condition"] = self.condition
            else:
                result["condition"] = {"name": "???", "description": "Скрыто"}

        # Секрет
        if self.secret_revealed or is_owner:
            result["secret"] = self.secret
        else:
            result["secret"] = {"secret": "???", "type": "hidden"}

        # Статусы раскрытия для владельца
        if is_owner:
            result["secret_revealed"] = self.secret_revealed
            result["profession_revealed"] = self.profession_revealed
            result["dossier_revealed"] = self.dossier_revealed
            result["can_reveal"] = self.get_reveal_options()

        return result
