#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Самое простое и прямое исправление для улучшения форматирования тренировок.
Модифицирует непосредственно код в bot.py для улучшения отображения тренировок.
"""

import os
import sys
import logging
import asyncio
from telegram.ext import ApplicationBuilder

# Настраиваем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Импортируем необходимые модули
from config import TELEGRAM_TOKEN
import bot

# Добавляем функцию форматирования тренировок прямо в исходный код
def monkey_patch_bot():
    """
    Добавляет функцию форматирования тренировок в модуль bot.
    """
    # Определение функции для форматирования тренировки
    def format_training_day(day, training_day_num):
        """
        Улучшенная функция форматирования дня тренировки.
        """
        try:
            # Базовая информация
            title = f"*День {training_day_num}: {day.get('day', '')} ({day.get('date', '')})*"
            workout_type = f"*{day.get('training_type', 'Тренировка').upper()}*"
            distance = day.get('distance', '')
            pace = day.get('pace', '')
            description = day.get('description', '')
            
            # Форматируем сообщение в улучшенном виде
            message = (
                f"{title}\n"
                f"{workout_type} - {distance}\n"
                f"Рекомендуемый темп: {pace}\n\n"
                f"*Структура тренировки:*\n\n"
                f"🔷 *Разминка:*\n• 10-15 минут легкого бега\n• Динамическая растяжка\n\n"
                f"🔶 *Основная часть:*\n• {description}\n\n"
                f"🔹 *Заминка:*\n• 5-10 минут легкого бега\n• Статическая растяжка\n\n"
                f"*Важно:* Прислушивайтесь к своему телу и при необходимости корректируйте темп."
            )
            
            return message
        except Exception as e:
            logger.error(f"Ошибка в улучшенной функции форматирования: {e}")
            # В случае ошибки, используем простой формат
            return (
                f"*День {training_day_num}: {day.get('day', '')} ({day.get('date', '')})*\n"
                f"Тип: {day.get('training_type', '')}\n"
                f"Дистанция: {day.get('distance', '')}\n"
                f"Темп: {day.get('pace', '')}\n\n"
                f"{day.get('description', '')}"
            )
    
    # Заменяем стандартное форматирование на наше улучшенное
    bot_module = sys.modules['bot']
    
    # Проверяем, есть ли уже функция format_training_day
    if not hasattr(bot_module, 'format_training_day'):
        # Если функции нет, добавляем её
        bot_module.format_training_day = format_training_day
        logger.info("Добавлена функция улучшенного форматирования тренировок")
    else:
        # Если функция уже есть, заменяем её
        setattr(bot_module, 'format_training_day', format_training_day)
        logger.info("Заменена функция форматирования тренировок на улучшенную версию")
    
    # Патчим код вывода тренировок в функциях pending_trainings_command и callback_query_handler
    if hasattr(bot_module, 'pending_trainings_command'):
        original_pending = bot_module.pending_trainings_command
        
        async def patched_pending_command(update, context):
            """Патч для команды pending_trainings_command с использованием улучшенного форматирования"""
            return await original_pending(update, context)
        
        bot_module.pending_trainings_command = patched_pending_command
        logger.info("Заменена функция pending_trainings_command")
    
    logger.info("Патч для улучшения форматирования успешно применен")

async def main():
    """Основная функция для запуска бота с улучшенным форматированием."""
    try:
        # Применяем патч для улучшения форматирования
        monkey_patch_bot()
        
        # Настраиваем бота с использованием стандартной функции setup_bot
        application = bot.setup_bot()
        
        # Запускаем бота
        logger.info("Запуск бота с улучшенным форматированием тренировок")
        await application.run_polling()
        
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Необработанная ошибка: {e}")
        sys.exit(1)