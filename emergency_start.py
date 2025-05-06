#!/usr/bin/env python
"""
Экстренный запуск бота - максимально простой скрипт для обхода конфликтов и проблем
"""

import os
import logging
import sys
import requests
import time
from bot_modified import setup_bot

# Настройка базового логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/emergency.log")
    ]
)

logger = logging.getLogger('emergency_start')

def simple_reset_api():
    """Самый простой сброс API"""
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        logger.error("TELEGRAM_TOKEN отсутствует!")
        return
        
    # Удаляем вебхук
    try:
        url = f"https://api.telegram.org/bot{token}/deleteWebhook?drop_pending_updates=true"
        response = requests.get(url)
        logger.info(f"Webhook delete: {response.text}")
    except Exception as e:
        logger.error(f"Error: {e}")
    
    # Сбрасываем очередь
    try:
        url = f"https://api.telegram.org/bot{token}/getUpdates?offset=1"
        response = requests.get(url)
        logger.info(f"Reset queue: {response.status_code}")
    except Exception as e:
        logger.error(f"Error: {e}")

def main():
    """Основная функция запуска"""
    logger.info("=== ЭКСТРЕННЫЙ ЗАПУСК БОТА ===")
    
    # Сброс API
    simple_reset_api()
    
    # Небольшая пауза для полного сброса
    time.sleep(2)
    
    # Запуск бота
    logger.info("Запуск бота...")
    try:
        # Получаем настроенное приложение
        application = setup_bot()
        
        # Запускаем в режиме polling
        application.run_polling(drop_pending_updates=True)
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")
        logger.exception("Подробная информация об ошибке:")

if __name__ == "__main__":
    main()