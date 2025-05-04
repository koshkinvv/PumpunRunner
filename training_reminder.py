#!/usr/bin/env python
"""
Скрипт для отправки напоминаний о предстоящих тренировках.
Проверяет наличие запланированных тренировок на следующий день
и отправляет уведомления в 20:00 по местному времени пользователя.
"""

import os
import logging
import asyncio
import datetime
import pytz
from telegram import Bot
from telegram.error import TelegramError
from db_manager import DBManager
from training_plan_manager import TrainingPlanManager
from config import TELEGRAM_TOKEN

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

class TrainingReminder:
    """Класс для работы с напоминаниями о тренировках."""
    
    def __init__(self):
        """Инициализация бота и настройка часового пояса по умолчанию."""
        self.bot = Bot(token=TELEGRAM_TOKEN)
        self.default_timezone = pytz.timezone('Europe/Moscow')  # Часовой пояс по умолчанию
    
    async def get_users_for_reminder(self):
        """
        Получает список пользователей, которым нужно отправить напоминание.
        
        Returns:
            list: Список словарей с информацией о пользователях и их тренировках на завтра
        """
        users = []
        
        try:
            # Получаем текущую дату в UTC
            utc_now = datetime.datetime.now(pytz.UTC)
            
            # Получаем все активные планы тренировок с информацией о пользователях
            active_plans = TrainingPlanManager.get_active_training_plans()
            
            for plan in active_plans:
                # Получаем информацию о пользователе из плана
                user_id = plan['user_id']
                telegram_id = plan['telegram_id']
                username = plan['username'] or ''
                first_name = plan['first_name'] or ''
                last_name = plan['last_name'] or ''
                timezone_str = plan['timezone'] or 'Europe/Moscow'
                
                # Определяем часовой пояс пользователя
                try:
                    user_timezone = pytz.timezone(timezone_str)
                except pytz.exceptions.UnknownTimeZoneError:
                    user_timezone = self.default_timezone
                    logger.warning(f"Неизвестный часовой пояс {timezone_str} для пользователя {user_id}, используем {self.default_timezone.zone}")
                
                # Конвертируем текущее время в часовой пояс пользователя
                local_now = utc_now.astimezone(user_timezone)
                
                # Проверяем, сейчас примерно 20:00 (±10 минут) по местному времени пользователя
                hour = local_now.hour
                minute = local_now.minute
                
                logger.debug(f"Пользователь {user_id}: время {hour}:{minute}, часовой пояс {user_timezone.zone}")
                
                if 19 <= hour <= 20 and (hour < 20 or minute <= 10):
                    # Получаем дату завтрашнего дня в формате DD.MM.YYYY
                    tomorrow = (local_now + datetime.timedelta(days=1)).strftime("%d.%m.%Y")
                    logger.info(f"Ищем тренировки на завтра ({tomorrow}) для пользователя {user_id}")
                    
                    if 'plan_data' in plan and 'training_days' in plan['plan_data']:
                        # Получаем выполненные и отмененные дни тренировок
                        completed = TrainingPlanManager.get_completed_trainings(user_id, plan['id'])
                        canceled = TrainingPlanManager.get_canceled_trainings(user_id, plan['id'])
                        processed_days = completed + canceled
                        
                        # Ищем тренировку на завтра
                        for idx, day in enumerate(plan['plan_data']['training_days']):
                            day_num = idx + 1
                            
                            # Проверяем, есть ли тренировка на завтра, которая еще не выполнена и не отменена
                            if day['date'] == tomorrow and day_num not in processed_days:
                                logger.info(f"Найдена тренировка для пользователя {user_id} на завтра ({tomorrow}): день {day_num}")
                                
                                # Добавляем пользователя в список для отправки напоминаний
                                users.append({
                                    'user_id': user_id,
                                    'telegram_id': telegram_id,
                                    'username': username,
                                    'first_name': first_name,
                                    'last_name': last_name,
                                    'training_day': day,
                                    'day_num': day_num,
                                    'plan_id': plan['id']
                                })
                                break
            
        except Exception as e:
            logger.error(f"Ошибка при получении пользователей для напоминаний: {e}", exc_info=True)
        
        return users
    
    async def send_reminder(self, user_info):
        """
        Отправляет напоминание о предстоящей тренировке.
        
        Args:
            user_info (dict): Информация о пользователе и тренировке
        """
        try:
            telegram_id = user_info['telegram_id']
            training = user_info['training_day']
            day_num = user_info['day_num']
            plan_id = user_info['plan_id']
            
            # Формируем сообщение с напоминанием
            message = (
                f"🔔 *Напоминание о завтрашней тренировке!*\n\n"
                f"Завтра у вас запланирована тренировка:\n\n"
                f"*День {day_num}: {training['day']} ({training['date']})*\n"
                f"Тип: {training['training_type']}\n"
                f"Дистанция: {training['distance']}\n"
                f"Темп: {training['pace']}\n\n"
                f"{training['description']}\n\n"
                f"Подготовьтесь заранее и не забудьте отметить тренировку как выполненную после завершения! "
                f"Также вы можете загрузить скриншот из вашего трекера тренировок для автоматической отметки."
            )
            
            # Отправляем сообщение пользователю
            await self.bot.send_message(
                chat_id=telegram_id,
                text=message,
                parse_mode='Markdown'
            )
            
            logger.info(f"Отправлено напоминание пользователю {telegram_id} о тренировке на {training['date']}")
            
        except TelegramError as e:
            logger.error(f"Ошибка Telegram при отправке напоминания пользователю {user_info['telegram_id']}: {e}")
        except Exception as e:
            logger.error(f"Ошибка при отправке напоминания: {e}")
    
    async def process_reminders(self):
        """Основной метод для обработки и отправки напоминаний."""
        logger.info("Начинаем проверку и отправку напоминаний о тренировках")
        
        try:
            # Получаем пользователей для напоминания
            users = await self.get_users_for_reminder()
            
            if not users:
                logger.info("Нет пользователей для отправки напоминаний на текущий момент")
                return
            
            logger.info(f"Найдено {len(users)} пользователей для отправки напоминаний")
            
            # Отправляем напоминания всем пользователям
            for user in users:
                await self.send_reminder(user)
                # Добавляем небольшую паузу между отправками
                await asyncio.sleep(0.5)
            
            logger.info("Отправка напоминаний завершена")
            
        except Exception as e:
            logger.error(f"Ошибка при обработке напоминаний: {e}")


async def main():
    """Основная функция для запуска процесса отправки напоминаний."""
    reminder = TrainingReminder()
    await reminder.process_reminders()


if __name__ == "__main__":
    # Запускаем асинхронный обработчик
    asyncio.run(main())