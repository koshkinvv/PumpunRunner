"""
Скрипт для отправки команды создания нового профиля пользователю @Ploskym.
"""
import os
import sys
import logging
import asyncio
from telegram import Bot

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def send_message_to_user():
    """Отправляет сообщение пользователю @Ploskym для начала создания профиля."""
    try:
        # Получаем токен из переменных окружения
        token = os.environ.get("TELEGRAM_TOKEN")
        if not token:
            logger.error("TELEGRAM_TOKEN не найден в переменных окружения")
            return
        
        # Создаем экземпляр бота
        bot = Bot(token=token)
        
        # Получаем ID пользователя из базы данных
        import psycopg2
        conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
        cursor = conn.cursor()
        
        cursor.execute('SELECT telegram_id FROM users WHERE username = %s', ('Ploskym',))
        user = cursor.fetchone()
        
        if not user:
            logger.error('Пользователь @Ploskym не найден')
            return
            
        telegram_id = user[0]
        logger.info(f"Найден пользователь @Ploskym с telegram_id: {telegram_id}")
        
        # Отправляем сообщение для начала создания профиля
        message = "Давайте создадим ваш профиль! Для начала, скажите, на какую дистанцию вы тренируетесь? (например, 5 км, 10 км, полумарафон, марафон)"
        
        await bot.send_message(
            chat_id=telegram_id, 
            text=message
        )
        
        logger.info(f"Сообщение успешно отправлено пользователю @Ploskym (telegram_id: {telegram_id})")
        
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения: {e}", exc_info=True)
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    # Запускаем отправку сообщения
    asyncio.run(send_message_to_user())