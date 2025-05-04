#!/usr/bin/env python
"""
Скрипт для запуска функции отправки напоминаний о тренировках.
Запускается регулярно через cron или аналогичный планировщик.
"""

import asyncio
import logging
import time
import sys
from training_reminder import main as run_reminders

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/reminders.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

async def main():
    """Главная функция для запуска отправки напоминаний."""
    logger.info("Запуск процесса отправки напоминаний о тренировках")
    
    start_time = time.time()
    
    try:
        # Запускаем функцию отправки напоминаний
        await run_reminders()
        logger.info("Процесс отправки напоминаний успешно завершен")
    except Exception as e:
        logger.error(f"Ошибка при отправке напоминаний: {e}", exc_info=True)
    
    # Логируем длительность выполнения
    elapsed_time = time.time() - start_time
    logger.info(f"Время выполнения: {elapsed_time:.2f} секунд")

if __name__ == "__main__":
    # Запускаем асинхронную функцию
    asyncio.run(main())