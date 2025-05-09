#!/usr/bin/env python3
"""
Интеграционный модуль для улучшенного генератора планов тренировок по бегу
с использованием методик из ведущих книг по тренерскому искусству и легкой атлетике.

Включает:
- Системный промпт на основе книг Jack Daniels, Steve Magness, Tudor Bompa и др.
- Логику генерации персонализированных 7-дневных тренировочных планов
- Функции для интеграции с Telegram-ботом и сохранения планов в БД
"""
import os
import json
import logging
from datetime import datetime, timedelta
import pytz
from typing import Dict, Any, List, Optional

# the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
# do not change this unless explicitly requested by the user
MODEL = "gpt-4o"

# Настройка логирования
os.makedirs('logs', exist_ok=True)
log_file = f'logs/coach_prompt_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("coach_prompt")

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    logger.error("Не удалось импортировать библиотеку OpenAI. Установите ее: pip install openai")
    OPENAI_AVAILABLE = False

class RunningCoachPrompt:
    """Генератор промптов для беговых тренировок на основе ведущих методик"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Инициализирует генератор промптов для тренировочных планов
        
        Args:
            api_key: Ключ API OpenAI (опционально)
        """
        if not OPENAI_AVAILABLE:
            raise ImportError("Библиотека OpenAI не установлена")
            
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("API ключ OpenAI не предоставлен и не найден в переменных окружения")
            
        self.client = OpenAI(api_key=self.api_key)
        
        # Московское время для работы с датами
        self.moscow_tz = pytz.timezone('Europe/Moscow')
        
        logger.info("Инициализирован генератор тренировочных планов")
    
    def get_expert_system_prompt(self) -> str:
        """
        Возвращает системный промпт для тренера по бегу,
        основанный на ведущих книгах и методиках.
        
        Returns:
            str: Системный промпт
        """
        return """Ты — персональный тренер по бегу, эксперт с глубокими знаниями методик из книг:

• Jack Daniels ("Training Distance Runners") - формулы VDOT, пульсовые зоны, периодизация нагрузки
• Steve Magness ("Science of Running") - физиология бега, нейромышечная адаптация
• Tudor Bompa ("Periodization Training for Sports") - блоковая периодизация тренировок
• Brad Stulberg & Steve Magness ("Peak Performance") - управление стрессом и восстановлением
• David Joyce & Daniel Lewindon ("High-Performance Training for Sports") - комплексный подход 

При составлении планов ты учитываешь:
- Целевую дистанцию и дату соревнования (для расчета фаз подготовки)
- Возраст, пол, рост и вес (для корректировки нагрузок)
- Уровень подготовки и опыт бега (для выбора типов тренировок)
- Текущий километраж и комфортный темп (для определения базового уровня)
- Цель бегуна (для создания специфичной структуры плана)
- Последние тренировки и самочувствие (для адаптации плана)

Ты создаешь научно-обоснованные планы, где:
1. Соблюдаются принципы прогрессивной нагрузки (5-10% в неделю)
2. Используется соотношение 80% легких и 20% интенсивных тренировок
3. Каждая тренировка имеет четкую цель и физиологическое обоснование
4. Предусмотрены восстановительные дни и адаптация к нагрузкам
5. Учитываются предпочтительные дни для тренировок

План должен включать:
- День недели и календарную дату для каждой тренировки
- Тип тренировки (интервалы, темп, восстановление и т.д.)
- Точный километраж и рекомендуемые темпы бега
- Целевые пульсовые зоны для каждой тренировки
- Подробное описание выполнения упражнений
- Рекомендации по питанию и восстановлению

Формируй план на точно 7 дней, начиная с указанной даты, следуя предпочтительным дням тренировок пользователя."""
    
    def get_basic_system_prompt(self) -> str:
        """
        Возвращает упрощенный системный промпт для генерации плана.
        Используется как запасной вариант.
        
        Returns:
            str: Упрощенный системный промпт
        """
        return """Ты — персональный тренер по бегу, обученный по методикам Джек Дэниелса, Стива Магнесса и Тюдора Бомпы. 
Твоя задача — создавать индивидуальные планы тренировок по бегу на 7 дней, адаптированные под:
- Цель пользователя (марафон, 10 км, улучшение формы и т.д.)
- Текущий уровень подготовки (начинающий, любитель, продвинутый)
- Возраст, пол, рост и вес
- Текущий недельный объём бега
- Комфортный темп бега
- Общую мотивацию и самочувствие

Правила:
- Всегда давай рекомендации на точно 7 дней вперёд
- Указывай тип тренировки (интервалы, темп, кросс, восстановление и т.д.)
- Добавляй километраж, темп, уровень пульса и цель на день
- Объясняй ключевые акценты недели и мотивируй
- Учитывай дни отдыха и адаптацию при усталости или пропусках
- Используй только указанные даты для тренировок"""
    
    def calculate_training_dates(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Рассчитывает даты тренировок на основе предпочтений из профиля.
        
        Args:
            profile: Профиль бегуна
            
        Returns:
            Dict: Информация о датах тренировок
        """
        try:
            # Получаем дату начала тренировок из профиля
            user_start_date = profile.get('training_start_date_text', profile.get('training_start_date', None))
            
            # Пытаемся распарсить дату начала
            start_date = None
            
            if user_start_date and user_start_date.lower() not in ['сегодня', 'не знаю']:
                try:
                    # Пробуем разные форматы даты
                    formats = ["%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d.%m"]
                    
                    for fmt in formats:
                        try:
                            if fmt == "%d.%m":
                                # Для формата без года добавляем текущий год
                                current_year = datetime.now().year
                                date_with_year = f"{user_start_date}.{current_year}"
                                start_date = datetime.strptime(date_with_year, "%d.%m.%Y")
                            else:
                                start_date = datetime.strptime(user_start_date, fmt)
                            
                            start_date = self.moscow_tz.localize(start_date)
                            logger.info(f"Успешно распарсили дату: {start_date.strftime('%d.%m.%Y')}")
                            break
                        except ValueError:
                            continue
                except Exception as e:
                    logger.error(f"Ошибка при парсинге даты: {e}")
            
            # Если дата не указана или не удалось распарсить, используем текущую
            if not start_date:
                start_date = datetime.now(pytz.UTC).astimezone(self.moscow_tz)
                logger.info(f"Используем текущую дату: {start_date.strftime('%d.%m.%Y')}")
            
            # Получаем предпочитаемые дни тренировок
            preferred_days_str = profile.get('preferred_training_days', '')
            preferred_days = []
            
            # Словарь для преобразования названий дней в числа
            day_name_to_number = {
                'пн': 0, 'вт': 1, 'ср': 2, 'чт': 3, 'пт': 4, 'сб': 5, 'вс': 6,
                'понедельник': 0, 'вторник': 1, 'среда': 2, 'четверг': 3, 
                'пятница': 4, 'суббота': 5, 'воскресенье': 6
            }
            
            # Обратный словарь для преобразования чисел в названия дней
            day_number_to_name = {
                0: "Понедельник", 
                1: "Вторник", 
                2: "Среда", 
                3: "Четверг", 
                4: "Пятница", 
                5: "Суббота", 
                6: "Воскресенье"
            }
            
            # Парсим предпочитаемые дни
            if preferred_days_str:
                for day in preferred_days_str.lower().split(','):
                    day = day.strip()
                    if day in day_name_to_number:
                        preferred_days.append(day_name_to_number[day])
            
            # Если дни не указаны, используем все дни недели
            if not preferred_days:
                preferred_days = list(range(7))
            
            # Количество тренировочных дней
            training_days_count = int(profile.get('training_days_per_week', 3))
            
            # Убедимся, что у нас достаточно дней для тренировок
            if len(preferred_days) < training_days_count:
                for i in range(7):
                    if i not in preferred_days:
                        preferred_days.append(i)
                        if len(preferred_days) >= training_days_count:
                            break
            
            # Если указано больше предпочитаемых дней, чем нужно, используем первые N
            if len(preferred_days) > training_days_count:
                preferred_days = preferred_days[:training_days_count]
            
            # Сортируем дни
            preferred_days.sort()
            
            # Проверяем, если дата в прошлом - используем текущую
            now = datetime.now(pytz.UTC).astimezone(self.moscow_tz)
            current_date = start_date
            if current_date.date() < now.date():
                current_date = now
                logger.info(f"Стартовая дата в прошлом, используем текущую: {current_date.strftime('%d.%m.%Y')}")
            
            # День недели для стартовой даты
            start_weekday = current_date.weekday()
            
            # Находим первый подходящий день для начала тренировок
            days_to_add = 0
            if preferred_days:
                # Ищем ближайший предпочитаемый день недели
                min_days_to_add = float('inf')
                for day in preferred_days:
                    # Количество дней до следующего предпочитаемого дня
                    days = (day - start_weekday) % 7
                    if days < min_days_to_add:
                        min_days_to_add = days
                
                days_to_add = min_days_to_add
            
            # Первый день тренировки
            first_training_date = current_date + timedelta(days=days_to_add)
            
            # Генерируем даты для всех тренировочных дней
            training_dates = []
            date_to_check = first_training_date
            training_day_counter = 0
            
            while training_day_counter < training_days_count:
                weekday = date_to_check.weekday()
                
                if weekday in preferred_days:
                    training_dates.append(date_to_check)
                    training_day_counter += 1
                
                date_to_check = date_to_check + timedelta(days=1)
            
            # Создаем информацию о тренировочных днях
            training_dates_info = []
            
            for date in training_dates:
                weekday_num = date.weekday()
                weekday_name = day_number_to_name[weekday_num]
                date_str = date.strftime("%d.%m.%Y")
                training_dates_info.append({
                    "date": date_str,
                    "weekday": weekday_name,
                    "weekday_num": weekday_num
                })
            
            # Преобразуем предпочитаемые дни в названия для лога
            preferred_days_names = [day_number_to_name[day] for day in preferred_days]
            preferred_days_text = ", ".join(preferred_days_names)
            
            logger.info(f"Предпочитаемые дни: {preferred_days_text}")
            logger.info(f"Даты тренировок: {[d['date'] for d in training_dates_info]}")
            
            # Создаем результат
            return {
                "start_date": start_date.strftime("%d.%m.%Y"),
                "preferred_days": preferred_days,
                "preferred_days_text": preferred_days_text,
                "training_days_count": training_days_count,
                "training_dates": training_dates_info,
                "first_training_date": first_training_date.strftime("%d.%m.%Y")
            }
            
        except Exception as e:
            logger.error(f"Ошибка при расчете дат тренировок: {e}")
            
            # В случае ошибки возвращаем базовую информацию
            return {
                "start_date": datetime.now().strftime("%d.%m.%Y"),
                "training_days_count": 3,
                "training_dates": []
            }
    
    def create_user_prompt(self, profile: Dict[str, Any], dates_info: Dict[str, Any]) -> str:
        """
        Создает пользовательский промпт для запроса к OpenAI
        с учетом профиля бегуна и рассчитанных дат.
        
        Args:
            profile: Профиль бегуна
            dates_info: Информация о датах тренировок
            
        Returns:
            str: Пользовательский промпт
        """
        # Форматируем основную информацию о профиле
        profile_text = (
            f"Профиль бегуна:\n"
            f"- Целевая дистанция: {profile.get('distance', 'Неизвестно')}\n"
            f"- Дата соревнования: {profile.get('competition_date', 'Неизвестно')}\n"
            f"- Пол: {profile.get('gender', 'Неизвестно')}\n"
            f"- Возраст: {profile.get('age', 'Неизвестно')}\n"
            f"- Рост: {profile.get('height', 'Неизвестно')} см\n"
            f"- Вес: {profile.get('weight', 'Неизвестно')} кг\n"
            f"- Опыт бега: {profile.get('experience', 'Начинающий')}\n"
            f"- Цель: {profile.get('goal', 'Финишировать')}\n"
        )
        
        # Добавляем информацию о целевом времени, если указана цель "Улучшить время"
        if profile.get('goal') == 'Улучшить время':
            profile_text += f"- Целевое время: {profile.get('target_time', 'Неизвестно')}\n"
            
        profile_text += (
            f"- Уровень физической подготовки: {profile.get('fitness_level', 'Средний')}\n"
            f"- Комфортный темп бега: {profile.get('comfortable_pace', 'Неизвестно')} мин/км\n"
            f"- Еженедельный объем бега: {profile.get('weekly_volume_text', profile.get('weekly_volume', 'Неизвестно'))} км\n"
            f"- Количество тренировок в неделю: {profile.get('training_days_per_week', '3')}\n"
            f"- Предпочитаемые дни тренировок: {dates_info.get('preferred_days_text', 'Не указаны')}\n"
        )
        
        # Информация о датах тренировок
        dates_text = "Расписание тренировок:\n"
        for date_info in dates_info.get('training_dates', []):
            dates_text += f"- {date_info['weekday']} ({date_info['date']})\n"
        
        # Форматируем инструкцию для формата ответа в JSON
        format_instruction = """
План должен быть представлен в формате JSON со следующей структурой:
{
  "plan_name": "Название плана",
  "plan_description": "Общее описание плана и его целей",
  "weekly_volume": число,
  "intensity_distribution": "70% легкие, 20% средние, 10% высокоинтенсивные тренировки",
  "training_days": [
    {
      "day": 1,
      "day_of_week": "Понедельник",
      "date": "13.05.2025",
      "workout_type": "Легкий бег",
      "distance": 5,
      "pace": "6:30-7:00",
      "heart_rate": "65-75% от максимума",
      "description": "Подробное описание тренировки",
      "purpose": "Цель этой тренировки"
    }
  ],
  "rest_days": [
    {
      "day": 3,
      "day_of_week": "Среда",
      "date": "15.05.2025",
      "activity": "Полный отдых или растяжка",
      "purpose": "Восстановление мышц и суставов"
    }
  ],
  "recommendations": {
    "nutrition": "Рекомендации по питанию",
    "recovery": "Рекомендации по восстановлению",
    "progression": "Как модифицировать план в будущем"
  }
}
"""
        
        # Объединяем всё в финальный промпт
        final_prompt = f"{profile_text}\n\n{dates_text}\n\n{format_instruction}"
        return final_prompt
    
    def generate_training_plan(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Генерирует тренировочный план с использованием OpenAI API
        на основе профиля бегуна и рассчитанных дат.
        
        Args:
            profile: Профиль бегуна
            
        Returns:
            Dict: Сгенерированный план тренировок
        """
        try:
            # Рассчитываем даты тренировок
            dates_info = self.calculate_training_dates(profile)
            
            # Получаем системный промпт
            system_prompt = self.get_expert_system_prompt()
            
            # Создаем пользовательский промпт
            user_prompt = self.create_user_prompt(profile, dates_info)
            
            logger.info("Отправляем запрос к OpenAI для генерации плана тренировок")
            
            # Отправляем запрос к API
            response = self.client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.7
            )
            
            # Получаем и обрабатываем ответ
            content = response.choices[0].message.content
            logger.info("Получен ответ от OpenAI API")
            
            # Преобразуем в JSON
            plan = json.loads(content)
            logger.info(f"План успешно преобразован в JSON формат: {len(str(plan))} символов")
            
            # Добавляем метаданные
            plan["generated_with"] = "improved_coach_prompt_v1"
            plan["generated_at"] = datetime.now().isoformat()
            plan["training_dates_info"] = dates_info
            
            return plan
            
        except Exception as e:
            logger.error(f"Ошибка при генерации плана тренировок: {e}")
            
            # В случае ошибки пробуем запасной вариант
            try:
                return self.generate_fallback_plan(profile)
            except Exception as fallback_error:
                logger.error(f"Ошибка при использовании запасного варианта: {fallback_error}")
                raise
    
    def generate_fallback_plan(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Запасной метод генерации плана тренировок на случай ошибки основного метода.
        Использует упрощенный промпт и базовые параметры.
        
        Args:
            profile: Профиль бегуна
            
        Returns:
            Dict: Сгенерированный план тренировок
        """
        logger.info("Использую запасной метод генерации плана")
        
        # Получаем упрощенный системный промпт
        system_prompt = self.get_basic_system_prompt()
        
        # Упрощенный пользовательский промпт
        user_prompt = (
            f"Возраст: {profile.get('age', 'Не указан')}\n"
            f"Пол: {profile.get('gender', 'Не указан')}\n"
            f"Рост: {profile.get('height', 'Не указан')} см\n"
            f"Вес: {profile.get('weight', 'Не указан')} кг\n"
            f"Текущий уровень: {profile.get('experience', 'любитель')}\n"
            f"Бегаю {profile.get('weekly_volume', 10)} км в неделю\n"
            f"Цель: {profile.get('goal', 'улучшение формы')}\n"
            f"Комфортный темп: {profile.get('comfortable_pace', 'Не указан')}\n"
            f"Общее самочувствие: нормальное\n\n"
            f"Создай план тренировок на 7 дней в формате JSON с полями:\n"
            f"- plan_name: название плана\n"
            f"- plan_description: описание плана\n"
            f"- training_days: массив тренировочных дней с датами\n"
            f"- rest_days: массив дней отдыха\n"
            f"- recommendations: рекомендации по питанию и восстановлению"
        )
        
        # Отправляем запрос
        response = self.client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.7
        )
        
        # Обрабатываем ответ
        content = response.choices[0].message.content
        plan = json.loads(content)
        
        # Добавляем метаданные
        plan["generated_with"] = "fallback_coach_prompt"
        plan["generated_at"] = datetime.now().isoformat()
        
        return plan

# Функция для интеграции с существующим кодом
def generate_improved_training_plan(runner_profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Функция для генерации улучшенного плана тренировок
    для интеграции с существующим кодом бота.
    
    Args:
        runner_profile: Словарь с профилем бегуна
        
    Returns:
        Dict: План тренировок в формате, совместимом с существующим кодом
    """
    try:
        coach = RunningCoachPrompt()
        plan = coach.generate_training_plan(runner_profile)
        return plan
    except Exception as e:
        logger.error(f"Ошибка при генерации улучшенного плана: {e}")
        # В случае ошибки вернем None, чтобы вызывающий код мог использовать старый метод
        return None

# Пример использования
if __name__ == "__main__":
    # Тестовый профиль бегуна
    test_profile = {
        "distance": "10 км", 
        "competition_date": "2025-07-15",
        "gender": "Мужской",
        "age": 35,
        "height": 180,
        "weight": 75,
        "experience": "Любитель",
        "goal": "Улучшить время",
        "target_time": "50 минут",
        "fitness_level": "Средний",
        "comfortable_pace": "5:30-6:30",
        "weekly_volume": 20,
        "training_days_per_week": 3,
        "preferred_training_days": "Пн, Ср, Пт"
    }
    
    try:
        # Генерируем и сохраняем план
        plan = generate_improved_training_plan(test_profile)
        
        if plan:
            # Сохраняем в файл для тестирования
            filename = f"test_plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(plan, f, ensure_ascii=False, indent=2)
            print(f"План сохранен в файл: {filename}")
            
            # Выводим базовую информацию о плане
            print(f"\nНазвание плана: {plan.get('plan_name')}")
            print(f"Общий объем: {plan.get('weekly_volume')} км")
            print(f"Распределение интенсивности: {plan.get('intensity_distribution')}")
            
            print("\nТренировочные дни:")
            for day in plan.get('training_days', []):
                print(f"- {day.get('day_of_week')} ({day.get('date')}): {day.get('workout_type')} {day.get('distance')} км")
        else:
            print("Не удалось сгенерировать план")
    
    except Exception as e:
        print(f"Произошла ошибка: {e}")