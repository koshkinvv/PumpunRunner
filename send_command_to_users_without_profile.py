"""
Отправляет сообщение всем пользователям без профиля с инструкцией начать регистрацию.
Скрипт отслеживает, кому уже отправлены сообщения, чтобы не дублировать их.
"""
import asyncio
import os
import json
from telegram import Bot
from db_manager import DBManager
from config import TELEGRAM_TOKEN, logging
import psycopg2.extras
from datetime import datetime

# Настройка логирования для текущего модуля
logger = logging.getLogger(__name__)

# Файл для хранения ID пользователей, которым уже было отправлено сообщение
SENT_USERS_FILE = "notified_users.json"

def load_sent_users():
    """Загружает список ID пользователей, которым уже отправлены сообщения."""
    if os.path.exists(SENT_USERS_FILE):
        try:
            with open(SENT_USERS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка при загрузке списка оповещенных пользователей: {e}")
    return {"notified_users": [], "last_update": ""}

def save_sent_user(telegram_id):
    """Сохраняет ID пользователя в список оповещенных."""
    data = load_sent_users()
    if telegram_id not in data["notified_users"]:
        data["notified_users"].append(telegram_id)
        data["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(SENT_USERS_FILE, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            logger.error(f"Ошибка при сохранении списка оповещенных пользователей: {e}")

async def send_profile_creation_messages(limit=5):
    """
    Отправляет сообщения пользователям без профиля.
    
    Args:
        limit: Максимальное количество сообщений для отправки за один запуск
    """
    try:
        # Получаем токен бота
        token = TELEGRAM_TOKEN
        if not token:
            logger.error("Токен бота не найден. Убедитесь, что переменная окружения TELEGRAM_TOKEN установлена.")
            return
            
        # Создаем экземпляр бота
        bot = Bot(token=token)
        
        # Загружаем список пользователей, которым уже отправлены сообщения
        sent_data = load_sent_users()
        already_sent = sent_data["notified_users"]
        
        # Получаем список пользователей без профиля
        users_without_profile = []
        
        # Запрос для получения пользователей без профиля
        query = """
        SELECT u.id, u.telegram_id, u.first_name 
        FROM users u
        LEFT JOIN runner_profiles rp ON u.id = rp.user_id
        WHERE rp.id IS NULL
        """
        
        # Подключаемся к базе данных и получаем данные
        conn = None
        try:
            conn = DBManager.get_connection()
            if conn is None:
                logger.error("Не удалось подключиться к базе данных")
                return
                
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute(query)
                rows = cursor.fetchall()
                users_without_profile = [(row['id'], row['telegram_id'], row['first_name']) for row in rows]
                
        except Exception as e:
            logger.error(f"Ошибка при выполнении запроса к базе данных: {e}")
            return
        finally:
            if conn:
                conn.close()
        
        # Проверяем, есть ли пользователи без профиля
        if not users_without_profile:
            logger.info("Нет пользователей без профиля")
            return
        
        # Фильтруем список, исключая пользователей, которым уже отправлены сообщения
        users_to_notify = [(user_id, telegram_id, first_name) 
                          for user_id, telegram_id, first_name in users_without_profile 
                          if telegram_id not in already_sent]
            
        if not users_to_notify:
            logger.info("Всем пользователям без профиля уже отправлены сообщения")
            return
            
        logger.info(f"Найдено {len(users_to_notify)} пользователей без профиля, которым не отправлено сообщение")
        
        # Ограничиваем количество сообщений для текущего запуска
        users_for_current_run = users_to_notify[:limit]
        logger.info(f"В текущем запуске будет отправлено сообщений: {len(users_for_current_run)}")
        
        # Отправляем сообщения выбранным пользователям
        successful_messages = 0
        for user in users_for_current_run:
            user_id, telegram_id, first_name = user
            
            # Формируем текст сообщения
            message = (
                f"Привет{', ' + first_name if first_name else ''}! 👋\n\n"
                "Кажется, вы начали регистрацию в беговом боте, но не завершили создание профиля.\n\n"
                "Чтобы продолжить и получить персональный план тренировок, пожалуйста, "
                "нажмите команду /start.\n\n"
                "После создания профиля вы сможете:\n"
                "✅ Получить индивидуальный план тренировок\n"
                "✅ Отслеживать свой прогресс\n"
                "✅ Получать напоминания о тренировках\n\n"
                "Буду рад помочь вам достичь ваших беговых целей! 🏃‍♂️"
            )
            
            try:
                # Отправляем сообщение
                await bot.send_message(chat_id=telegram_id, text=message)
                logger.info(f"Отправлено сообщение пользователю {telegram_id} ({first_name})")
                
                # Сохраняем пользователя в список оповещенных
                save_sent_user(telegram_id)
                successful_messages += 1
                
                # Делаем паузу между сообщениями, чтобы избежать ограничений API
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Ошибка при отправке сообщения пользователю {telegram_id}: {e}")
        
        remaining = len(users_to_notify) - successful_messages
        logger.info(f"Всего отправлено сообщений: {successful_messages}")
        logger.info(f"Осталось отправить сообщений: {remaining}")
        
        if remaining > 0:
            logger.info("Для отправки оставшихся сообщений запустите скрипт еще раз")
        
    except Exception as e:
        logger.error(f"Произошла ошибка: {e}")

async def main():
    """Основная функция для запуска рассылки."""
    logger.info("Начинаем отправку сообщений пользователям без профиля")
    
    # Устанавливаем лимит сообщений для каждого запуска (10 сообщений)
    # Это поможет избежать тайм-аутов и ограничений Telegram API
    await send_profile_creation_messages(limit=10)
    
    logger.info("Отправка сообщений завершена")

if __name__ == "__main__":
    # Запускаем асинхронное приложение
    asyncio.run(main())