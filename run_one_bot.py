#!/usr/bin/env python
"""
Самый простой запуск бота - просто запускает и ничего больше не делает.
"""
import os
import sys
import logging
from telegram.ext import ApplicationBuilder

# Базовое логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/run_one_bot.log")
    ]
)

logger = logging.getLogger('run_one_bot')

def main():
    """Простой запуск бота"""
    logger.info("Запуск простого бота")
    
    # Получаем токен
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        logger.error("TELEGRAM_TOKEN отсутствует!")
        return
    
    # Создаем приложение
    try:
        from bot_modified import setup_bot
        
        # Получаем настроенное приложение
        app = setup_bot()
        
        # Запускаем без лишнего функционала
        app.run_polling(drop_pending_updates=True)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        logger.exception("Детали ошибки:")

if __name__ == "__main__":
    main()