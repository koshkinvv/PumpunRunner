#!/usr/bin/env python
"""
Простой скрипт для запуска Telegram бота.
Этот файл запускает только сам бот без дополнительных компонентов.
"""

import sys
import os
import logging
import traceback
import importlib
import time

# Настройка логирования в файл и консоль
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/bot_launcher.log")
    ]
)

logger = logging.getLogger("telegram_bot_launcher")

def main():
    """Основная функция для запуска бота."""
    # Создаем директорию для логов, если она не существует
    os.makedirs("logs", exist_ok=True)

    logger.info("Запуск Telegram бота...")
    
    try:
        # Импортируем setup_bot из bot_modified.py
        from bot_modified import setup_bot
        
        # Получаем экземпляр приложения бота
        application = setup_bot()
        
        # Запускаем поллинг для получения обновлений
        logger.info("Запуск бота в режиме поллинга...")
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=None,
            close_loop=False,
            timeout=60
        )
    except ImportError as e:
        logger.error(f"Ошибка импорта: {e}")
        logger.error(traceback.format_exc())
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")
        logger.error(traceback.format_exc())
    
    logger.info("Завершение работы Telegram бота")

if __name__ == "__main__":
    main()