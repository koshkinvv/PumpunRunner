"""
Скрипт для проверки статуса плана тренировок и отправки поздравительного сообщения
с возможностью продолжения тренировок.
"""

import json
import os
import logging

from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton
from db_manager import DBManager
from training_plan_manager import TrainingPlanManager
from config import TELEGRAM_TOKEN

# Настройка логирования
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def check_plan_status_for_user(telegram_id, username=''):
    """
    Проверяет статус плана для конкретного пользователя и отправляет сообщение,
    если все тренировки выполнены или отменены.
    """
    try:
        # Инициализация бота
        bot = Bot(token=TELEGRAM_TOKEN)
        
        # Получение ID пользователя из базы данных
        db_user_id = DBManager.get_user_id(telegram_id)
        if not db_user_id:
            logger.info(f"Пользователь {username or telegram_id} не найден в базе данных")
            return
        
        # Получение последнего плана тренировок
        plan = TrainingPlanManager.get_latest_training_plan(db_user_id)
        if not plan:
            logger.info(f"План тренировок для пользователя {username or telegram_id} не найден")
            return
        
        # Получение списка выполненных и отмененных тренировок
        plan_id = plan['id']
        completed_days = TrainingPlanManager.get_completed_trainings(db_user_id, plan_id)
        canceled_days = TrainingPlanManager.get_canceled_trainings(db_user_id, plan_id)
        processed_days = completed_days + canceled_days
        
        # Количество тренировок в плане
        total_days = len(plan['plan_data']['training_days'])
        
        # Проверка, все ли тренировки выполнены или отменены
        has_pending_trainings = any(day_num not in processed_days for day_num in range(1, total_days + 1))
        
        logger.info(f"Пользователь: {username or telegram_id}")
        logger.info(f"План ID: {plan_id}")
        logger.info(f"Всего тренировок: {total_days}")
        logger.info(f"Выполнено: {len(completed_days)}")
        logger.info(f"Отменено: {len(canceled_days)}")
        logger.info(f"Ожидают выполнения: {True if has_pending_trainings else False}")
        
        # Если все тренировки выполнены или отменены, отправляем поздравительное сообщение
        if not has_pending_trainings:
            # Расчет общего пройденного расстояния
            total_distance = TrainingPlanManager.calculate_total_completed_distance(db_user_id, plan_id)
            
            # Обновление еженедельного объема в профиле пользователя
            new_volume = DBManager.update_weekly_volume(db_user_id, total_distance)
            
            # Создание кнопки для продолжения тренировок
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Продолжить тренировки", callback_data=f"continue_plan_{plan_id}")]
            ])
            
            # Отправка сообщения пользователю
            await bot.send_message(
                chat_id=telegram_id,
                text=(
                    f"🎉 Поздравляем! Все тренировки в вашем текущем плане выполнены или отменены!\n\n"
                    f"Вы пробежали в общей сложности {total_distance:.1f} км, и ваш еженедельный объем бега обновлен до {new_volume}.\n\n"
                    f"Хотите продолжить тренировки с учетом вашего прогресса?"
                ),
                reply_markup=keyboard
            )
            
            logger.info(f"Поздравительное сообщение отправлено пользователю {username or telegram_id}")
            return True
        
        logger.info(f"У пользователя {username or telegram_id} остались невыполненные тренировки")
        return False
        
    except Exception as e:
        logger.error(f"Ошибка при проверке статуса плана: {e}")
        return False

async def main():
    """Основная функция для запуска проверки"""
    # Пользователь, которого нужно проверить (id и имя)
    telegram_id = 594077073  # @koshvv
    username = "koshvv"
    
    # Запуск проверки
    result = await check_plan_status_for_user(telegram_id, username)
    logger.info(f"Результат проверки для {username}: {'Обработано успешно' if result else 'Не требует обработки'}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())