"""
Простой тест для проверки работы адаптера MCP-инструментов.
"""

import logging
import os

# Настройка логирования
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def check_adapter_imports():
    """Проверяет импорты необходимых классов адаптера."""
    try:
        from agent.adapter import AgentAdapter
        from agent.tools.generate_plan import RunnerProfile, RecentRun
        
        logging.info("✅ Импорты успешно загружены")
        return True
    except Exception as e:
        logging.error(f"❌ Ошибка при импорте: {e}")
        return False

def create_simple_profile():
    """Создает простой профиль для тестирования."""
    from agent.tools.generate_plan import RunnerProfile
    
    try:
        profile = RunnerProfile(
            age=30,
            gender="Мужской",
            weight=75.0,
            height=180.0,
            level=None,
            weekly_distance=20.0,
            goal_distance="10 км",
            goal_date="2025-12-31",
            available_days=["Понедельник", "Среда", "Пятница"],
            target_time="45:00",
            comfortable_pace="5:30",
            recent_runs=[],
            adjustment_info=None,
            current_plan=None
        )
        
        logging.info(f"✅ Профиль создан: {profile.model_dump_json(indent=2)}")
        return True
    except Exception as e:
        logging.error(f"❌ Ошибка при создании профиля: {e}")
        return False

def create_adapter():
    """Создает экземпляр адаптера."""
    from agent.adapter import AgentAdapter
    
    try:
        adapter = AgentAdapter()
        logging.info("✅ Адаптер успешно создан")
        return adapter
    except Exception as e:
        logging.error(f"❌ Ошибка при создании адаптера: {e}")
        return None

def main():
    """Основная функция для запуска тестов."""
    print("=" * 50)
    print("Базовое тестирование адаптера MCP-инструментов")
    print("=" * 50)
    
    # Проверяем наличие API ключа
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("⚠️ ВНИМАНИЕ: Переменная окружения OPENAI_API_KEY не найдена.")
        openai_key = input("Введите API ключ OpenAI для тестирования: ")
        os.environ["OPENAI_API_KEY"] = openai_key
    
    # Тестируем импорты
    if not check_adapter_imports():
        return
    
    # Тестируем создание профиля
    if not create_simple_profile():
        return
    
    # Тестируем создание адаптера
    adapter = create_adapter()
    if not adapter:
        return
    
    print("\n✅ Все базовые тесты успешно пройдены")
    print("=" * 50)

if __name__ == "__main__":
    main()