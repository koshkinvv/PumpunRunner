#!/usr/bin/env python3
"""
Финальная версия промпта для генерации персонализированных планов тренировок
с использованием OpenAI GPT-4o модели. 

Включает знания из ведущих книг по тренерскому искусству и лёгкой атлетике,
исправлены ошибки форматирования и обработки JSON, улучшен формат вывода.
"""
import os
import sys
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List

# the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
# do not change this unless explicitly requested by the user
MODEL = "gpt-4o"

# Настройка логирования
os.makedirs('logs', exist_ok=True)
log_file = f'logs/coach_prompt_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
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

class CoachPrompt:
    """Генератор улучшенных промптов для тренировочных планов по бегу"""
    
    def __init__(self):
        """Инициализация генератора промптов"""
        if not OPENAI_AVAILABLE:
            raise ImportError("Библиотека OpenAI не установлена")
            
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY не найден в переменных окружения")
            
        self.client = OpenAI(api_key=api_key)
        logger.info("Инициализирован генератор тренерских промптов")
    
    def get_system_prompt(self) -> str:
        """
        Возвращает системный промпт с информацией для модели OpenAI,
        основанный на книгах по тренерству и бегу.
        
        Использованные источники:
        - "Training Distance Runners" (Jack Daniels)
        - "Science of Running" (Steve Magness)
        - "Periodization Training for Sports" (Tudor Bompa)
        - "Peak Performance" (Brad Stulberg & Steve Magness)
        - "High-Performance Training for Sports" (David Joyce & Daniel Lewindon)
        
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

Твоя задача - создать персонализированный план, который поможет бегуну достичь цели безопасно и эффективно, с учетом научных принципов и практического опыта тренерской работы."""
    
    def get_user_prompt(self, profile: Dict[str, Any]) -> str:
        """
        Создает пользовательский промпт на основе профиля бегуна
        
        Args:
            profile: Словарь с данными профиля бегуна
            
        Returns:
            str: Пользовательский промпт для запроса
        """
        # Извлекаем данные профиля с защитой от None
        distance = profile.get('distance', 'Неизвестно')
        competition_date = profile.get('competition_date', 'Неизвестно')
        gender = profile.get('gender', 'Неизвестно')
        age = str(profile.get('age', 'Неизвестно'))
        height = str(profile.get('height', 'Неизвестно'))
        weight = str(profile.get('weight', 'Неизвестно'))
        experience = profile.get('experience', 'Начинающий')
        goal = profile.get('goal', 'Финишировать')
        target_time = profile.get('target_time', 'Неизвестно')
        fitness_level = profile.get('fitness_level', 'Средний')
        comfortable_pace = profile.get('comfortable_pace', 'Неизвестно')
        weekly_volume = profile.get('weekly_volume_text', str(profile.get('weekly_volume', 'Неизвестно')))
        training_days = str(profile.get('training_days_per_week', '3'))
        
        # Формируем пользовательский запрос
        prompt = f"""Составь персонализированный план беговых тренировок на 7 дней для бегуна со следующим профилем:

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
1. Конкретные дни недели с датами тренировок (начиная с понедельника)
2. Дистанцию и целевой темп для каждой тренировки
3. Оптимальный пульсовой диапазон 
4. Детальное описание выполнения с тактикой
5. Общий недельный объем и его распределение

Ответ должен быть в формате JSON со следующими полями:
- "plan_name": название плана
- "plan_description": описание цели и особенностей плана
- "weekly_volume": общий объем за неделю в км (число)
- "intensity_distribution": распределение интенсивности в процентах
- "training_days": массив объектов с тренировками, включающий:
  * "day": номер дня (1-7)
  * "day_of_week": день недели на русском
  * "date": дата в формате ГГГГ-ММ-ДД
  * "workout_type": тип тренировки
  * "distance": дистанция в км (число)
  * "pace": рекомендуемый темп в мин/км
  * "heart_rate": диапазон пульса
  * "description": подробное описание тренировки
  * "purpose": цель этой тренировки
- "rest_days": массив объектов с днями отдыха, включающий:
  * "day": номер дня (1-7)
  * "day_of_week": день недели на русском
  * "date": дата в формате ГГГГ-ММ-ДД
  * "activity": рекомендуемая активность в день отдыха
  * "purpose": цель отдыха
- "recommendations": объект с рекомендациями:
  * "nutrition": питание
  * "recovery": восстановление
  * "progression": развитие в последующие недели
  * "adjustments": рекомендации по корректировке плана

Используй методики из книг Jack Daniels "Training Distance Runners", Steve Magness "Science of Running" и Tudor Bompa "Periodization Training for Sports" для определения оптимальных зон интенсивности и нагрузки."""
        
        return prompt
    
    def generate_training_plan(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Генерирует персонализированный план тренировок
        
        Args:
            profile: Словарь с данными профиля бегуна
            
        Returns:
            Dict: Структурированный план тренировок
        """
        try:
            # Получаем промпты
            system_prompt = self.get_system_prompt()
            user_prompt = self.get_user_prompt(profile)
            
            logger.info("Отправляем запрос к OpenAI для генерации плана тренировок")
            
            # Формируем запрос к API
            response = self.client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.7
            )
            
            # Получаем ответ
            content = response.choices[0].message.content
            logger.info("Получен ответ от OpenAI API")
            
            # Преобразуем в JSON
            plan = json.loads(content)
            logger.info(f"План успешно преобразован в JSON формат: {len(str(plan))} символов")
            
            # Добавляем информацию о времени генерации
            plan["generated_at"] = datetime.now().isoformat()
            
            return plan
            
        except Exception as e:
            logger.error(f"Ошибка при генерации плана тренировок: {e}")
            raise

def format_training_plan(plan: Dict[str, Any]) -> str:
    """
    Форматирует план тренировок для удобного вывода
    
    Args:
        plan: Словарь с данными плана
        
    Returns:
        str: Отформатированный план тренировок
    """
    output = []
    output.append("="*60)
    output.append(f"🏃 ПЛАН ТРЕНИРОВОК: {plan.get('plan_name', 'Персонализированный план')}")
    output.append("="*60)
    output.append("")
    
    # Описание плана
    output.append(plan.get('plan_description', 'Нет описания'))
    output.append("")
    output.append(f"📊 Общий объем: {plan.get('weekly_volume', '?')} км")
    output.append(f"📈 Распределение интенсивности: {plan.get('intensity_distribution', '?')}")
    output.append("")
    
    # Дни тренировок
    output.append("📅 РАСПИСАНИЕ ТРЕНИРОВОК:")
    output.append("-"*60)
    
    # Сортируем дни по номеру
    all_days = []
    all_days.extend([{"type": "training", **day} for day in plan.get('training_days', [])])
    all_days.extend([{"type": "rest", **day} for day in plan.get('rest_days', [])])
    all_days.sort(key=lambda x: x.get('day', 0))
    
    for day_data in all_days:
        day_num = day_data.get('day', '?')
        day_name = day_data.get('day_of_week', '?')
        date = day_data.get('date', '')
        date_str = f" ({date})" if date else ""
        
        output.append(f"ДЕНЬ {day_num}: {day_name}{date_str}")
        
        if day_data.get('type') == 'training':
            workout_type = day_data.get('workout_type', 'Тренировка')
            distance = day_data.get('distance', '?')
            pace = day_data.get('pace', '?')
            hr = day_data.get('heart_rate', '?')
            
            output.append(f"🏃 {workout_type} - {distance} км")
            output.append(f"⏱️ Темп: {pace} мин/км")
            output.append(f"❤️ Пульс: {hr}")
            output.append(f"📝 {day_data.get('description', 'Нет описания')}")
            output.append(f"🎯 Цель: {day_data.get('purpose', 'Не указана')}")
        else:
            activity = day_data.get('activity', 'Отдых')
            output.append(f"🧘 {activity}")
            output.append(f"🎯 Цель: {day_data.get('purpose', 'Восстановление')}")
        
        output.append("-"*60)
    
    # Рекомендации
    recommendations = plan.get('recommendations', {})
    if recommendations:
        output.append("💡 РЕКОМЕНДАЦИИ:")
        for key, value in recommendations.items():
            # Преобразуем ключ в заголовок
            title_map = {
                "nutrition": "Питание",
                "recovery": "Восстановление",
                "progression": "Прогрессия",
                "adjustments": "Корректировки"
            }
            title = title_map.get(key, key.capitalize())
            
            output.append(f"• {title}: {value}")
        
        output.append("-"*60)
    
    return "\n".join(output)

def save_plan_to_file(plan: Dict[str, Any], filename: str = None) -> str:
    """
    Сохраняет план тренировок в JSON файл
    
    Args:
        plan: Словарь с данными плана
        filename: Имя файла (опционально)
        
    Returns:
        str: Путь к сохраненному файлу
    """
    if not filename:
        filename = f"training_plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(plan, f, ensure_ascii=False, indent=2)
        
        logger.info(f"План тренировок сохранен в файл: {filename}")
        return filename
    except Exception as e:
        logger.error(f"Ошибка при сохранении плана в файл: {e}")
        raise

def test_coach_prompt():
    """
    Тестирует генерацию плана с тестовым профилем
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
            "goal": "Улучшить время",
            "target_time": "50 минут",
            "fitness_level": "Средний",
            "comfortable_pace": "5:30-6:30",
            "weekly_volume": 20,
            "training_days_per_week": 4
        }
        
        # Создаем генератор промптов и получаем план
        coach = CoachPrompt()
        plan = coach.generate_training_plan(test_profile)
        
        # Сохраняем план в файл
        filename = save_plan_to_file(plan)
        
        # Форматируем и выводим план
        formatted_plan = format_training_plan(plan)
        print(formatted_plan)
        
        print(f"\nПлан сохранен в файл: {filename}")
        
    except Exception as e:
        logger.error(f"Ошибка при тестировании генерации плана: {e}")
        print(f"Произошла ошибка: {e}")
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(test_coach_prompt())