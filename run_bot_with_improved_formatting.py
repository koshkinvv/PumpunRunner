#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт для запуска бота с улучшенным форматированием тренировок.
Исправляет все существующие процессы бота и запускает новую версию.
"""

import os
import sys
import logging
import subprocess
import time
import signal
import asyncio
from telegram.ext import ApplicationBuilder

# Настраиваем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    filename='improved_bot.log'
)
logger = logging.getLogger(__name__)

def kill_existing_bot_processes():
    """Завершает все существующие процессы бота."""
    logger.info("Завершение существующих процессов бота...")
    
    # Пытаемся найти и завершить процессы по PID
    if os.path.exists("bot.pid"):
        try:
            with open("bot.pid", "r") as f:
                pid = f.read().strip()
            if pid:
                try:
                    os.kill(int(pid), signal.SIGTERM)
                    logger.info(f"Завершен процесс бота с PID {pid}")
                    time.sleep(1)
                except (ProcessLookupError, ValueError):
                    logger.info(f"Процесс с PID {pid} не найден")
        except Exception as e:
            logger.error(f"Ошибка при чтении и завершении процесса по PID: {e}")
    
    # Завершаем все процессы Python, связанные с ботом
    try:
        subprocess.run(
            ["pkill", "-f", "python.*bot.*py"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE
        )
        logger.info("Все процессы бота успешно завершены")
        time.sleep(1)  # Даем время на завершение процессов
    except Exception as e:
        logger.error(f"Ошибка при завершении процессов бота: {e}")

def update_health_file():
    """Обновляет файл здоровья бота."""
    try:
        with open("bot_health.txt", "w") as f:
            f.write(str(int(time.time())))
        logger.info("Файл здоровья бота обновлен")
    except Exception as e:
        logger.error(f"Ошибка при обновлении файла здоровья: {e}")

from config import TELEGRAM_TOKEN
from bot_modified import setup_bot

async def run_bot():
    """Запускает бота с улучшенным форматированием."""
    try:
        # Создаем приложение
        application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        
        # Настраиваем обработчики
        setup_bot(application)
        
        # Запускаем бота
        await application.run_polling(allowed_updates=["message", "callback_query", "my_chat_member"])
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        raise

def main():
    """Основная функция."""
    try:
        # Записываем PID текущего процесса
        with open("bot.pid", "w") as f:
            f.write(str(os.getpid()))
        
        # Завершаем существующие процессы бота
        kill_existing_bot_processes()
        
        # Обновляем файл здоровья
        update_health_file()
        
        # Запускаем бота
        logger.info("Запуск бота с улучшенным форматированием тренировок...")
        asyncio.run(run_bot())
        
        return 0
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
        return 0
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())