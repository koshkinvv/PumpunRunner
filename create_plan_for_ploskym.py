"""
Скрипт для создания тренировочного плана для пользователя ploskym и его сохранения в базе данных.
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

# Добавляем текущую директорию в путь поиска модулей
sys.path.append('.')

def generate_training_plan():
    """Генерирует и сохраняет тренировочный план для пользователя ploskym."""
    try:
        from openai_service import OpenAIService
        
        logger.info("Импортирован модуль OpenAIService")
        
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
        
        # Получаем профиль пользователя
        cursor.execute("""
            SELECT 
                id, user_id, distance, competition_date, gender, age, 
                height, weight, experience, goal, target_time, 
                fitness_level, comfortable_pace, weekly_volume, 
                training_start_date, training_days_per_week, 
                preferred_training_days
            FROM runner_profiles 
            WHERE user_id = %s
        """, (user_id,))
        
        columns = [desc[0] for desc in cursor.description]
        profile = cursor.fetchone()
        
        if not profile:
            logger.error('Профиль для пользователя ploskym не найден')
            return
            
        # Преобразуем результат запроса в словарь
        profile_data = dict(zip(columns, profile))
        logger.info(f"Получен профиль: {json.dumps(profile_data, default=str)}")
        
        # Создаем экземпляр сервиса OpenAI
        logger.info("Создание экземпляра OpenAIService")
        openai_service = OpenAIService()
        
        # Генерируем план тренировок
        logger.info("Начинаем генерацию плана тренировок")
        plan = openai_service.generate_training_plan(profile_data)
        
        if not plan:
            logger.error('Не удалось сгенерировать план тренировок')
            return
        
        logger.info("План тренировок успешно сгенерирован")
            
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
    # Запускаем генерацию плана
    generate_training_plan()