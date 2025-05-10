#!/usr/bin/env python
"""
Скрипт для проверки и исправления структуры данных планов тренировок.
Автоматически находит и исправляет недопустимые форматы данных в базе.
"""
import os
import sys
import json
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

# Настройка логирования
log_dir = 'logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

log_filename = os.path.join(log_dir, f'plan_structure_check_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler(sys.stdout)
    ]
)

# Получение параметров подключения к базе данных из переменных окружения
DB_URL = os.environ.get('DATABASE_URL')

def connect_to_db():
    """
    Устанавливает соединение с базой данных.
    
    Returns:
        tuple: (connection, cursor) или (None, None) в случае ошибки
    """
    try:
        # Подключение к базе данных
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        return conn, cursor
    except Exception as e:
        logging.error(f"Ошибка подключения к базе данных: {e}")
        return None, None

def create_default_training_days():
    """
    Создает базовый массив тренировочных дней.
    
    Returns:
        list: Базовый массив тренировочных дней
    """
    return [
        {
            "day": "Понедельник",
            "date": datetime.now().strftime("%d.%m.%Y"),
            "training_type": "Легкая пробежка",
            "distance": "5 км",
            "pace": "6:00-6:30 мин/км",
            "description": "Легкая восстановительная пробежка в комфортном темпе."
        },
        {
            "day": "Среда",
            "date": datetime.now().strftime("%d.%m.%Y"),
            "training_type": "Темповая тренировка",
            "distance": "7 км",
            "pace": "5:30-6:00 мин/км",
            "description": "Разминка 2 км, темповая часть 3 км, заминка 2 км."
        },
        {
            "day": "Суббота",
            "date": datetime.now().strftime("%d.%m.%Y"),
            "training_type": "Длительная пробежка",
            "distance": "10 км",
            "pace": "6:00-6:30 мин/км",
            "description": "Длительная пробежка в аэробном темпе для развития выносливости."
        }
    ]

