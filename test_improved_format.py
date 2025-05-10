#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import psycopg2
from improved_training_format import format_training_day

def get_training_plan_from_db(plan_id=31):
    """Получает данные плана тренировок из базы данных по ID."""
    try:
        # Подключаемся к базе данных
        conn = psycopg2.connect(os.environ.get("DATABASE_URL"))
        cur = conn.cursor()
        
        # Получаем данные плана
        cur.execute("SELECT plan_data FROM training_plans WHERE id = %s", (plan_id,))
        plan_data = cur.fetchone()[0]
        
        # Закрываем соединение
        cur.close()
        conn.close()
        
        return plan_data
    except Exception as e:
        print(f"Ошибка при получении плана из БД: {e}")
        return None

def main():
    """Основная функция для тестирования улучшенного форматирования."""
    # Получаем план из базы данных
    plan_data_str = get_training_plan_from_db()
    
    if not plan_data_str:
        print("Не удалось получить данные плана.")
        return
    
    try:
        # Парсим данные плана (если это уже словарь, использовать напрямую)
        if isinstance(plan_data_str, dict):
            plan_data = plan_data_str
        else:
            plan_data = json.loads(plan_data_str)
        
        # Извлекаем дни тренировок
        if "plan_data" in plan_data and "training_days" in plan_data["plan_data"]:
            training_days = plan_data["plan_data"]["training_days"]
        else:
            print("Ошибка: Не найдено training_days в данных плана.")
            print(f"Структура данных: {plan_data.keys()}")
            return
        
        # Форматируем и выводим каждый день тренировки
        for i, day in enumerate(training_days, 1):
            formatted_day = format_training_day(day, i)
            print("\n" + "=" * 80)
            print(f"ДЕНЬ ТРЕНИРОВКИ {i}")
            print("=" * 80)
            print(formatted_day)
            print("=" * 80)
            
        print("\nФорматирование завершено успешно.")
        
    except Exception as e:
        print(f"Ошибка при обработке данных плана: {e}")
        print(f"Тип данных: {type(plan_data_str)}")
        print(f"Данные: {plan_data_str[:100]}...")

if __name__ == "__main__":
    main()