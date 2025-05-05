#!/usr/bin/env python
"""
Прямой запуск бота без промежуточных скриптов.
Файл для ручного запуска в случае проблем с другими скриптами.
"""

import os
import sys
import time
import signal
import logging
import requests
import json
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ConversationHandler, MessageHandler, filters
from bot_modified import setup_bot

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/direct_start.log")
    ]
)

logger = logging.getLogger('direct_start')

def reset_telegram_api_session():
    """Сбрасывает сессию Telegram API."""
    token = os.environ.get('TELEGRAM_TOKEN')
    if not token:
        logger.error("TELEGRAM_TOKEN не найден!")
        return False
    
    logger.info("Сброс сессии Telegram API...")
    
    # 1. Удаляем вебхук
    try:
        webhook_url = f"https://api.telegram.org/bot{token}/deleteWebhook?drop_pending_updates=true"
        response = requests.get(webhook_url)
        logger.info(f"Удаление вебхука: {response.text}")
    except Exception as e:
        logger.error(f"Ошибка при удалении вебхука: {e}")
    
    # 2. Сброс очереди обновлений
    for offset in range(1, 5):
        try:
            url = f"https://api.telegram.org/bot{token}/getUpdates?offset={offset}"
            response = requests.get(url)
            logger.info(f"Сброс с offset={offset}: {response.status_code}")
            time.sleep(1)
        except Exception as e:
            logger.error(f"Ошибка при сбросе с offset={offset}: {e}")
    
    # Ожидаем для полного сброса
    time.sleep(2)
    return True

def main():
    """Основная функция запуска бота."""
    logger.info("=" * 50)
    logger.info("ПРЯМОЙ ЗАПУСК БОТА")
    logger.info("=" * 50)
    
    # Сбрасываем сессию Telegram API
    reset_telegram_api_session()
    
    # Создаем и настраиваем бота
    token = os.environ.get('TELEGRAM_TOKEN')
    if not token:
        logger.error("TELEGRAM_TOKEN не найден!")
        return
    
    try:
        # Получаем приложение с настроенными обработчиками
        logger.info("Настройка бота...")
        bot_app = setup_bot()
        
        # Запускаем бота в режиме polling
        logger.info("Запуск бота...")
        bot_app.run_polling()
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")

if __name__ == "__main__":
    main()