def check_and_fix_plans():
    """
    Проверяет все планы тренировок и исправляет структуру данных при необходимости.
    
    Returns:
        dict: Статистика проверки и исправления
    """
    conn, cursor = connect_to_db()
    if not conn:
        return {"error": "Failed to connect to database"}
    
    stats = {
        "total_plans": 0,
        "plans_with_null_training_days": 0,
        "plans_with_empty_array": 0,
        "plans_with_nested_structure": 0,
        "fixed_plans": 0
    }
    
    try:
        # Общее количество планов
        cursor.execute("SELECT COUNT(*) as count FROM training_plans")
        stats["total_plans"] = cursor.fetchone()['count']
        
        # Проверка планов с null в training_days
        cursor.execute("""
            SELECT id, user_id, plan_name
            FROM training_plans
            WHERE jsonb_typeof(plan_data->'training_days') = 'null'
        """)
        null_training_days_plans = cursor.fetchall()
        stats["plans_with_null_training_days"] = len(null_training_days_plans)
        
        # Исправление планов с null в training_days
        if null_training_days_plans:
            null_plan_ids = [plan['id'] for plan in null_training_days_plans]
            logging.info(f"Найдено {len(null_plan_ids)} планов с NULL в training_days: {null_plan_ids}")
            
            # Создаем значение по умолчанию для training_days
            default_training_days = json.dumps(create_default_training_days())
            
            # Обновляем все проблемные планы
            cursor.execute(f"""
                UPDATE training_plans
                SET plan_data = jsonb_set(plan_data, '{{training_days}}', %s::jsonb)
                WHERE id IN ({','.join(map(str, null_plan_ids))})
            """, (default_training_days,))
            stats["fixed_plans"] += len(null_plan_ids)
            logging.info(f"Исправлено {len(null_plan_ids)} планов с NULL в training_days")
        
        # Проверка планов с пустым массивом training_days
        cursor.execute("""
            SELECT id, user_id, plan_name
            FROM training_plans
            WHERE jsonb_typeof(plan_data->'training_days') = 'array'
            AND jsonb_array_length(plan_data->'training_days') = 0
        """)
        empty_array_plans = cursor.fetchall()
        stats["plans_with_empty_array"] = len(empty_array_plans)
        
        # Исправление планов с пустым массивом training_days
        if empty_array_plans:
            empty_plan_ids = [plan['id'] for plan in empty_array_plans]
            logging.info(f"Найдено {len(empty_plan_ids)} планов с пустым массивом training_days: {empty_plan_ids}")
            
            # Создаем значение по умолчанию для training_days
            default_training_days = json.dumps(create_default_training_days())
            
            # Обновляем все проблемные планы
            cursor.execute(f"""
                UPDATE training_plans
                SET plan_data = jsonb_set(plan_data, '{{training_days}}', %s::jsonb)
                WHERE id IN ({','.join(map(str, empty_plan_ids))})
            """, (default_training_days,))
            stats["fixed_plans"] += len(empty_plan_ids)
            logging.info(f"Исправлено {len(empty_plan_ids)} планов с пустым массивом training_days")
        
        # Проверка планов с вложенной структурой
        cursor.execute("""
            SELECT id, user_id, plan_name
            FROM training_plans
            WHERE plan_data->'plan_data'->'training_days' IS NOT NULL
        """)
        nested_plans = cursor.fetchall()
        stats["plans_with_nested_structure"] = len(nested_plans)
        
        # Исправление планов с вложенной структурой
        if nested_plans:
            nested_plan_ids = [plan['id'] for plan in nested_plans]
            logging.info(f"Найдено {len(nested_plan_ids)} планов с вложенной структурой: {nested_plan_ids}")
            
            # Получаем данные о каждом плане
            for plan in nested_plans:
                plan_id = plan['id']
                
                # Получаем текущие данные плана
                cursor.execute("SELECT plan_data FROM training_plans WHERE id = %s", (plan_id,))
                plan_data = cursor.fetchone()['plan_data']
                
                # Извлекаем информацию о плане и данные о тренировочных днях
                try:
                    # Извлекаем тренировочные дни из вложенной структуры
                    nested_training_days = plan_data.get('plan_data', {}).get('training_days', [])
                    
                    # Получаем plan_name и plan_description
                    plan_name = plan_data.get('plan_name', 
                                              plan_data.get('plan_data', {}).get('plan_name', 'План тренировок'))
                    plan_description = plan_data.get('plan_description', 
                                                   plan_data.get('plan_data', {}).get('plan_description', 
                                                                                      'План тренировок для подготовки к марафону'))
                    
                    # Создаем новую структуру данных
                    new_plan_data = {
                        'plan_name': plan_name,
                        'plan_description': plan_description,
                        'training_days': nested_training_days if nested_training_days else create_default_training_days()
                    }
                    
                    # Обновляем запись в базе данных
                    cursor.execute(
                        "UPDATE training_plans SET plan_data = %s WHERE id = %s",
                        (json.dumps(new_plan_data), plan_id)
                    )
                    stats["fixed_plans"] += 1
                    logging.info(f"Исправлен план с ID {plan_id} (извлечение из вложенной структуры)")
                
                except Exception as e:
                    logging.error(f"Ошибка при исправлении плана с ID {plan_id}: {e}")
        
        # Фиксируем изменения
        conn.commit()
        logging.info(f"Проверка и исправление структуры данных завершены: {stats}")
        return stats
    
    except Exception as e:
        logging.exception(f"Ошибка при проверке и исправлении структуры данных: {e}")
        conn.rollback()
        return {"error": str(e)}
    
    finally:
        # Закрываем соединение
        cursor.close()
        conn.close()

def main():
    """
    Основная функция для запуска скрипта
    """
    logging.info("Запуск проверки и исправления структуры данных планов тренировок")
    stats = check_and_fix_plans()
    
    if "error" in stats:
        logging.error(f"Не удалось проверить и исправить структуру данных: {stats['error']}")
        sys.exit(1)
    else:
        logging.info(f"Итоги проверки:")
        logging.info(f"- Всего планов: {stats['total_plans']}")
        logging.info(f"- Планов с NULL в training_days: {stats['plans_with_null_training_days']}")
        logging.info(f"- Планов с пустым массивом training_days: {stats['plans_with_empty_array']}")
        logging.info(f"- Планов с вложенной структурой: {stats['plans_with_nested_structure']}")
        logging.info(f"- Исправлено планов: {stats['fixed_plans']}")
        
        if stats['fixed_plans'] > 0:
            logging.info("Структура данных успешно исправлена!")
        else:
            logging.info("Все планы тренировок имеют корректную структуру данных!")
    
    sys.exit(0)

if __name__ == "__main__":
    main()