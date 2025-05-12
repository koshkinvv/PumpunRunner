"""
Упрощенный тест для проверки корректности преобразования профиля koshvv.
Не делает запрос к OpenAI API, только проверяет конвертацию данных.
"""

import logging
from pprint import pprint

# Настройка логирования
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Профиль пользователя koshvv
KOSHVV_PROFILE = {
    "id": 1,
    "user_id": 987654321,
    "age": 35,
    "gender": "Мужской",
    "weight": 82,
    "height": 185,
    "experience": None,  # Поскольку fitness_level удален, теперь передаем None
    "weekly_volume": 17.5,
    "goal_distance": 42.2,
    "goal_distance_text": "Марафон",
    "competition_date": None,  # Без конкретной даты соревнования
    "preferred_days": ["Понедельник", "Суббота", "Воскресенье"],
    "target_time": "4:30:00",
    "comfortable_pace": "6:30",
    "created_at": "2025-05-09"
}

def test_profile_conversion():
    """
    Тестирует преобразование профиля из формата бота в формат MCP.
    """
    try:
        from agent.adapter import AgentAdapter
        
        # Инициализируем адаптер
        adapter = AgentAdapter()
        
        # Преобразуем профиль
        mcp_profile = adapter._convert_to_mcp_profile(KOSHVV_PROFILE)
        
        # Выводим результат
        print("\nКонвертированный профиль для пользователя koshvv:")
        print(f"goal_distance: {mcp_profile.goal_distance}")
        print(f"goal_date: {mcp_profile.goal_date}")
        print(f"age: {mcp_profile.age}")
        print(f"gender: {mcp_profile.gender}")
        print(f"weight: {mcp_profile.weight}")
        print(f"height: {mcp_profile.height}")
        print(f"level: {mcp_profile.level}")
        print(f"weekly_distance: {mcp_profile.weekly_distance}")
        print(f"available_days: {mcp_profile.available_days}")
        print(f"target_time: {mcp_profile.target_time}")
        print(f"comfortable_pace: {mcp_profile.comfortable_pace}")
        
        # Проверяем корректность целевой дистанции
        assert mcp_profile.goal_distance == "Марафон", "Неправильная целевая дистанция"
        
        return True
    except Exception as e:
        logging.error(f"Ошибка при тестировании преобразования профиля: {e}", exc_info=True)
        return False

def main():
    """Основная функция для запуска тестов."""
    print("=" * 60)
    print("Тест преобразования профиля пользователя koshvv")
    print("=" * 60)
    
    if test_profile_conversion():
        print("\n✅ Тест преобразования профиля успешно пройден")
    else:
        print("\n❌ Тест преобразования профиля не пройден")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()