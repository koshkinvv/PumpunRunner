#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт для запуска бота с улучшенным форматированием тренировок.
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

# Импортируем улучшенный модуль бота
import enhanced_bot as bot

async def main():
    """Основная функция для запуска бота."""
    try:
        logger.info("Запуск бота с улучшенным форматированием тренировок")
        
        # Настраиваем бота
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
