"""
Скрипт для проверки интеграции MCP-адаптера с ботом.
Имитирует основные вызовы бота для генерации планов тренировок.
"""

import json
import logging
import os
from datetime import datetime

# Настройка логирования
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Пример профиля бегуна
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

# Пример плана тренировок
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
            }
        ],
        "completed_trainings": {
            "completed_1": True,
            "completed_2": True
        }
    }
}

def test_bot_generate_plan():
    """
    Имитирует вызов генерации плана из бота.
    """
    logging.info("Имитация генерации плана из бота...")
    
    try:
        # Этот код аналогичен коду в bot_modified.py
        try:
            # Пробуем использовать новый MCP-инструмент через адаптер
            from agent.adapter import AgentAdapter
            agent_adapter = AgentAdapter()
            logging.info("Инициализация AgentAdapter для генерации плана...")
            plan = agent_adapter.generate_training_plan(EXAMPLE_PROFILE)
            logging.info(f"План успешно создан через MCP-инструмент: {plan.get('plan_name', 'Неизвестный план')}")
        except Exception as e:
            logging.error(f"Ошибка при использовании MCP-инструмента: {e}")
            logging.info("Переключение на оригинальный сервис...")
            
            from openai_service import OpenAIService
            openai_service = OpenAIService()
            plan = openai_service.generate_training_plan(EXAMPLE_PROFILE)
            logging.info(f"План успешно создан через OpenAIService: {plan.get('plan_name', 'Неизвестный план')}")
        
        # Сохраняем план для проверки
        filename = f"test_bot_generated_plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(plan, f, indent=2, ensure_ascii=False)
        
        logging.info(f"План сохранен в файл: {filename}")
        return True
    
    except Exception as e:
        logging.error(f"Ошибка при имитации генерации плана: {e}")
        return False

def test_bot_continue_plan():
    """
    Имитирует вызов продолжения плана из бота.
    """
    logging.info("Имитация продолжения плана из бота...")
    
    try:
        # Расчет общего пройденного расстояния
        total_distance = 11.0  # 5 км + 6 км
        
        # Этот код аналогичен коду в bot_modified.py
        try:
            # Сначала пробуем использовать MCP-инструмент через адаптер
            logging.info("Инициализация AgentAdapter для продолжения плана...")
            from agent.adapter import AgentAdapter
            agent_adapter = AgentAdapter()
            
            logging.info(f"Вызов agent_adapter.generate_training_plan_continuation с total_distance={total_distance}")
            new_plan = agent_adapter.generate_training_plan_continuation(
                EXAMPLE_PROFILE, 
                total_distance, 
                EXAMPLE_PLAN["plan_data"]
            )
            logging.info(f"Получен новый план через MCP-инструмент: {new_plan.get('plan_name', 'Неизвестный план')}")
        except Exception as adapter_error:
            # Если произошла ошибка с адаптером, используем старый сервис
            logging.error(f"Ошибка при использовании AgentAdapter: {adapter_error}")
            logging.info("Переключение на OpenAIService для продолжения плана")
            
            from openai_service import OpenAIService
            openai_service = OpenAIService()
            logging.info(f"Вызов openai_service.generate_training_plan_continuation с total_distance={total_distance}")
            new_plan = openai_service.generate_training_plan_continuation(
                EXAMPLE_PROFILE, 
                total_distance, 
                EXAMPLE_PLAN["plan_data"]
            )
            logging.info(f"Получен новый план через OpenAIService: {new_plan.get('plan_name', 'Неизвестный план')}")
        
        # Сохраняем план для проверки
        filename = f"test_bot_continued_plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(new_plan, f, indent=2, ensure_ascii=False)
        
        logging.info(f"План сохранен в файл: {filename}")
        return True
    
    except Exception as e:
        logging.error(f"Ошибка при имитации продолжения плана: {e}")
        return False

def main():
    """Основная функция для запуска тестов."""
    print("=" * 50)
    print("Тестирование интеграции MCP-адаптера с ботом")
    print("=" * 50)
    
    # Проверяем наличие API ключа
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("⚠️ ВНИМАНИЕ: Переменная окружения OPENAI_API_KEY не найдена.")
        openai_key = input("Введите API ключ OpenAI для тестирования: ")
        os.environ["OPENAI_API_KEY"] = openai_key
    
    # Запускаем тест генерации плана
    print("\n1. Тестирование генерации плана...")
    if test_bot_generate_plan():
        print("✅ Тест генерации плана успешно пройден")
    else:
        print("❌ Тест генерации плана не пройден")
    
    # Запускаем тест продолжения плана
    print("\n2. Тестирование продолжения плана...")
    if test_bot_continue_plan():
        print("✅ Тест продолжения плана успешно пройден")
    else:
        print("❌ Тест продолжения плана не пройден")
    
    print("\n" + "=" * 50)
    print("Тестирование завершено")
    print("=" * 50)

if __name__ == "__main__":
    main()