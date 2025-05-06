#!/usr/bin/env python
"""
Скрипт для проверки подключения к Telegram API.
Просто проверяет подключение, без запуска бота.
"""
import os
import sys
import time
import logging
import requests

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger("telegram_check")

def check_telegram_api():
    """Проверяет подключение к Telegram API"""
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        logger.error("TELEGRAM_TOKEN не найден в переменных окружения!")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{token}/getMe"
        logger.info(f"Отправка запроса к API...")
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                bot_info = data.get("result", {})
                logger.info(f"Успешное подключение к API! Бот: @{bot_info.get('username')} ({bot_info.get('first_name')})")
                
                # Сбросим вебхук и очистим обновления
                logger.info("Сброс вебхука...")
                reset_url = f"https://api.telegram.org/bot{token}/deleteWebhook?drop_pending_updates=true"
                reset_response = requests.get(reset_url, timeout=10)
                logger.info(f"Результат сброса вебхука: {reset_response.text}")
                
                return True
            else:
                logger.error(f"API вернул ошибку: {data.get('description')}")
        else:
            logger.error(f"Ошибка HTTP: {response.status_code}")
            logger.error(f"Текст ошибки: {response.text}")
        
        return False
    except Exception as e:
        logger.error(f"Ошибка при подключении к API: {e}")
        return False

def main():
    logger.info("====== ЗАПУСК ПРОВЕРКИ TELEGRAM ======")
    logger.info(f"Python версия: {sys.version}")
    logger.info(f"Рабочая директория: {os.getcwd()}")
    
    # Проверка переменных окружения
    env_vars = [
        "TELEGRAM_TOKEN", "DATABASE_URL", "OPENAI_API_KEY",
        "PGUSER", "PGHOST", "PGPORT"
    ]
    
    logger.info("Проверка переменных окружения:")
    for var in env_vars:
        if os.environ.get(var):
            logger.info(f"  ✓ {var}: установлена")
        else:
            logger.info(f"  ✗ {var}: отсутствует")
    
    # Проверяем подключение к Telegram API
    api_ok = check_telegram_api()
    
    if api_ok:
        logger.info("Подключение к Telegram API успешно!")
    else:
        logger.error("Не удалось подключиться к Telegram API.")
    
    # Продолжаем работу worker
    count = 0
    try:
        while True:
            count += 1
            logger.info(f"Worker работает уже {count*10} секунд")
            
            # Периодически проверяем API
            if count % 6 == 0:  # Каждую минуту
                logger.info("Повторная проверка API...")
                check_telegram_api()
            
            time.sleep(10)
    except KeyboardInterrupt:
        logger.info("Worker остановлен по команде пользователя")
    except Exception as e:
        logger.error(f"Ошибка в работе: {e}")
    
    logger.info("====== ЗАВЕРШЕНИЕ ПРОВЕРКИ TELEGRAM ======")

if __name__ == "__main__":
    main()