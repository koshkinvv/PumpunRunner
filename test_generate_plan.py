#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работы MCP-инструмента GeneratePlanUseCase.
Демонстрирует, как можно использовать инструмент напрямую для генерации
тренировочного плана.
"""

import os
import sys
from agent.tools.generate_plan import GeneratePlanUseCase, RunnerProfile, RecentRun

def main():
    """
    Основная функция для тестирования GeneratePlanUseCase.
    """
    # Проверяем наличие ключа OpenAI API
    if not os.environ.get("OPENAI_API_KEY"):
        print("Ошибка: переменная среды OPENAI_API_KEY не установлена")
        print("Установите ключ API командой: export OPENAI_API_KEY='ваш-ключ'")
        sys.exit(1)
    
    try:
        # Создаем экземпляр GeneratePlanUseCase
        generate_plan_tool = GeneratePlanUseCase()
        
        # Создаем тестовый профиль бегуна
        profile = RunnerProfile(
            age=30,
            gender="Женский",
            weight=62.0,
            height=165.0,
            level="beginner",
            weekly_distance=15.0,
            goal_distance="10 км",
            goal_date="2025-07-20",
            available_days=["Вторник", "Четверг", "Суббота"],
            recent_runs=[
                RecentRun(date="2025-05-01", distance=5.0, pace="6:30"),
                RecentRun(date="2025-05-08", distance=6.0, pace="6:25")
            ]
        )
        
        print(f"📋 Генерация плана для бегуна:")
        print(f"   Возраст: {profile.age} лет")
        print(f"   Пол: {profile.gender}")
        print(f"   Уровень: {profile.level}")
        print(f"   Цель: {profile.goal_distance} ({profile.goal_date})")
        print(f"   Доступные дни: {', '.join(profile.available_days)}")
        print("\n⏳ Пожалуйста, подождите, генерация плана может занять до 30 секунд...\n")
        
        # Генерируем план
        plan = generate_plan_tool(profile)
        
        # Выводим результат
        print(plan)
        
        print("\n✅ План успешно сгенерирован!")
        
    except Exception as e:
        print(f"❌ Ошибка при выполнении: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())