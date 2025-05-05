"""
Модуль для напоминаний о предстоящих тренировках.
Отправляет пользователям сообщения каждый день в 20:00 о тренировках, запланированных на следующий день.
"""

import logging
import os
import sys
import asyncio
import pytz
from datetime import datetime, timedelta
from telegram import Bot
from telegram.error import TelegramError

from db_manager import DBManager
from training_plan_manager import TrainingPlanManager
from config import TELEGRAM_TOKEN

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Московский часовой пояс
MOSCOW_TZ = pytz.timezone('Europe/Moscow')

# Время отправки напоминаний (20:00 по МСК)
REMINDER_HOUR = 20
REMINDER_MINUTE = 0

async def get_next_day_trainings():
    """
    Получает все тренировки, запланированные на следующий день.
    
    Returns:
        List of tuples: [(telegram_id, plan_id, training_day)]
    """
    logging.info("Ищем тренировки на завтра")
    try:
        # Получаем текущую дату в МСК
        today = datetime.now(MOSCOW_TZ).date()
        tomorrow = today + timedelta(days=1)
        tomorrow_str = tomorrow.strftime("%d.%m.%Y")
        
        logging.info(f"Ищем тренировки на дату: {tomorrow_str}")
        
        # Получаем всех пользователей с активными планами тренировок
        all_users = []
        try:
            all_users = DBManager.get_all_users_with_plans()
            logging.info(f"Найдено {len(all_users)} пользователей с планами тренировок")
        except Exception as e:
            logging.error(f"Ошибка при получении пользователей с планами: {e}")
            return []
        
        # Результаты - список кортежей: (telegram_id, plan_id, training_day)
        results = []
        
        for user in all_users:
            try:
                user_id = user['id']
                telegram_id = user['telegram_id']
                
                # Получаем последний план пользователя
                latest_plan = TrainingPlanManager.get_latest_training_plan(user_id)
                if not latest_plan:
                    logging.info(f"У пользователя {telegram_id} нет активного плана тренировок")
                    continue
                
                plan_id = latest_plan['id']
                training_days = latest_plan['plan_data'].get('training_days', [])
                
                # Получаем обработанные тренировки
                completed = TrainingPlanManager.get_completed_trainings(user_id, plan_id)
                canceled = TrainingPlanManager.get_canceled_trainings(user_id, plan_id)
                processed_days = completed + canceled
                
                # Ищем тренировки на следующий день
                for idx, day in enumerate(training_days):
                    day_num = idx + 1
                    
                    # Пропускаем уже обработанные дни
                    if day_num in processed_days:
                        continue
                    
                    # Если дата совпадает с завтрашней
                    if day.get('date') == tomorrow_str:
                        logging.info(f"Найдена тренировка для пользователя {telegram_id}: День {day_num}, {day.get('training_type')}")
                        results.append((telegram_id, plan_id, day))
            except Exception as e:
                logging.error(f"Ошибка при обработке пользователя {user.get('telegram_id', 'Unknown')}: {e}")
        
        logging.info(f"Всего найдено {len(results)} тренировок на завтра")
        return results
    
    except Exception as e:
        logging.error(f"Общая ошибка при поиске тренировок на завтра: {e}")
        return []

async def send_training_reminder(telegram_id, training_day):
    """
    Отправляет напоминание о тренировке пользователю.
    
    Args:
        telegram_id: ID пользователя в Telegram
        training_day: Данные о дне тренировки из плана
    """
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        
        # Формируем текст напоминания
        reminder_text = (
            f"⏰ *Напоминание о тренировке завтра!*\n\n"
            f"Завтра у вас запланирована тренировка:\n\n"
            f"*{training_day['day']} ({training_day['date']})*\n"
            f"Тип: {training_day['training_type']}\n"
            f"Дистанция: {training_day['distance']}\n"
            f"Темп: {training_day['pace']}\n\n"
            f"{training_day['description']}\n\n"
            f"Удачной тренировки! 💪"
        )
        
        # Отправляем сообщение
        await bot.send_message(
            chat_id=telegram_id,
            text=reminder_text,
            parse_mode='Markdown'
        )
        logging.info(f"Напоминание отправлено пользователю {telegram_id}")
        return True
    
    except TelegramError as te:
        logging.error(f"Ошибка Telegram при отправке напоминания пользователю {telegram_id}: {te}")
        return False
    
    except Exception as e:
        logging.error(f"Общая ошибка при отправке напоминания пользователю {telegram_id}: {e}")
        return False

async def send_reminders():
    """
    Находит все тренировки на следующий день и отправляет напоминания пользователям.
    """
    logging.info("Запуск отправки напоминаний о тренировках")
    try:
        # Получаем тренировки на завтра
        trainings = await get_next_day_trainings()
        
        if not trainings:
            logging.info("Нет тренировок на завтра, напоминания не требуются")
            return
        
        # Счетчики для статистики
        successful = 0
        failed = 0
        
        # Отправляем напоминания
        for telegram_id, plan_id, training_day in trainings:
            result = await send_training_reminder(telegram_id, training_day)
            if result:
                successful += 1
            else:
                failed += 1
        
        logging.info(f"Отправка напоминаний завершена. Успешно: {successful}, Ошибки: {failed}")
    
    except Exception as e:
        logging.error(f"Ошибка при отправке напоминаний: {e}")

async def schedule_reminders():
    """
    Планирует отправку напоминаний каждый день в 20:00 по МСК.
    """
    while True:
        try:
            # Текущее время в МСК
            now = datetime.now(MOSCOW_TZ)
            logging.info(f"Текущее время: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            
            # Вычисляем время следующего запуска
            next_run = now.replace(hour=REMINDER_HOUR, minute=REMINDER_MINUTE, second=0, microsecond=0)
            
            # Если текущее время уже после запланированного на сегодня, переходим на завтра
            if now >= next_run:
                next_run = next_run + timedelta(days=1)
            
            # Вычисляем сколько секунд ждать до следующего запуска
            wait_seconds = (next_run - now).total_seconds()
            
            logging.info(f"Следующая отправка напоминаний запланирована на {next_run.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            logging.info(f"Ожидание {wait_seconds:.1f} секунд до следующей отправки")
            
            # Ожидаем до запланированного времени
            await asyncio.sleep(wait_seconds)
            
            # Выполняем отправку напоминаний
            await send_reminders()
            
            # Небольшая пауза, чтобы не отправлять уведомления дважды
            await asyncio.sleep(60)
        
        except Exception as e:
            logging.error(f"Ошибка в планировщике напоминаний: {e}")
            # Пауза перед повторной попыткой
            await asyncio.sleep(60)

async def main():
    """
    Основная функция для запуска планировщика напоминаний.
    """
    logging.info("Запуск сервиса напоминаний о тренировках")
    
    # Добавляем метод в DBManager для получения всех пользователей с планами
    if not hasattr(DBManager, 'get_all_users_with_plans'):
        logging.warning("Метод get_all_users_with_plans отсутствует в DBManager. Напоминания не будут работать!")
        return
    
    # Запускаем бесконечный цикл планирования
    await schedule_reminders()

if __name__ == "__main__":
    asyncio.run(main())