#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт для запуска бота с улучшенным форматированием тренировок.
Использует улучшенную функцию format_training_day из improved_training_format.py.
"""

import os
import sys
import logging
import asyncio
import signal
from telegram.ext import ApplicationBuilder

# Настраиваем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Импортируем необходимые модули
from bot_modified import setup_bot
from config import TELEGRAM_TOKEN
from improved_training_format import format_training_day

async def main():
    """
    Основная функция для запуска бота с улучшенным форматированием.
    """
    try:
        logger.info("Запуск бота с улучшенным форматом тренировок...")
        
        # Устанавливаем обработчик сигналов для корректного завершения
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        
        # Инициализируем бота
        application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        
        # Регистрируем обработчики из стандартной конфигурации
        setup_bot(application)
        
        # Запускаем бота в режиме long polling
        logger.info("Бот запущен и готов принимать сообщения")
        await application.run_polling(allowed_updates=["message", "callback_query", "my_chat_member"])
        
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        # Записываем PID процесса для мониторинга
        with open("bot.pid", "w") as f:
            f.write(str(os.getpid()))
        
        # Запускаем основную функцию
        asyncio.run(main())
        
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)