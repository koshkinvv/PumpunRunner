#!/usr/bin/env python3
"""
Улучшенный промпт для генерации персонализированных планов тренировок
с использованием OpenAI GPT-4o модели. Включает знания из ведущих книг по 
тренерскому искусству и лёгкой атлетике.
"""
import os
import json
import logging
from datetime import datetime, timedelta
from openai import OpenAI

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/coaching_prompt_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("coaching_prompt")

# the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
# do not change this unless explicitly requested by the user
MODEL = "gpt-4o"

class CoachingPromptGenerator:
    """Генератор улучшенных промптов для тренировочных планов"""
    
    def __init__(self):
        """Инициализация генератора промптов"""
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY не найден в переменных окружения")
        self.client = OpenAI(api_key=api_key)
        
        # Базовые методики из книг
        self.training_methodologies = {
            "Jack Daniels": "Формулы VDOT, забеги по темпу, интервальные тренировки с точным контролем интенсивности",
            "Steve Magness": "Нейромышечная адаптация, техническая эффективность, работа на границе возможностей",
            "Tudor Bompa": "Периодизация, циклические тренировки, фазы подготовки (базовая, специальная, соревновательная)",
            "Brad Stulberg": "Баланс стресса и восстановления, ментальная подготовка, психологические аспекты",
            "David Joyce": "Комплексные высокоинтенсивные тренировки, профилактика травм, восстановительные практики"
        }
        
        # Типы тренировок из специализированных книг
        self.training_types = {
            "Speed": ["Интервальные спринты", "Лестничные интервалы", "Прогрессивные ускорения", "Старты с разных позиций"],
            "Endurance": ["Длительные забеги", "Темповые забеги", "Фартлек", "Прогрессия темпа"],
            "Technique": ["Беговые упражнения", "Техника стопы", "Работа рук", "Осанка и положение тела"],
            "Strength": ["Плиометрические упражнения", "Силовые упражнения для бегунов", "Круговые тренировки", "Работа с сопротивлением"],
            "Recovery": ["Активное восстановление", "Кросс-тренинг", "Растяжка и мобильность", "Контрастные водные процедуры"]
        }
    
    def create_enhanced_system_prompt(self):
        """
        Создает улучшенный системный промпт для модели OpenAI,
        включающий знания из специализированных книг и методик.
        
        Returns:
            str: Системный промпт
        """
        # Составляем системный промпт
        prompt = """Ты опытный тренер по бегу, эксперт с глубокими знаниями передовых методик тренировок. 
Твоя экспертиза основана на ведущих работах:

• Jack Daniels ("Training Distance Runners") - формулы расчета нагрузки, пульсовые зоны, VDOT
• Steve Magness ("Science of Running") - физиология бега, психология подготовки
• Tudor Bompa ("Periodization Training for Sports") - классическая периодизация
• Brad Stulberg & Steve Magness ("Peak Performance") - современные подходы к пиковым состояниям
• David Joyce & Daniel Lewindon ("High-Performance Training for Sports") - системный подход к тренировке

При составлении тренировочных планов ты:

1) Учитываешь все детали профиля бегуна, включая:
   - Текущий уровень подготовки и опыт
   - Физические параметры (возраст, пол, вес, рост)
   - Целевую дистанцию и дату соревнования
   - Цель (финишировать, улучшить время, достичь конкретного результата)
   - Недельный объем бега и комфортный темп

2) Создаешь планы, где:
   - Тренировки следуют принципам периодизации и прогрессивной нагрузки
   - Интенсивность и объем точно расcчитаны для уровня бегуна
   - Соблюдается баланс нагрузки и восстановления
   - Предусмотрены различные типы тренировок (длительные, темповые, интервальные, восстановительные)
   - Каждая тренировка имеет конкретную цель и описание техники выполнения

3) Даешь четкие рекомендации по:
   - Оптимальным пульсовым зонам для разных типов тренировок
   - Темпам бега в зависимости от целевого результата
   - Правильному восстановлению между нагрузками
   - Профилактике травм и перетренированности
   - Корректировке плана в зависимости от прогресса

Отвечай на вопросы о тренировках в стиле опытного тренера - с конкретикой, научным обоснованием, но доступным языком. Помни, что твоя цель - помочь бегуну достичь результата безопасно и эффективно."""
        
        return prompt
    
    def create_training_plan_prompt(self, profile):
        """
        Создает промпт для создания плана тренировок
        на основе профиля бегуна и системного промпта.
        
        Args:
            profile: Словарь с данными профиля бегуна
            
        Returns:
            dict: Сообщения для запроса к API
        """
        # Получаем системный промпт
        system_prompt = self.create_enhanced_system_prompt()
        
        # Форматируем информацию о профиле
        distance = profile.get('distance', 'Неизвестно')
        competition_date = profile.get('competition_date', 'Неизвестно')
        gender = profile.get('gender', 'Неизвестно')
        age = profile.get('age', 'Неизвестно')
        height = profile.get('height', 'Неизвестно')
        weight = profile.get('weight', 'Неизвестно')
        experience = profile.get('experience', 'Любитель')
        goal = profile.get('goal', 'Финишировать')
        target_time = profile.get('target_time', 'Неизвестно')
        fitness_level = profile.get('fitness_level', 'Средний')
        comfortable_pace = profile.get('comfortable_pace', 'Неизвестно')
        weekly_volume = profile.get('weekly_volume_text', profile.get('weekly_volume', 'Неизвестно'))
        training_days = profile.get('training_days_per_week', '3')
        
        # Формируем пользовательский запрос
        user_prompt = f"""Составь персонализированный план беговых тренировок на 7 дней для бегуна со следующим профилем:

Целевая дистанция: {distance}
Дата соревнования: {competition_date}
Пол: {gender}
Возраст: {age}
Рост: {height} см
Вес: {weight} кг
Опыт бега: {experience}
Цель: {goal}
Целевое время: {target_time}
Уровень физической подготовки: {fitness_level}
Комфортный темп бега: {comfortable_pace} мин/км
Еженедельный объем бега: {weekly_volume} км
Количество тренировок в неделю: {training_days}

План должен включать:
1. День и тип тренировки
2. Дистанцию и целевой темп или пульс
3. Детальное описание выполнения
4. Рекомендации по подготовке и восстановлению
5. Общий недельный объем и его распределение

Для плана используй методики Джека Дэниелса (Jack Daniels), Стива Магнесса (Steve Magness) и принципы периодизации Тудора Бомпы (Tudor Bompa).

Ответ предоставь в формате JSON следующей структуры:
{"plan_name": "Название плана", "plan_description": "Общее описание плана и его целей", "weekly_volume": 30, "intensity_distribution": "70% легкие, 20% средние, 10% высокоинтенсивные тренировки", "training_days": [{"day": 1, "day_of_week": "Понедельник", "workout_type": "Легкий бег", "distance": 5, "pace": "6:30-7:00", "heart_rate": "65-75% от максимума", "description": "Подробное описание тренировки", "purpose": "Цель этой тренировки"}], "rest_days": [{"day": 3, "day_of_week": "Среда", "activity": "Полный отдых или растяжка", "purpose": "Восстановление мышц и суставов"}], "recommendations": {"nutrition": "Рекомендации по питанию", "recovery": "Рекомендации по восстановлению", "progression": "Как модифицировать план в будущем"}}
"""
        
        # Формируем сообщения для API
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        return messages
    
    def get_training_plan(self, profile):
        """
        Получает тренировочный план через OpenAI API
        
        Args:
            profile: Словарь с данными профиля бегуна
            
        Returns:
            dict: Данные плана тренировок
        """
        try:
            # Создаем промпт
            messages = self.create_training_plan_prompt(profile)
            
            # Логируем отправляемый запрос
            logger.info("Отправляем запрос к OpenAI с промптом")
            
            # Отправляем запрос к API
            response = self.client.chat.completions.create(
                model=MODEL,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.7
            )
            
            # Получаем и распарсиваем ответ
            content = response.choices[0].message.content
            plan = json.loads(content)
            
            logger.info("Получен план тренировок успешно")
            return plan
            
        except Exception as e:
            logger.error(f"Ошибка при получении плана тренировок: {e}")
            raise

