#!/usr/bin/env python
"""
Самый простой скрипт запуска бота для production.
"""
import os
import sys
import logging
import traceback

# Настройка базового логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger("run_production")

def main():
    """Главная функция запуска бота"""
    try:
        logger.info("Запуск бота в продакшн режиме")
        
        # Вывод текущей директории и списка файлов
        current_dir = os.getcwd()
        logger.info(f"Текущая директория: {current_dir}")
        logger.info(f"Содержимое директории: {os.listdir('.')}")
        
        # Импорт функции настройки бота
        try:
            logger.info("Импорт функции setup_bot из bot_modified.py")
            from bot_modified import setup_bot
        except ImportError as e:
            logger.error(f"Ошибка импорта из bot_modified.py: {e}")
            logger.info("Пробуем импортировать из bot.py")
            from bot import setup_bot
        
        # Запускаем бота
        logger.info("Запуск бота...")
        application = setup_bot()
        application.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()