#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт для запуска бота с улучшенным форматированием тренировок.
Использует очищенную версию файла bot_modified_clean.py.
"""

import os
import sys
import logging
import asyncio
import signal
import time
from telegram.ext import ApplicationBuilder

# Настраиваем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Импортируем необходимые функции
from config import TELEGRAM_TOKEN

def signal_handler(sig, frame):
    """Обработчик сигналов для корректного завершения."""
    logger.info("Получен сигнал завершения, останавливаю бота...")
    sys.exit(0)

async def run_bot():
    """Функция для запуска бота."""
    try:
        # Регистрируем обработчик сигналов
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Инициализируем бота
        logger.info("Инициализация бота с улучшенным форматированием тренировок...")
        
        # Импортируем функции из cleaned файла
        from bot_modified_clean import setup_bot
        
        # Создаем экземпляр приложения
        app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        
        # Настраиваем обработчики
        setup_bot(app)
        
        # Запускаем бота
        logger.info("Бот успешно запущен и готов принимать сообщения")
        
        # Сохраняем PID для мониторинга
        with open("bot.pid", "w") as f:
            f.write(str(os.getpid()))
        
        # Запускаем бота в режиме long polling
        await app.run_polling(allowed_updates=["message", "callback_query", "my_chat_member"])
    
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске бота: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        # Запускаем бота
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Необработанная ошибка: {e}")
        sys.exit(1)