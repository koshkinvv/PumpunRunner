"""
Скрипт для исправления структуры плана тренировок для пользователя koshvv.
Исправляет конкретную проблему с базой данных.
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

def fix_plans_for_user(telegram_id):
    """
    Исправляет структуру плана тренировок для конкретного пользователя.
    
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
        
        # Получаем все планы тренировок пользователя
        cursor.execute("SELECT id, plan_data FROM training_plans WHERE user_id = %s", (user_id,))
        plans = cursor.fetchall()
        
        if not plans:
            logging.info(f"Планы тренировок для пользователя с ID {user_id} не найдены.")
            return False
        
        num_plans_fixed = 0
        
        for plan in plans:
            plan_id = plan['id']
            plan_data = plan['plan_data']
            
            try:
                # Проверяем, имеет ли план_data строковый формат
                if isinstance(plan_data, str):
                    try:
                        # Пытаемся преобразовать string в dict
                        parsed_data = json.loads(plan_data)
                        
                        # Проверяем структуру
                        if isinstance(parsed_data, dict):
                            if 'training_days' in parsed_data:
                                # Структура ОК
                                training_days = parsed_data['training_days']
                                
                                # Создаем новый формат
                                new_plan_data = {
                                    'training_days': training_days,
                                    'status': 'active'
                                }
                                
                                # Обновляем запись в базе данных
                                cursor.execute(
                                    "UPDATE training_plans SET plan_data = %s WHERE id = %s",
                                    (json.dumps(new_plan_data), plan_id)
                                )
                                num_plans_fixed += 1
                                logging.info(f"Исправлен план с ID {plan_id}")
                            else:
                                logging.warning(f"План с ID {plan_id} не содержит training_days, пропускаем")
                        
                        elif isinstance(parsed_data, list):
                            # Если это список тренировочных дней
                            # Создаем новый формат
                            new_plan_data = {
                                'training_days': parsed_data,
                                'status': 'active'
                            }
                            
                            # Обновляем запись
                            cursor.execute(
                                "UPDATE training_plans SET plan_data = %s WHERE id = %s",
                                (json.dumps(new_plan_data), plan_id)
                            )
                            num_plans_fixed += 1
                            logging.info(f"Исправлен план с ID {plan_id} (преобразование списка)")
                    
                    except json.JSONDecodeError:
                        logging.error(f"План с ID {plan_id} содержит невалидный JSON: {plan_data}")
                
                elif isinstance(plan_data, dict):
                    # Проверяем структуру существующего dict
                    if 'training_days' not in plan_data:
                        # Проверяем, возможно, есть вложенный plan_data
                        if 'plan_data' in plan_data and isinstance(plan_data['plan_data'], dict) and 'training_days' in plan_data['plan_data']:
                            # Извлекаем тренировочные дни из вложенной структуры
                            training_days = plan_data['plan_data']['training_days']
                            
                            # Создаем новый формат
                            new_plan_data = {
                                'training_days': training_days,
                                'status': 'active'
                            }
                            
                            # Обновляем запись
                            cursor.execute(
                                "UPDATE training_plans SET plan_data = %s WHERE id = %s",
                                (json.dumps(new_plan_data), plan_id)
                            )
                            num_plans_fixed += 1
                            logging.info(f"Исправлен план с ID {plan_id} (извлечение из вложенной структуры)")
                        else:
                            logging.warning(f"План с ID {plan_id} имеет неизвестную структуру: {plan_data.keys()}")
                    else:
                        logging.info(f"План с ID {plan_id} уже имеет правильную структуру")
                
                else:
                    logging.warning(f"План с ID {plan_id} имеет неожиданный тип данных: {type(plan_data)}")
            
            except Exception as e:
                logging.error(f"Ошибка при обработке плана с ID {plan_id}: {e}")
        
        # Фиксируем изменения
        conn.commit()
        logging.info(f"Всего исправлено планов: {num_plans_fixed}")
        return num_plans_fixed > 0
    
    except Exception as e:
        logging.exception(f"Ошибка при исправлении планов тренировок: {e}")
        conn.rollback()
        return False
    
    finally:
        # Закрываем соединение
        cursor.close()
        conn.close()

def create_fallback_plan_for_user(telegram_id):
    """
    Создает резервный план тренировок для пользователя.
    
    Args:
        telegram_id: Telegram ID пользователя
    
    Returns:
        bool: True если план создан успешно, иначе False
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
        
        # Создаем базовый план тренировок
        fallback_plan = {
            'plan_name': 'Резервный план тренировок',
            'plan_description': 'Базовый план бега для подготовки к соревнованиям',
            'training_days': [
                {
                    "day": "Понедельник",
                    "date": "10.05.2025",
                    "training_type": "Легкая пробежка",
                    "distance": "5 км",
                    "pace": "6:00-6:30 мин/км",
                    "description": "Легкая восстановительная пробежка в комфортном темпе."
                },
                {
                    "day": "Среда",
                    "date": "12.05.2025",
                    "training_type": "Темповая тренировка",
                    "distance": "7 км",
                    "pace": "5:30-6:00 мин/км",
                    "description": "Разминка 2 км, темповая часть 3 км, заминка 2 км."
                },
                {
                    "day": "Суббота",
                    "date": "15.05.2025",
                    "training_type": "Длительная пробежка",
                    "distance": "10 км",
                    "pace": "6:00-6:30 мин/км",
                    "description": "Длительная пробежка в аэробном темпе для развития выносливости."
                }
            ],
            'status': 'active'
        }
        
        # Сначала проверяем, есть ли уже планы у пользователя
        cursor.execute("SELECT COUNT(*) as count FROM training_plans WHERE user_id = %s", (user_id,))
        count_result = cursor.fetchone()
        
        if count_result and count_result['count'] > 0:
            logging.info(f"У пользователя с ID {user_id} уже есть планы тренировок. Пропускаем создание резервного.")
            return False
        
        # Вставляем новый план
        cursor.execute(
            "INSERT INTO training_plans (user_id, plan_name, plan_description, plan_data) VALUES (%s, %s, %s, %s)",
            (user_id, fallback_plan['plan_name'], fallback_plan['plan_description'], json.dumps(fallback_plan))
        )
        
        # Фиксируем изменения
        conn.commit()
        logging.info(f"Резервный план тренировок создан для пользователя с ID {user_id}")
        return True
    
    except Exception as e:
        logging.exception(f"Ошибка при создании резервного плана: {e}")
        conn.rollback()
        return False
    
    finally:
        # Закрываем соединение
        cursor.close()
        conn.close()

def main():
    """
    Основная функция для запуска исправлений
    """
    # Telegram ID пользователя koshvv
    koshvv_telegram_id = 594077073
    
    logging.info("Запуск исправления структуры плана тренировок для пользователя koshvv")
    
    # Пытаемся исправить существующие планы
    success = fix_plans_for_user(koshvv_telegram_id)
    
    if success:
        logging.info("Структура плана тренировок успешно исправлена")
    else:
        logging.warning("Не удалось исправить существующие планы или они отсутствуют")
        
        # Если не удалось исправить, создаем резервный план
        if create_fallback_plan_for_user(koshvv_telegram_id):
            logging.info("Создан резервный план тренировок для пользователя koshvv")
        else:
            logging.error("Не удалось создать резервный план")
    
    logging.info("Исправление завершено")

if __name__ == "__main__":
    main()