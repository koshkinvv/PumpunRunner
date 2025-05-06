#!/usr/bin/env python
"""
Простой скрипт для работы в Background Worker.
Этот скрипт просто пишет лог каждые 10 секунд, чтобы показать что живой.
"""
import os
import sys
import time
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger("simple_worker")

def main():
    logger.info("====== ЗАПУСК WORKER ======")
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
    
    count = 0
    try:
        while True:
            count += 1
            logger.info(f"Worker работает уже {count*10} секунд")
            time.sleep(10)
    except KeyboardInterrupt:
        logger.info("Worker остановлен по команде пользователя")
    except Exception as e:
        logger.error(f"Ошибка в работе: {e}")
    
    logger.info("====== ЗАВЕРШЕНИЕ WORKER ======")

if __name__ == "__main__":
    main()