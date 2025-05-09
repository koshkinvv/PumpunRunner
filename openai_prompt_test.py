#!/usr/bin/env python3
"""
Скрипт для тестирования промптов к OpenAI API.
Позволяет проверить работу промптов для генерации планов тренировок.
"""
import os
import sys
import json
import argparse
from openai import OpenAI

# Настройка API ключа
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print("❌ Ошибка: Не найден OPENAI_API_KEY в переменных окружения")
    sys.exit(1)

client = OpenAI(api_key=OPENAI_API_KEY)

def get_test_profile():
    """Возвращает тестовый профиль бегуна для генерации плана"""
    return {
        "distance": "10 км",
        "competition_date": "2025-08-01",
        "gender": "Мужской",
        "age": 30,
        "height": 180,
        "weight": 75,
        "experience": "Начинающий",
        "goal": "Финишировать",
        "target_time": "50 минут",
        "fitness_level": "Средний",
        "comfortable_pace": "5:30-6:30",
        "weekly_volume": 20,
        "training_start_date": "2025-05-15",
        "training_days_per_week": 3,
        "preferred_training_days": ["Понедельник", "Среда", "Суббота"]
    }

def create_training_plan_prompt(profile):
    """Создает промпт для генерации плана тренировок на основе профиля бегуна"""
    # Формируем основной промпт с информацией о профиле
    prompt = f"""Создай план беговых тренировок на 7 дней на основе следующего профиля бегуна:

Дистанция: {profile['distance']}
Дата соревнования: {profile['competition_date']}
Пол: {profile['gender']}
Возраст: {profile['age']}
Рост: {profile['height']} см
Вес: {profile['weight']} кг
Опыт бега: {profile['experience']}
Цель: {profile['goal']}
Целевое время: {profile['target_time']}
Уровень физической подготовки: {profile['fitness_level']}
Комфортный темп: {profile['comfortable_pace']} мин/км
Текущий недельный объем бега: {profile['weekly_volume']} км
Дата начала тренировок: {profile['training_start_date']}
Тренировочных дней в неделю: {profile['training_days_per_week']}
Предпочтительные дни тренировок: {', '.join(profile['preferred_training_days'])}

План должен включать:
1. Конкретные тренировки на каждый день (тип тренировки, дистанция, темп)
2. Дни отдыха
3. Рекомендации по темпу и интенсивности для каждой тренировки
4. Общий недельный километраж

План должен учитывать уровень подготовки бегуна и быть реалистичным. Используй термины и форматы, понятные бегунам.
Представь ответ в формате JSON со следующей структурой:
{{
  "plan": [
    {{
      "day": 1,
      "date": "2025-05-15",
      "day_of_week": "Четверг",
      "workout_type": "Легкий бег",
      "distance": 5,
      "description": "Легкий бег в комфортном темпе",
      "pace": "6:30-7:00",
      "duration": 33
    }},
    // и так далее для каждого дня недели
  ],
  "total_distance": 30,
  "recommendations": "Рекомендации по плану тренировок"
}}
"""
    return prompt

def test_training_plan_generation(profile=None, model="gpt-4o", save_to_file=None):
    """Тестирует генерацию плана тренировок"""
    if profile is None:
        profile = get_test_profile()
    
    prompt = create_training_plan_prompt(profile)
    
    print(f"Генерация плана тренировок с использованием модели {model}...")
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        
        # Пытаемся разобрать JSON
        try:
            plan = json.loads(content)
            
            # Выводим информацию о сгенерированном плане
            print("\n✅ План тренировок успешно сгенерирован!")
            print(f"\nОбщий километраж: {plan.get('total_distance', 'Не указан')} км")
            print(f"\nРекомендации: {plan.get('recommendations', 'Нет рекомендаций')}")
            
            print("\nПлан по дням:")
            for day in plan.get('plan', []):
                print(f"День {day.get('day', '?')}: {day.get('date', '?')} ({day.get('day_of_week', '?')})")
                print(f"  {day.get('workout_type', '?')}, {day.get('distance', '?')} км")
                print(f"  Темп: {day.get('pace', '?')}, Длительность: {day.get('duration', '?')} мин")
                print(f"  {day.get('description', '')}")
                print()
            
            # Сохраняем в файл, если указано
            if save_to_file:
                with open(save_to_file, 'w', encoding='utf-8') as f:
                    json.dump(plan, f, ensure_ascii=False, indent=2)
                print(f"\nПлан сохранен в файл: {save_to_file}")
            
            # Информация о запросе
            print(f"\nИнформация о запросе:")
            print(f"- Использованная модель: {response.model}")
            print(f"- Токены запроса: {response.usage.prompt_tokens}")
            print(f"- Токены ответа: {response.usage.completion_tokens}")
            print(f"- Всего токенов: {response.usage.total_tokens}")
            
            return True, plan
        
        except json.JSONDecodeError:
            print("❌ Ошибка: Ответ API не является валидным JSON")
            print("\nПолученный ответ:")
            print(content)
            return False, content
    
    except Exception as e:
        print(f"❌ Ошибка при генерации плана тренировок: {e}")
        return False, str(e)

def main():
    """Основная функция скрипта"""
    parser = argparse.ArgumentParser(description="Тестирование промптов OpenAI для генерации планов тренировок")
    parser.add_argument("--model", default="gpt-4o", help="Модель OpenAI для генерации (по умолчанию: gpt-4o)")
    parser.add_argument("--save", help="Сохранить результат в указанный файл")
    args = parser.parse_args()
    
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ ГЕНЕРАЦИИ ПЛАНА ТРЕНИРОВОК")
    print("=" * 60)
    
    success, _ = test_training_plan_generation(model=args.model, save_to_file=args.save)
    
    print("\n" + "=" * 60)
    if success:
        print("✅ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО УСПЕШНО")
    else:
        print("❌ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО С ОШИБКАМИ")
    print("=" * 60)

if __name__ == "__main__":
    main()