#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работы функции корректировки плана тренировок
через MCP-адаптер.
"""

import os
import sys
import json
import logging
from pprint import pprint

from agent.adapter import AgentAdapter
from agent.tools.generate_plan import RunnerProfile, AdjustmentInfo, CurrentPlan, TrainingDay

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
    "experience": "intermediate",
    "weekly_volume": 25,
    "goal_distance": 10.0,
    "goal_distance_text": "10 км",
    "competition_date": "2025-09-30",
    "preferred_days": ["Понедельник", "Среда", "Пятница", "Воскресенье"],
    "target_time": "45:00",
    "comfortable_pace": "5:30",
    "created_at": "2025-05-01"
}

# Пример текущего плана тренировок
EXAMPLE_PLAN = {
    "plan_name": "План тренировки для забега на 10 км",
    "plan_description": "Персонализированный план тренировок для подготовки к забегу на 10 км",
    "plan_data": {
        "training_days": [
            {
                "day": "Понедельник",
                "date": "13.05.2025",
                "training_type": "Легкий бег",
                "distance": 5.0,
                "pace": "6:00",
                "description": "Легкий восстановительный бег в комфортном темпе."
            },
            {
                "day": "Среда",
                "date": "15.05.2025",
                "training_type": "Интервалы",
                "distance": 6.0,
                "pace": "5:00",
                "description": "Интервальная тренировка: разминка 2 км, 5x400м с отдыхом 2 мин, заминка 1.5 км."
            },
            {
                "day": "Пятница",
                "date": "17.05.2025",
                "training_type": "Темповой бег",
                "distance": 4.0,
                "pace": "5:30",
                "description": "Равномерный бег в темповом режиме."
            },
            {
                "day": "Воскресенье",
                "date": "19.05.2025",
                "training_type": "Длительный бег",
                "distance": 8.0,
                "pace": "6:15",
                "description": "Длительный бег в умеренном темпе для развития выносливости."
            }
        ],
        "total_distance": 23.0
    }
}

def test_adjustment():
    """
    Тестирует функцию корректировки плана тренировок через MCP-адаптер.
    """
    # Проверяем наличие ключа OpenAI API
    if not os.environ.get("OPENAI_API_KEY"):
        print("Ошибка: переменная среды OPENAI_API_KEY не установлена")
        print("Установите ключ API командой: export OPENAI_API_KEY='ваш-ключ'")
        sys.exit(1)
    
    try:
        # Создаем экземпляр адаптера
        agent_adapter = AgentAdapter()
        
        # Параметры корректировки плана
        day_num = 2  # День для корректировки (Среда - интервалы)
        planned_distance = 6.0  # Планировалось пробежать 6 км
        actual_distance = 4.5  # Фактически пробежали 4.5 км
        
        # Корректируем план
        print(f"\nКорректировка плана: день {day_num}, плановая дистанция {planned_distance} км, фактическая {actual_distance} км")
        
        adjusted_plan = agent_adapter.adjust_training_plan(
            EXAMPLE_PROFILE,
            EXAMPLE_PLAN["plan_data"],
            day_num,
            planned_distance,
            actual_distance
        )
        
        # Выводим результат
        if adjusted_plan:
            print("\n✅ План успешно скорректирован!")
            print(f"Название плана: {adjusted_plan.get('plan_name')}")
            print(f"Описание: {adjusted_plan.get('plan_description')}")
            
            # Выводим скорректированные дни тренировок
            print("\nСкорректированный план тренировок:")
            for i, day in enumerate(adjusted_plan.get('training_days', [])):
                print(f"\nДень {i+1}: {day.get('day')} ({day.get('date')})")
                print(f"Тип: {day.get('training_type')}")
                print(f"Дистанция: {day.get('distance')} км")
                print(f"Описание: {day.get('description')}")
            
            return True
        else:
            print("\n❌ Не удалось скорректировать план")
            return False
            
    except Exception as e:
        print(f"\n❌ Ошибка при корректировке плана: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Тестирование корректировки плана тренировок через MCP-адаптер")
    print("=" * 60)
    
    success = test_adjustment()
    
    if success:
        print("\n✅ Тест успешно пройден")
    else:
        print("\n❌ Тест не пройден")
    
    print("=" * 60)