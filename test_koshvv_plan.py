"""
Тестовый скрипт для генерации плана тренировок с использованием MCP-адаптера
на примере профиля пользователя koshvv.
"""

import json
import logging
import os
from datetime import datetime

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

def format_training_plan(plan):
    """
    Форматирует план тренировок для удобного вывода в консоль.
    
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
    
    # Получаем тренировочные дни из плана
    training_days = plan.get('plan_data', {}).get('training_days', [])
    
    for day_data in training_days:
        day_name = day_data.get('day', '?')
        date = day_data.get('date', '')
        training_type = day_data.get('training_type', 'Тренировка')
        distance = day_data.get('distance', '?')
        pace = day_data.get('pace', '?')
        description = day_data.get('description', 'Нет описания')
        
        output.append(f"ДЕНЬ {day_name} - {date}")
        output.append(f"🏃 {training_type} - {distance}")
        output.append(f"⏱️ Темп: {pace}")
        output.append(f"📝 {description}")
        output.append("-"*60)
    
    return "\n".join(output)

def generate_plan_for_koshvv():
    """
    Генерирует план тренировок для пользователя koshvv,
    используя новый MCP-адаптер.
    """
    try:
        # Инициализируем адаптер
        logging.info("Инициализация AgentAdapter для генерации плана koshvv...")
        from agent.adapter import AgentAdapter
        agent_adapter = AgentAdapter()
        
        # Генерируем план через адаптер
        logging.info(f"Вызов agent_adapter.generate_training_plan для пользователя koshvv")
        
        # Измеряем время выполнения
        start_time = datetime.now()
        plan = agent_adapter.generate_training_plan(KOSHVV_PROFILE)
        execution_time = (datetime.now() - start_time).total_seconds()
        
        logging.info(f"План успешно сгенерирован через MCP-инструмент за {execution_time:.2f} секунд")
        logging.info(f"Название плана: {plan.get('plan_name', 'Неизвестный план')}")
        
        # Сохраняем план в файл для проверки
        filename = f"koshvv_mcp_plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(plan, f, indent=2, ensure_ascii=False)
            
        logging.info(f"План сохранен в файл: {filename}")
        
        # Форматируем и возвращаем план
        return format_training_plan(plan), filename
    
    except Exception as e:
        logging.error(f"Ошибка при генерации плана: {e}", exc_info=True)
        return f"Ошибка при генерации плана: {e}", None

def main():
    """Основная функция для запуска тестов."""
    print("=" * 60)
    print("Тестовая генерация плана для пользователя koshvv")
    print("=" * 60)
    
    # Проверяем наличие API ключа
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("⚠️ ВНИМАНИЕ: Переменная окружения OPENAI_API_KEY не найдена.")
        openai_key = input("Введите API ключ OpenAI для тестирования: ")
        os.environ["OPENAI_API_KEY"] = openai_key
    
    # Генерируем план
    plan_text, filename = generate_plan_for_koshvv()
    
    # Выводим результаты
    if filename:
        print(f"\n✅ План успешно сгенерирован и сохранен в файл: {filename}")
        print("\nКраткое содержание плана:")
        print(plan_text)
    else:
        print("\n❌ Не удалось сгенерировать план")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()