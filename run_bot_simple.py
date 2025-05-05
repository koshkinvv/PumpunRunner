#!/usr/bin/env python3
"""
Упрощенный скрипт для запуска Telegram бота в режиме поллинга.
"""

import os
import sys
import logging
import time
import signal
import subprocess

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Основная функция запуска бота
def main():
    """Запускает Telegram бота в упрощенном режиме."""
    
    # Убиваем все существующие процессы бота для предотвращения конфликтов
    try:
        logging.info("Останавливаем существующие процессы бота...")
        os.system("pkill -f 'python.*bot_modified.py'")
        os.system("pkill -f 'python.*run_telegram_bot.py'")
        os.system("pkill -f 'python.*main.py'")
        time.sleep(2)  # Даем процессам время завершиться
    except Exception as e:
        logging.error(f"Ошибка при остановке процессов: {e}")
    
    try:
        # Запускаем бота напрямую из bot_modified.py
        from bot_modified import setup_bot
        
        logging.info("Инициализируем бота...")
        application = setup_bot()
        
        # Настраиваем обработчик сигналов для корректного завершения
        def signal_handler(sig, frame):
            logging.info("Получен сигнал остановки. Завершаем работу бота...")
            # Завершаем бота
            application.stop()
            logging.info("Бот остановлен.")
            sys.exit(0)
        
        # Регистрируем обработчики сигналов
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Запускаем бота в режиме поллинга
        logging.info("Запускаем бота в режиме поллинга...")
        application.run_polling(
            drop_pending_updates=True,  # Игнорируем накопившиеся обновления
            allowed_updates=None,  # Принимаем все типы обновлений
            stop_signals=(signal.SIGINT, signal.SIGTERM),  # Сигналы для остановки
            timeout=30  # Timeout для запросов
        )
        
    except Exception as e:
        logging.error(f"Ошибка при запуске бота: {e}")
        logging.error(f"Трассировка: {sys.exc_info()[2]}")
        return 1
    
    return 0

if __name__ == "__main__":
    # Запускаем основную функцию
    sys.exit(main())