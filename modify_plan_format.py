"""
Скрипт для изменения формата плана тренировок для пользователя koshvv.
Изменяет структуру plan_data для всех планов пользователя koshvv.
"""
import os
import sys
import json
import logging
import psycopg2
from psycopg2.extras import RealDictCursor

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
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

def modify_plan_format(user_id):
    """
    Изменяет формат всех планов тренировок для указанного пользователя.
    
    Args:
        user_id: ID пользователя в базе данных
    
    Returns:
        int: Количество измененных планов
    """
    conn, cursor = connect_to_db()
    if not conn:
        return 0
    
    try:
        # Получаем все планы тренировок пользователя
        cursor.execute("SELECT id, plan_data FROM training_plans WHERE user_id = %s", (user_id,))
        plans = cursor.fetchall()
        
        if not plans:
            logging.info(f"Планы тренировок для пользователя с ID {user_id} не найдены.")
            return 0
        
        num_plans_modified = 0
        
        for plan in plans:
            plan_id = plan['id']
            plan_data = plan['plan_data']
            
            # Создаем новый формат плана
            new_plan_data = None
            
            try:
                # Если plan_data строка - преобразуем в dict
                if isinstance(plan_data, str):
                    parsed_data = json.loads(plan_data)
                else:
                    parsed_data = plan_data
                
                # Проверяем наличие training_days
                if isinstance(parsed_data, dict) and 'training_days' in parsed_data:
                    training_days = parsed_data['training_days']
                    plan_name = parsed_data.get('plan_name', 'План тренировок')
                    plan_description = parsed_data.get('plan_description', 'План тренировок для марафона')
                    
                    # Создаем новую структуру
                    new_plan_data = {
                        'plan_name': plan_name,
                        'plan_description': plan_description,
                        'training_days': training_days
                    }
                    
                    # Обновляем запись в базе данных
                    cursor.execute(
                        "UPDATE training_plans SET plan_data = %s WHERE id = %s",
                        (json.dumps(new_plan_data), plan_id)
                    )
                    num_plans_modified += 1
                    logging.info(f"Формат плана {plan_id} успешно изменен.")
                else:
                    logging.warning(f"План с ID {plan_id} не содержит training_days, пропускаем.")
            
            except Exception as e:
                logging.error(f"Ошибка при обработке плана с ID {plan_id}: {e}")
        
        # Фиксируем изменения
        conn.commit()
        return num_plans_modified
    
    except Exception as e:
        logging.exception(f"Ошибка при изменении формата планов: {e}")
        conn.rollback()
        return 0
    
    finally:
        # Закрываем соединение
        cursor.close()
        conn.close()

def show_user_plans(user_id):
    """
    Показывает все планы тренировок для указанного пользователя.
    
    Args:
        user_id: ID пользователя в базе данных
    """
    conn, cursor = connect_to_db()
    if not conn:
        return
    
    try:
        # Получаем все планы тренировок пользователя
        cursor.execute("SELECT id, plan_name, plan_data FROM training_plans WHERE user_id = %s", (user_id,))
        plans = cursor.fetchall()
        
        if not plans:
            logging.info(f"Планы тренировок для пользователя с ID {user_id} не найдены.")
            return
        
        # Выводим информацию о каждом плане
        for i, plan in enumerate(plans, 1):
            plan_id = plan['id']
            plan_name = plan['plan_name']
            plan_data = plan['plan_data']
            
            logging.info(f"{i}. План {plan_id}: {plan_name}")
            
            # Анализируем структуру plan_data
            if isinstance(plan_data, str):
                try:
                    parsed_data = json.loads(plan_data)
                    logging.info(f"   - Формат данных: строка JSON")
                    logging.info(f"   - Ключи: {list(parsed_data.keys()) if isinstance(parsed_data, dict) else 'Не словарь'}")
                    training_days_count = len(parsed_data.get('training_days', [])) if isinstance(parsed_data, dict) else 0
                    logging.info(f"   - Количество тренировочных дней: {training_days_count}")
                except json.JSONDecodeError:
                    logging.info(f"   - Формат данных: невалидный JSON")
            elif isinstance(plan_data, dict):
                logging.info(f"   - Формат данных: dict")
                logging.info(f"   - Ключи: {list(plan_data.keys())}")
                training_days_count = len(plan_data.get('training_days', []))
                logging.info(f"   - Количество тренировочных дней: {training_days_count}")
            else:
                logging.info(f"   - Формат данных: {type(plan_data)}")
    
    except Exception as e:
        logging.exception(f"Ошибка при получении информации о планах: {e}")
    
    finally:
        # Закрываем соединение
        cursor.close()
        conn.close()

def fix_plan_for_telegram_id(telegram_id):
    """
    Исправляет формат плана тренировок для пользователя с указанным Telegram ID.
    
    Args:
        telegram_id: Telegram ID пользователя
    
    Returns:
        bool: True если исправления успешны, иначе False
    """
    conn, cursor = connect_to_db()
    if not conn:
        return False
    
    try:
        # Находим пользователя по Telegram ID
        cursor.execute("SELECT id FROM users WHERE telegram_id = %s", (telegram_id,))
        user_result = cursor.fetchone()
        
        if not user_result:
            logging.error(f"Пользователь с Telegram ID {telegram_id} не найден.")
            return False
        
        user_id = user_result['id']
        
        # Выводим информацию о планах пользователя
        show_user_plans(user_id)
        
        # Изменяем формат планов
        num_plans_modified = modify_plan_format(user_id)
        
        logging.info(f"Всего изменено планов: {num_plans_modified}")
        return num_plans_modified > 0
    
    except Exception as e:
        logging.exception(f"Ошибка при исправлении планов: {e}")
        return False
    
    finally:
        # Закрываем соединение
        cursor.close()
        conn.close()

def main():
    """
    Основная функция для запуска скрипта
    """
    # ID пользователя koshvv в Telegram
    koshvv_telegram_id = 594077073
    
    # Исправляем формат планов
    success = fix_plan_for_telegram_id(koshvv_telegram_id)
    
    if success:
        logging.info("Формат планов тренировок успешно изменен!")
    else:
        logging.error("Не удалось изменить формат планов тренировок.")

if __name__ == "__main__":
    main()