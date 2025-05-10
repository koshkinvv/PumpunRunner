#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт для запуска бота с улучшенным форматированием тренировок без создания workflow.
"""

import os
import sys
import logging
import subprocess
import signal
import time
import atexit

# Настраиваем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    filename='improved_bot.log'
)
logger = logging.getLogger(__name__)

def cleanup():
    """Функция для очистки при завершении работы скрипта."""
    logger.info("Очистка и завершение...")
    try:
        # Получаем PID бота, если он есть
        if os.path.exists("bot.pid"):
            with open("bot.pid", "r") as f:
                pid = f.read().strip()
            
            # Пытаемся завершить процесс бота
            try:
                os.kill(int(pid), signal.SIGTERM)
                logger.info(f"Завершен процесс бота с PID {pid}")
            except (ProcessLookupError, ValueError):
                logger.info(f"Процесс с PID {pid} не найден")
        
        logger.info("Очистка завершена")
    except Exception as e:
        logger.error(f"Ошибка при очистке: {e}")

def kill_existing_bot_processes():
    """Завершает все существующие процессы бота."""
    logger.info("Завершение существующих процессов бота...")
    try:
        # Пытаемся завершить все процессы Python, связанные с ботом
        subprocess.run(
            ["pkill", "-f", "python.*bot.*py"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE
        )
        logger.info("Существующие процессы бота завершены")
        time.sleep(1)
    except Exception as e:
        logger.error(f"Ошибка при завершении существующих процессов: {e}")

def start_bot():
    """Запускает бота с улучшенным форматированием."""
    logger.info("Запуск бота с улучшенным форматированием...")
    try:
        # Запускаем процесс бота
        process = subprocess.Popen(
            ["python", "start_improved_bot.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Записываем PID процесса
        with open("bot.pid", "w") as f:
            f.write(str(process.pid))
        
        logger.info(f"Бот запущен с PID {process.pid}")
        
        # Возвращаем процесс для дальнейшего мониторинга
        return process
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        return None

def monitor_bot_process(process):
    """Мониторит процесс бота и перезапускает его при необходимости."""
    logger.info("Начало мониторинга процесса бота...")
    try:
        while True:
            # Обновляем файл здоровья бота
            with open("bot_health.txt", "w") as f:
                f.write(str(int(time.time())))
            
            # Проверяем, работает ли процесс
            if process.poll() is not None:
                logger.warning(f"Процесс бота завершился с кодом {process.returncode}")
                # Читаем вывод процесса для логов
                stdout, stderr = process.communicate()
                logger.info(f"Вывод процесса: {stdout}")
                logger.error(f"Ошибки процесса: {stderr}")
                
                # Перезапускаем бота
                logger.info("Перезапуск бота...")
                process = start_bot()
                if process is None:
                    logger.error("Не удалось перезапустить бота")
                    break
            
            # Ждем перед следующей проверкой
            time.sleep(30)
    except KeyboardInterrupt:
        logger.info("Мониторинг остановлен пользователем")
    except Exception as e:
        logger.error(f"Ошибка при мониторинге: {e}")

def main():
    """Основная функция."""
    try:
        logger.info("Запуск улучшенного бота с форматированием тренировок...")
        
        # Регистрируем функцию очистки
        atexit.register(cleanup)
        
        # Завершаем существующие процессы бота
        kill_existing_bot_processes()
        
        # Запускаем бота
        process = start_bot()
        if process is None:
            logger.error("Не удалось запустить бота")
            return 1
        
        # Мониторим процесс
        monitor_bot_process(process)
        
        return 0
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())