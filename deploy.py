#!/usr/bin/env python
"""
Скрипт для запуска приложения в среде развертывания Replit.
Этот скрипт запускает Flask-приложение, которое обслуживает запросы
и отображает информацию о статусе бота.
"""

import os
import threading
import logging
import sys
import time
import datetime
import signal
import subprocess

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/deploy.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("deploy")

def ensure_logs_directory():
    """Создает директорию для логов, если она не существует."""
    if not os.path.exists("logs"):
        os.makedirs("logs")
        logger.info("Создана директория для логов")

def update_health_check():
    """Обновляет файл проверки здоровья приложения."""
    try:
        with open("bot_health.txt", "w") as f:
            f.write(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        logger.debug("Файл проверки здоровья обновлен")
    except Exception as e:
        logger.error(f"Ошибка при обновлении файла проверки здоровья: {e}")

def run_health_updater():
    """Запускает периодическое обновление файла здоровья."""
    while True:
        update_health_check()
        time.sleep(60)

def signal_handler(sig, frame):
    """Обработчик сигналов для корректного завершения."""
    logger.info(f"Получен сигнал {sig}, завершаем работу")
    
    # Завершаем все дочерние процессы
    for process in running_processes:
        if process.poll() is None:  # Если процесс еще работает
            try:
                process.terminate()
                logger.info(f"Процесс {process.pid} завершен")
            except Exception as e:
                logger.error(f"Ошибка при завершении процесса {process.pid}: {e}")
    
    sys.exit(0)

def start_telegram_bot():
    """Запускает Telegram-бота в режиме поллинга."""
    logger.info("Запуск Telegram-бота...")
    try:
        # Запускаем бота в фоновом режиме
        bot_process = subprocess.Popen(
            ["python", "run_telegram_bot.py"],
            stdout=open("logs/bot_output.log", "w"),
            stderr=open("logs/bot_error.log", "w")
        )
        running_processes.append(bot_process)
        logger.info(f"Telegram-бот запущен с PID: {bot_process.pid}")
        return bot_process
    except Exception as e:
        logger.error(f"Ошибка при запуске Telegram-бота: {e}")
        return None

def start_flask_app():
    """Запускает Flask-приложение для обработки запросов."""
    logger.info("Запуск Flask-приложения...")
    try:
        # Запускаем Flask-приложение через gunicorn
        app_process = subprocess.Popen(
            ["gunicorn", "--bind", "0.0.0.0:5000", "--timeout", "120", "app:app"],
            stdout=open("logs/app_output.log", "w"),
            stderr=open("logs/app_error.log", "w")
        )
        running_processes.append(app_process)
        logger.info(f"Flask-приложение запущено с PID: {app_process.pid}")
        return app_process
    except Exception as e:
        logger.error(f"Ошибка при запуске Flask-приложения: {e}")
        return None

def check_processes():
    """Проверяет работоспособность процессов и перезапускает их при необходимости."""
    global running_processes
    
    # Проверяем каждый процесс
    for i, process in enumerate(running_processes):
        if process.poll() is not None:  # Если процесс завершился
            logger.warning(f"Процесс {process.pid} завершился с кодом {process.returncode}")
            
            # Определяем тип процесса и перезапускаем
            if "run_telegram_bot.py" in process.args:
                logger.info("Перезапуск Telegram-бота...")
                new_process = start_telegram_bot()
                if new_process:
                    running_processes[i] = new_process
            elif "gunicorn" in process.args:
                logger.info("Перезапуск Flask-приложения...")
                new_process = start_flask_app()
                if new_process:
                    running_processes[i] = new_process

def monitor_processes():
    """Мониторит процессы и перезапускает их при необходимости."""
    while True:
        try:
            check_processes()
        except Exception as e:
            logger.error(f"Ошибка при мониторинге процессов: {e}")
        time.sleep(10)  # Проверяем каждые 10 секунд

if __name__ == "__main__":
    # Глобальный список процессов
    running_processes = []
    
    # Создаем директорию для логов
    ensure_logs_directory()
    
    # Регистрируем обработчики сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Запускаем обновление файла здоровья в отдельном потоке
    health_thread = threading.Thread(target=run_health_updater)
    health_thread.daemon = True
    health_thread.start()
    
    try:
        # Запускаем Telegram-бота
        bot_process = start_telegram_bot()
        
        # Запускаем Flask-приложение
        app_process = start_flask_app()
        
        # Запускаем мониторинг процессов
        monitor_thread = threading.Thread(target=monitor_processes)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        # Основной цикл для предотвращения завершения скрипта
        while True:
            time.sleep(60)
            logger.debug("Приложение работает")
    
    except KeyboardInterrupt:
        logger.info("Получен сигнал прерывания, завершаем работу")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
    finally:
        # Завершаем все процессы при выходе
        for process in running_processes:
            if process.poll() is None:  # Если процесс еще работает
                try:
                    process.terminate()
                    logger.info(f"Процесс {process.pid} завершен")
                except Exception as e:
                    logger.error(f"Ошибка при завершении процесса: {e}")