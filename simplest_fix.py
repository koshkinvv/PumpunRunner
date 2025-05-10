#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Самый простой способ интеграции улучшенного форматирования тренировок.
Вносит минимальные изменения в оригинальный код.
"""

import asyncio
import logging
from telegram.ext import ApplicationBuilder

# Настраиваем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

from config import TELEGRAM_TOKEN

# Модифицируем функцию вывода дней тренировки в bot.py
import bot

# Создаем функцию для форматирования тренировок напрямую в модуле bot
def format_training_day(day, training_day_num):
    """
    Улучшенная функция для форматирования дня тренировки.
    Эта функция будет добавлена в модуль bot.
    """
    try:
        # Основная информация о тренировке
        day_date = day.get('date', 'Дата не указана')
        day_name = day.get('day', day.get('day_of_week', f'День {training_day_num}'))
        training_type = day.get('training_type', day.get('type', 'Тип не указан'))
        distance = day.get('distance', 'Дистанция не указана')
        pace = day.get('pace', 'Темп не указан')
        description = day.get('description', '')
        
        # Структура тренировки
        title = f"*{day_name.upper()}: {training_type.upper()} ({distance})*"
        
        # Разделение на части
        warmup = f"1. Разминка (1 км):\n• 10-15 минут легкого бега\n• Динамическая растяжка"
        
        # Основная часть
        main_part = f"2. Основная часть ({distance}):\n• {description}\n• Поддерживайте темп: {pace}"
        
        # Заминка
        cooldown = f"3. Заминка (1 км):\n• 5-10 минут легкого бега\n• Растяжка основных мышечных групп"
        
        # Формируем полное сообщение
        message = f"{title}\n\n{warmup}\n\n{main_part}\n\n{cooldown}"
        
        return message
    except Exception as e:
        logger.error(f"Ошибка при форматировании дня тренировки: {e}")
        # В случае ошибки возвращаем базовый формат
        return (
            f"*День {training_day_num}: {day.get('training_type', 'Тренировка')} ({day.get('distance', '?')})*\n"
            f"Дата: {day.get('date', 'Не указана')}\n"
            f"Темп: {day.get('pace', 'Не указан')}\n\n"
            f"{day.get('description', 'Описание отсутствует')}"
        )

# Патчим функцию в модуле bot
# Это самый простой и прямой метод монки-патчинга
bot_module_globals = globals()['bot'].__dict__
bot_module_globals['format_training_day'] = format_training_day

async def main():
    """Точка входа для запуска бота с улучшенным форматированием."""
    try:
        logger.info("Запуск бота с улучшенным форматированием тренировок")
        
        # Создаем и настраиваем бота
        application = bot.setup_bot()
        
        # Запускаем бота
        await application.run_polling()
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Необработанная ошибка: {e}")