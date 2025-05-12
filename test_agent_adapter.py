"""
Тестовый скрипт для проверки работы адаптера MCP-инструментов.
Этот скрипт позволяет протестировать генерацию плана тренировок как с нуля,
так и продолжение существующего плана на основе выполненных тренировок.
"""

import json
import logging
import os
from pprint import pprint

from agent.adapter import AgentAdapter
from agent.tools.generate_plan import RunnerProfile, RecentRun

# Настройка логирования
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Пример профиля бегуна в формате, используемом ботом
EXAMPLE_PROFILE = {
    "id": 1,
    "user_id": 123456789,
    "age": 30,
    "gender": "Мужской",
    "weight": 75,
    "height": 180,
    "experience": None,  # Уровень подготовки теперь может быть None
    "weekly_volume": 20,
    "goal_distance": 10.0,
    "goal_distance_text": "10 км",
    "competition_date": "2025-12-31",
    "preferred_days": ["Понедельник", "Среда", "Пятница", "Воскресенье"],
    "target_time": "45:00",
    "comfortable_pace": "5:30",
    "created_at": "2025-05-01"
}

# Пример плана тренировок с выполненными тренировками
EXAMPLE_PLAN = {
    "plan_name": "План тренировки для забега на 10 км",
    "plan_description": "Персонализированный план тренировок для подготовки к забегу на 10 км",
    "plan_data": {
        "training_days": [
            {
                "day": "Понедельник",
                "date": "13.05.2025",
                "training_type": "Легкий бег",
                "distance": "5 км",
                "pace": "6:00",
                "description": "Легкий восстановительный бег в комфортном темпе."
            },
            {
                "day": "Среда",
                "date": "15.05.2025",
                "training_type": "Интервалы",
                "distance": "6 км",
                "pace": "5:30",
                "description": "10 x 400м с восстановлением 200м шагом."
            },
            {
                "day": "Пятница",
                "date": "17.05.2025",
                "training_type": "Темповой бег",
                "distance": "7 км",
                "pace": "5:15",
                "description": "3 км разминка, 3 км в темповом темпе, 1 км заминка."
            },
            {
                "day": "Воскресенье",
                "date": "19.05.2025",
                "training_type": "Длительный бег",
                "distance": "12 км",
                "pace": "6:00",
                "description": "Длительный бег в равномерном темпе."
            }
        ],
        "completed_trainings": {
            "completed_1": True,
            "completed_2": True,
            "completed_3": False,
            "completed_4": False
        },
        "cancelled_trainings": {
            "cancelled_3": True
        }
    }
}

def test_generate_plan():
    """Тестирует генерацию нового плана тренировок."""
    logging.info("Тестирование генерации нового плана тренировок")
    
    try:
        # Инициализируем адаптер
        adapter = AgentAdapter()
        
        # Генерируем план
        plan = adapter.generate_training_plan(EXAMPLE_PROFILE)
        
        # Выводим результат
        logging.info(f"План успешно сгенерирован: {plan.get('plan_name', 'Неизвестный план')}")
        print("\nСгенерированный план:\n")
        print(json.dumps(plan, indent=2, ensure_ascii=False))
        
        # Сохраняем план в файл для ручной проверки
        with open("test_generated_plan.json", "w", encoding="utf-8") as f:
            json.dump(plan, f, indent=2, ensure_ascii=False)
            
        logging.info("План сохранен в файл test_generated_plan.json")
        
        return True
    except Exception as e:
        logging.error(f"Ошибка при генерации плана: {e}")
        return False

def test_continue_plan():
    """Тестирует генерацию продолжения плана тренировок."""
    logging.info("Тестирование генерации продолжения плана тренировок")
    
    try:
        # Инициализируем адаптер
        adapter = AgentAdapter()
        
        # Генерируем продолжение плана
        total_distance = 11.0  # 5 км + 6 км
        new_plan = adapter.generate_training_plan_continuation(
            EXAMPLE_PROFILE, 
            total_distance, 
            EXAMPLE_PLAN["plan_data"]
        )
        
        # Выводим результат
        logging.info(f"Продолжение плана успешно сгенерировано: {new_plan.get('plan_name', 'Неизвестный план')}")
        print("\nСгенерированное продолжение плана:\n")
        print(json.dumps(new_plan, indent=2, ensure_ascii=False))
        
        # Сохраняем план в файл для ручной проверки
        with open("test_continued_plan.json", "w", encoding="utf-8") as f:
            json.dump(new_plan, f, indent=2, ensure_ascii=False)
            
        logging.info("Продолжение плана сохранено в файл test_continued_plan.json")
        
        return True
    except Exception as e:
        logging.error(f"Ошибка при генерации продолжения плана: {e}")
        return False

def test_mock_recent_runs():
    """
    Тестирует создание экземпляров RecentRun и их использование
    в RunnerProfile.
    """
    logging.info("Тестирование создания объектов RecentRun")
    
    try:
        # Создаем список недавних тренировок
        recent_runs = [
            RecentRun(
                date="2025-05-13",
                distance=5.0,
                pace="6:00",
                notes="Легкий восстановительный бег"
            ),
            RecentRun(
                date="2025-05-15",
                distance=6.0,
                pace="5:30",
                notes="Интервалы 10x400м"
            )
        ]
        
        # Создаем профиль с недавними тренировками
        profile = RunnerProfile(
            age=30,
            gender="Мужской",
            weight=75,
            height=180,
            level=None,
            weekly_distance=20,
            goal_distance="10 км",
            goal_date="2025-12-31",
            available_days=["Понедельник", "Среда", "Пятница", "Воскресенье"],
            target_time="45:00",
            comfortable_pace="5:30",
            recent_runs=recent_runs,
            adjustment_info=None,
            current_plan=None
        )
        
        # Выводим профиль
        print("\nПрофиль с недавними тренировками:\n")
        print(profile.model_dump_json(indent=2))
        
        return True
    except Exception as e:
        logging.error(f"Ошибка при создании объектов RecentRun: {e}")
        return False

def main():
    """Основная функция для запуска тестов."""
    print("=" * 50)
    print("Тестирование адаптера MCP-инструментов")
    print("=" * 50)
    
    # Проверяем наличие API ключа
    if not os.environ.get("OPENAI_API_KEY"):
        print("⚠️ ВНИМАНИЕ: Переменная окружения OPENAI_API_KEY не найдена.")
        print("Убедитесь, что вы установили ключ API для OpenAI перед запуском тестов.")
        return
    
    # Запускаем тесты
    print("\n1. Тестирование создания объектов RecentRun")
    test_mock_recent_runs()
    
    print("\n2. Тестирование генерации нового плана тренировок")
    test_generate_plan()
    
    print("\n3. Тестирование генерации продолжения плана тренировок")
    test_continue_plan()
    
    print("\n" + "=" * 50)
    print("Тестирование завершено")
    print("=" * 50)

if __name__ == "__main__":
    main()