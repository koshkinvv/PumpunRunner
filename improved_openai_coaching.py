#!/usr/bin/env python3
"""
Модуль для улучшенного взаимодействия с OpenAI API для создания 
персонализированных планов тренировок на основе методик ведущих книг по бегу.

Использует:
- Методики Jack Daniels из книги "Training Distance Runners"
- Принципы Steve Magness из книги "Science of Running"
- Периодизацию Tudor Bompa из книги "Periodization Training for Sports"
- Подходы Brad Stulberg & Steve Magness из книги "Peak Performance"
"""
import os
import json
import logging
from datetime import datetime, timedelta
import pytz
from typing import Dict, Any

# the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
# do not change this unless explicitly requested by the user
MODEL = "gpt-4o"

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/coach_prompt_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("coach_prompt")

# Проверяем наличие OpenAI
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    logger.error("Не удалось импортировать библиотеку OpenAI. Установите ее: pip install openai")
    OPENAI_AVAILABLE = False

class ImprovedCoachingService:
    """Улучшенный сервис для генерации планов тренировок по бегу"""
    
    def __init__(self):
        """Инициализация сервиса с OpenAI API"""
        if not OPENAI_AVAILABLE:
            raise ImportError("Библиотека OpenAI не установлена")
            
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY не найден в переменных окружения")
            
        self.client = OpenAI(api_key=api_key)
        logger.info("Инициализирован улучшенный сервис тренерских планов")
        
        # Для работы с датами используем московское время
        self.moscow_tz = pytz.timezone('Europe/Moscow')
    
    def get_enhanced_system_prompt(self) -> str:
        """
        Возвращает улучшенный системный промпт на основе ведущих книг по тренерству и бегу.
        
        Returns:
            str: Системный промпт для модели
        """
        return """Ты опытный тренер по бегу, эксперт с глубокими знаниями передовых методик тренировок, 
основанных на лучших книгах и исследованиях:

• Jack Daniels ("Training Distance Runners") - разработал формулы расчета VDOT и нагрузки, определил оптимальные пульсовые зоны
• Steve Magness ("Science of Running") - исследовал физиологию бега и психологию подготовки на научной основе
• Tudor Bompa ("Periodization Training for Sports") - создал принципы периодизации тренировок для достижения пика формы к соревнованиям
• Brad Stulberg & Steve Magness ("Peak Performance") - разработали методики достижения пиковых состояний с учетом восстановления
• David Joyce & Daniel Lewindon ("High-Performance Training for Sports") - систематизировали современные методы спортивной подготовки

При составлении тренировочных планов ты:

1) Тщательно анализируешь профиль бегуна:
   - Физические параметры (пол, возраст, вес, рост) для корректировки нагрузок
   - Текущий уровень подготовки и опыт для выбора подходящих тренировок
   - Целевую дистанцию и дату соревнования для расчета периодизации
   - Целевое время и темп для определения оптимальных тренировочных зон
   - Комфортный темп и недельный объем для оценки текущего уровня

2) Создаешь научно-обоснованные планы, включая:
   - Прогрессивное увеличение нагрузки с соблюдением принципа суперкомпенсации
   - Чередование типов тренировок разной интенсивности (80:20 правило)
   - Разнообразие тренировок: длительные аэробные, темповые, интервальные, восстановительные
   - Адаптацию тренировок к уровню бегуна с допустимым темпом прогресса 5-10% в неделю
   - Использование формул Джека Дэниелса для расчета оптимальных зон интенсивности

3) Даешь практические рекомендации по:
   - Темпам бега для каждого типа тренировок (с учетом физиологических зон)
   - Технике выполнения упражнений и профилактике травм
   - Восстановлению между тренировками, включая сон и питание
   - Корректировке плана при отклонениях от графика
   - Ментальной подготовке к соревнованиям

Твоя задача - создать персонализированный план, который поможет бегуну достичь цели безопасно и эффективно, с учетом научных принципов и практического опыта тренерской работы.

ВАЖНО: План тренировок должен включать ТОЛЬКО УКАЗАННЫЕ ДАТЫ и ДНИ НЕДЕЛИ. 
НЕ ДОБАВЛЯЙ дополнительные дни тренировок кроме указанных."""
    
    def calculate_training_dates(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Рассчитывает оптимальные даты для тренировок на основе профиля бегуна
        
        Args:
            profile: Словарь с данными профиля бегуна
            
        Returns:
            Dict: Информация о датах тренировок
        """
        try:
            # Проверяем, указал ли пользователь дату начала тренировок
            user_start_date = profile.get('training_start_date_text', profile.get('training_start_date', None))
            
            # Попытка распарсить дату начала тренировок
            start_date = None
            
            if user_start_date and user_start_date.lower() != 'сегодня' and user_start_date.lower() != 'не знаю':
                try:
                    # Попробуем распарсить дату в нескольких форматах
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
                    logger.error(f"Ошибка при парсинге даты начала тренировок: {e}")
            
            # Если не удалось распарсить дату или она не была указана, используем текущую дату
            if not start_date:
                start_date = datetime.now(pytz.UTC).astimezone(self.moscow_tz)
                logger.info(f"Используем текущую дату: {start_date.strftime('%d.%m.%Y')}")
            
            # Получаем предпочитаемые дни тренировок
            preferred_days_str = profile.get('preferred_training_days', '')
            preferred_days = []
            
            if preferred_days_str:
                # Словарь для преобразования сокращений дней недели в числа (0 - понедельник, 6 - воскресенье)
                day_name_to_number = {
                    'пн': 0, 'вт': 1, 'ср': 2, 'чт': 3, 'пт': 4, 'сб': 5, 'вс': 6,
                    'понедельник': 0, 'вторник': 1, 'среда': 2, 'четверг': 3, 
                    'пятница': 4, 'суббота': 5, 'воскресенье': 6
                }
                
                # Разбиваем строку предпочитаемых дней и преобразуем в числа
                for day in preferred_days_str.lower().split(','):
                    day = day.strip()
                    if day in day_name_to_number:
                        preferred_days.append(day_name_to_number[day])
            
            # Если предпочитаемые дни не указаны, используем все дни недели
            if not preferred_days:
                preferred_days = list(range(7))  # 0 - понедельник, 6 - воскресенье
            
            # Количество тренировочных дней в неделю (по умолчанию 3)
            training_days_count = int(profile.get('training_days_per_week', 3))
            
            # Убедимся, что у нас достаточно дней для тренировок
            if len(preferred_days) < training_days_count:
                for i in range(7):
                    if i not in preferred_days:
                        preferred_days.append(i)
                        if len(preferred_days) >= training_days_count:
                            break
            
            # Если указано больше предпочитаемых дней, чем нужно для тренировок, используем первые N дней
            if len(preferred_days) > training_days_count:
                preferred_days = preferred_days[:training_days_count]
            
            # Сортируем дни недели, чтобы они шли по порядку
            preferred_days.sort()
            
            # Проверяем, если стартовая дата раньше текущей даты, используем текущую
            now = datetime.now(pytz.UTC).astimezone(self.moscow_tz)
            current_date = start_date
            if current_date.date() < now.date():
                current_date = now
            
            # Получаем день недели для стартовой даты (0 - понедельник, 6 - воскресенье)
            start_weekday = current_date.weekday()
            
            # Находим первый подходящий день для начала тренировок
            days_to_add = 0
            if preferred_days:
                # Ищем ближайший предпочитаемый день недели, начиная со стартовой даты
                min_days_to_add = float('inf')
                for day in preferred_days:
                    # Вычисляем, сколько дней нужно добавить к стартовой дате
                    days = (day - start_weekday) % 7
                    if days < min_days_to_add:
                        min_days_to_add = days
                
                days_to_add = min_days_to_add
            
            # Добавляем дни к стартовой дате, чтобы получить первый день тренировки
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
                    logger.info(f"Добавлена дата тренировки: {date_to_check.strftime('%d.%m.%Y (%A)')}")
                
                date_to_check = date_to_check + timedelta(days=1)
            
            # Словарь для названий дней недели
            day_number_to_name = {
                0: "Понедельник", 
                1: "Вторник", 
                2: "Среда", 
                3: "Четверг", 
                4: "Пятница", 
                5: "Суббота", 
                6: "Воскресенье"
            }
            
            # Формируем окончательный словарь с информацией о тренировочных днях
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
            
            # Возвращаем результат
            return {
                "start_date": start_date.strftime("%d.%m.%Y"),
                "preferred_days": preferred_days,
                "training_days_count": training_days_count,
                "training_dates": training_dates_info
            }
            
        except Exception as e:
            logger.error(f"Ошибка при расчете дат тренировок: {e}")
            raise
    
    def generate_enhanced_plan(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Генерирует улучшенный план тренировок с использованием OpenAI API
        
        Args:
            profile: Словарь с данными профиля бегуна
            
        Returns:
            Dict: Структурированный план тренировок
        """
        try:
            # Получаем системный промпт
            system_prompt = self.get_enhanced_system_prompt()
            
            # Рассчитываем даты тренировок
            dates_info = self.calculate_training_dates(profile)
            
            # Преобразуем профиль в строку для промпта
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
            
            if profile.get('goal') == 'Улучшить время':
                profile_text += f"- Целевое время: {profile.get('target_time', 'Неизвестно')}\n"
                
            profile_text += (
                f"- Уровень физической подготовки: {profile.get('fitness_level', 'Средний')}\n"
                f"- Комфортный темп бега: {profile.get('comfortable_pace', 'Неизвестно')} мин/км\n"
                f"- Еженедельный объем бега: {profile.get('weekly_volume_text', profile.get('weekly_volume', 'Неизвестно'))} км\n"
                f"- Количество тренировок в неделю: {profile.get('training_days_per_week', '3')}\n"
            )
            
            # Информация о датах тренировок
            dates_text = "Расписание тренировок:\n"
            for date_info in dates_info['training_dates']:
                dates_text += f"- {date_info['weekday']} ({date_info['date']})\n"
            
            # Формируем инструкцию для формата ответа
            format_text = """
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
            
            # Объединяем всё в один пользовательский запрос
            user_prompt = f"{profile_text}\n\n{dates_text}\n\n{format_text}"
            
            logger.info("Отправляем запрос к OpenAI для генерации улучшенного плана тренировок")
            
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
            
            # Получаем и распарсиваем ответ
            content = response.choices[0].message.content
            logger.info("Получен ответ от OpenAI API")
            
            # Преобразуем в JSON
            plan = json.loads(content)
            logger.info(f"План успешно преобразован в JSON формат: {len(str(plan))} символов")
            
            # Добавляем метаданные
            plan["generated_with"] = "enhanced_coach_prompt"
            plan["generated_at"] = datetime.now().isoformat()
            plan["training_dates_info"] = dates_info
            
            return plan
            
        except Exception as e:
            logger.error(f"Ошибка при генерации улучшенного плана тренировок: {e}")
            raise

# Функция для интеграции с существующим кодом
def generate_enhanced_training_plan(runner_profile):
    """
    Генерирует улучшенный план тренировок для указанного профиля бегуна
    используя усовершенствованный промпт на основе книг
    
    Args:
        runner_profile: Словарь с профилем бегуна
        
    Returns:
        Словарь с планом тренировок в формате, совместимом с существующим кодом
    """
    try:
        # Создаем сервис для генерации планов
        coach_service = ImprovedCoachingService()
        
        # Генерируем план
        enhanced_plan = coach_service.generate_enhanced_plan(runner_profile)
        
        # Возвращаем результат
        return enhanced_plan
    
    except Exception as e:
        logger.error(f"Ошибка при вызове улучшенного генератора планов: {e}")
        # В случае ошибки возвращаем None, чтобы вызывающий код мог использовать запасной метод
        return None

if __name__ == "__main__":
    # Тестирование генерации плана
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
        "training_days_per_week": 4,
        "preferred_training_days": "Пн, Ср, Пт, Вс"
    }
    
    try:
        # Генерируем план
        plan = generate_enhanced_training_plan(test_profile)
        
        # Сохраняем план в файл
        if plan:
            filename = f"test_plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(plan, f, ensure_ascii=False, indent=2)
            print(f"План сохранен в файл: {filename}")
        else:
            print("Не удалось сгенерировать план")
    
    except Exception as e:
        print(f"Произошла ошибка: {e}")