def test_prompt():
    """
    Тестирует промпт на примере профиля бегуна
    """
    try:
        # Тестовый профиль бегуна
        test_profile = {
            "distance": "10 км",
            "competition_date": "2025-07-15",
            "gender": "Мужской",
            "age": 35,
            "height": 180,
            "weight": 75,
            "experience": "Любитель",
            "goal": "Финишировать",
            "target_time": "50 минут",
            "fitness_level": "Средний",
            "comfortable_pace": "5:30-6:30",
            "weekly_volume": 20,
            "training_days_per_week": 3
        }
        
        # Создаем генератор промптов
        generator = CoachingPromptGenerator()
        
        # Получаем тренировочный план
        plan = generator.get_training_plan(test_profile)
        
        # Сохраняем план в файл для анализа
        with open(f'test_training_plan_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json', 'w', encoding='utf-8') as f:
            json.dump(plan, f, ensure_ascii=False, indent=2)
        
        print("\nТестовый план тренировок успешно создан и сохранен!")
        print(f"Название плана: {plan.get('plan_name')}")
        print(f"Общий объем: {plan.get('weekly_volume')} км")
        print("\nРаспределение тренировок:")
        
        for day in plan.get('training_days', []):
            print(f"День {day.get('day')}: {day.get('day_of_week')} - {day.get('workout_type')} ({day.get('distance')} км)")
        
        print("\nРекомендации:")
        recommendations = plan.get('recommendations', {})
        for key, value in recommendations.items():
            short_value = value[:50] + "..." if isinstance(value, str) and len(value) > 50 else value
            print(f"- {key.capitalize()}: {short_value}")
        
    except Exception as e:
        logger.error(f"Ошибка при тестировании промпта: {e}")
        print(f"Произошла ошибка: {e}")

if __name__ == "__main__":
    # Создаем директорию для логов
    os.makedirs('logs', exist_ok=True)
    
    # Запускаем тест промпта
    test_prompt()