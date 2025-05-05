#!/usr/bin/env python
"""
Скрипт для прямого запуска бота в одном процессе.
Оптимизирован для использования в workflow bot_runner.
"""

import os
import sys
import time
import logging
import requests
import json
from bot_modified import setup_bot

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/start_bot_directly.log")
    ]
)

logger = logging.getLogger('start_bot_directly')

def reset_telegram_api():
    """
    Сбрасывает сессию Telegram API перед запуском.
    """
    token = os.environ.get('TELEGRAM_TOKEN')
    if not token:
        logger.error("TELEGRAM_TOKEN не найден!")
        return False
    
    logger.info("Сброс сессии Telegram API...")
    
    # Удаляем вебхук
    try:
        webhook_url = f"https://api.telegram.org/bot{token}/deleteWebhook?drop_pending_updates=true"
        response = requests.get(webhook_url)
        logger.info(f"Удаление вебхука: {response.text}")
    except Exception as e:
        logger.error(f"Ошибка при удалении вебхука: {e}")
    
    # Сбрасываем getUpdates
    for offset in range(1, 10):
        try:
            url = f"https://api.telegram.org/bot{token}/getUpdates?offset={offset*10}&limit=100"
            response = requests.get(url)
            logger.info(f"Сброс с offset={offset*10}: {response.status_code}")
            
            # Если успешно, можем прервать цикл
            if response.status_code == 200:
                data = json.loads(response.text)
                if data.get("ok", False) and len(data.get("result", [])) == 0:
                    if offset >= 3:  # Минимум 3 успешных запроса
                        break
            
            time.sleep(2)
        except Exception as e:
            logger.error(f"Ошибка при сбросе с offset={offset}: {e}")
    
    # Даем API время на обработку
    time.sleep(5)
    return True

def main():
    """
    Основная функция запуска бота.
    """
    logger.info("=" * 50)
    logger.info("ПРЯМОЙ ЗАПУСК БОТА ДЛЯ WORKFLOW")
    logger.info("=" * 50)
    
    # Сбрасываем сессию API
    reset_telegram_api()
    
    # Получаем настроенное приложение
    logger.info("Настройка бота...")
    application = setup_bot()
    
    # Запускаем в режиме polling
    logger.info("Запуск бота...")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()