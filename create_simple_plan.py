"""
Скрипт для создания простого тренировочного плана для пользователя ploskym и его сохранения в базе данных.
"""
import os
import sys
import json
import psycopg2
import logging
from datetime import datetime, timedelta

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_simple_plan():
    """Создает и сохраняет простой тренировочный план для пользователя ploskym."""
    try:
        # Подключение к базе данных
        conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
        cursor = conn.cursor()
        
        logger.info("Подключение к базе данных установлено")
        
        # Получаем ID пользователя
        cursor.execute('SELECT id FROM users WHERE username = %s', ('ploskym',))
        user = cursor.fetchone()
        
        if not user:
            logger.error('Пользователь ploskym не найден')
            return
            
        user_id = user[0]
        logger.info(f"Найден пользователь ploskym с ID: {user_id}")
        
        # Получаем профиль пользователя для получения предпочитаемых дней
        cursor.execute("""
            SELECT 
                preferred_training_days, training_start_date
            FROM runner_profiles 
            WHERE user_id = %s
        """, (user_id,))
        
        profile = cursor.fetchone()
        
        if not profile:
            logger.error('Профиль для пользователя ploskym не найден')
            return
            
        preferred_days = profile[0].split(',')
        start_date_str = profile[1]
        
        # Парсим дату начала тренировок
        try:
            start_date = datetime.strptime(start_date_str, '%d.%m.%Y')
        except ValueError:
            start_date = datetime.now()
        
        # Создаем план тренировок на 7 дней
        plan = {
            "meta": {
                "user_id": user_id,
                "distance": 21.0,
                "goal": "Просто финишировать",
                "target_time": "1:35:59",
                "weekly_volume": 20.0,
                "training_days_per_week": 6
            },
            "plan": []
        }
        
        # Типы тренировок
        training_types = [
            "Легкий бег",
            "Интервальная тренировка",
            "Темповый бег",
            "Длительный бег",
            "Восстановительный бег",
            "Длительный бег"
        ]
        
        # Добавляем тренировки в план
        current_date = start_date
        for i in range(6):
            # Форматируем дату
            date_str = current_date.strftime('%d.%m.%Y')
            day_of_week = current_date.strftime('%A')
            
            # Определяем расстояние в зависимости от типа тренировки
            if "Легкий" in training_types[i] or "Восстановительный" in training_types[i]:
                distance = 3.0
            elif "Интервальная" in training_types[i]:
                distance = 5.0
            elif "Темповый" in training_types[i]:
                distance = 6.0
            else:  # Длительный
                distance = 8.0
                
            # Формируем дневную тренировку
            day = {
                "id": f"day_{i+1}",
                "date": date_str,
                "day_of_week": day_of_week,
                "type": training_types[i],
                "distance": distance,
                "status": "pending",
                "description": f"Тренировка {i+1}: {training_types[i]} {distance} км",
                "purpose": f"Цель: развитие {('выносливости' if i % 2 == 0 else 'скорости')}",
                "warmup": "Разминка: 10 минут легкий бег, динамическая растяжка",
                "main_workout": f"Основная часть: {training_types[i]} {distance} км",
                "cooldown": "Заминка: 5 минут легкий бег, статическая растяжка",
                "tips": "Совет: следите за правильной техникой бега"
            }
            
            plan["plan"].append(day)
            current_date += timedelta(days=1)
        
        # Сохраняем план тренировок в базу данных
        plan_json = json.dumps(plan)
        
        cursor.execute(
            'INSERT INTO training_plans (user_id, plan_data, created_at) VALUES (%s, %s, %s) RETURNING id',
            (user_id, plan_json, datetime.now())
        )
        
        plan_id = cursor.fetchone()[0]
        
        # Подтверждаем транзакцию
        conn.commit()
        
        logger.info(f'План тренировок успешно сохранен (ID: {plan_id})')
        logger.info(f'Содержимое плана: {json.dumps(plan, indent=2, ensure_ascii=False)}')
        
        return plan
        
    except Exception as e:
        logger.error(f'Ошибка: {e}', exc_info=True)
        if 'conn' in locals():
            conn.rollback()
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    # Запускаем создание плана
    create_simple_plan()