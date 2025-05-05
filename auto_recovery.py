#!/usr/bin/env python
"""
Скрипт для автоматического восстановления и перезапуска бота при сбоях.
Работает как сторожевой таймер (watchdog), регулярно проверяя работоспособность бота.
"""

import os
import sys
import time
import json
import psutil
import signal
import logging
import datetime
import subprocess
import traceback
import requests
from pathlib import Path

# Настройка логирования
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_dir / "auto_recovery.log")
    ]
)

logger = logging.getLogger('auto_recovery')

# Константы
BOT_PROCESS_NAMES = ["main.py", "bot_monitor.py"]
WEB_APP_PROCESS_NAME = "gunicorn"
KEEP_ALIVE_PROCESS_NAME = "keep_alive.py"
CHECK_INTERVAL = 60  # Проверка каждую минуту
HEALTH_FILE = "bot_health.txt"
HEALTH_THRESHOLD = 300  # 5 минут без обновления -> перезапуск
API_URL = "http://localhost:5000/status"
RESTART_SCRIPT = "run_24_7.sh"
MAX_CONSECUTIVE_FAILURES = 3

# Счетчики
consecutive_failures = 0
last_restart_time = datetime.datetime.now() - datetime.timedelta(hours=1)

def is_process_running(process_name):
    """Проверяет, запущен ли процесс с указанным именем."""
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['cmdline'] and any(process_name in cmd for cmd in proc.info['cmdline']):
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return False
    except Exception as e:
        logger.error(f"Ошибка при проверке процесса {process_name}: {e}")
        return False

def check_health_file():
    """Проверяет файл здоровья бота."""
    try:
        if not os.path.exists(HEALTH_FILE):
            logger.warning(f"Файл здоровья {HEALTH_FILE} не существует")
            return False
        
        with open(HEALTH_FILE, "r") as f:
            health_time_str = f.read().strip()
        
        try:
            health_time = datetime.datetime.strptime(health_time_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            logger.warning(f"Некорректный формат времени в файле здоровья: {health_time_str}")
            return False
        
        current_time = datetime.datetime.now()
        time_diff = (current_time - health_time).total_seconds()
        
        if time_diff > HEALTH_THRESHOLD:
            logger.warning(f"Файл здоровья устарел: {time_diff:.1f} сек (порог: {HEALTH_THRESHOLD} сек)")
            return False
        
        logger.info(f"Файл здоровья актуален: {health_time_str}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при проверке файла здоровья: {e}")
        return False

def check_api_status():
    """Проверяет статус API бота."""
    try:
        response = requests.get(API_URL, timeout=10)
        
        if response.status_code != 200:
            logger.warning(f"API вернул некорректный статус: {response.status_code}")
            return False
        
        data = response.json()
        
        if not data.get("is_running", False):
            logger.warning("API сообщает, что бот не запущен")
            return False
        
        logger.info("API сообщает, что бот запущен и работает")
        return True
    except requests.RequestException as e:
        logger.warning(f"Не удалось подключиться к API: {e}")
        return False
    except Exception as e:
        logger.error(f"Ошибка при проверке API: {e}")
        return False

def update_health_file():
    """Обновляет файл здоровья с текущим временем."""
    try:
        with open(HEALTH_FILE, "w") as f:
            f.write(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        logger.info("Файл здоровья обновлен")
    except Exception as e:
        logger.error(f"Ошибка при обновлении файла здоровья: {e}")

def restart_system():
    """Перезапускает всю систему бота."""
    global last_restart_time, consecutive_failures
    
    current_time = datetime.datetime.now()
    
    # Проверка времени последнего перезапуска
    if (current_time - last_restart_time).total_seconds() < 300:  # 5 минут
        consecutive_failures += 1
        logger.warning(f"Частые перезапуски системы: {consecutive_failures} подряд")
        
        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            logger.error(f"Достигнут лимит последовательных сбоев ({MAX_CONSECUTIVE_FAILURES})")
            logger.error("Возможно, есть серьезная проблема с системой")
            # Увеличиваем время ожидания перед следующим перезапуском
            time.sleep(60 * consecutive_failures)  # Ждем N минут, где N - количество последовательных сбоев
    else:
        consecutive_failures = 0
    
    logger.warning("Перезапуск всей системы...")
    
    try:
        # Останавливаем все процессы
        for process_name in BOT_PROCESS_NAMES + [WEB_APP_PROCESS_NAME, KEEP_ALIVE_PROCESS_NAME]:
            logger.info(f"Остановка процесса: {process_name}")
            os.system(f"pkill -f '{process_name}'")
        
        time.sleep(5)  # Даем время на остановку процессов
        
        # Запускаем скрипт перезапуска
        logger.info(f"Запуск скрипта перезапуска: {RESTART_SCRIPT}")
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        restart_log = str(log_dir / f"restart_{timestamp}.log")
        restart_err = str(log_dir / f"restart_error_{timestamp}.log")
        
        with open(restart_log, "w") as stdout, open(restart_err, "w") as stderr:
            subprocess.Popen(
                ["bash", RESTART_SCRIPT],
                stdout=stdout,
                stderr=stderr,
                env=dict(os.environ),
                cwd=os.getcwd()
            )
        
        logger.info(f"Скрипт перезапуска запущен (логи: {restart_log}, {restart_err})")
        last_restart_time = current_time
        
        # Обновляем файл здоровья
        update_health_file()
        
        return True
    except Exception as e:
        logger.error(f"Ошибка при перезапуске системы: {e}")
        logger.error(traceback.format_exc())
        return False

def check_system_health():
    """Проверяет здоровье всей системы и перезапускает при необходимости."""
    try:
        logger.info("Проверка здоровья системы...")
        
        # Проверяем файл здоровья
        health_file_ok = check_health_file()
        
        # Проверяем API
        api_ok = check_api_status()
        
        # Проверяем запуск основных процессов
        processes_ok = True
        for process_name in BOT_PROCESS_NAMES:
            if not is_process_running(process_name):
                logger.warning(f"Процесс {process_name} не запущен")
                processes_ok = False
        
        if not is_process_running(WEB_APP_PROCESS_NAME):
            logger.warning(f"Веб-приложение {WEB_APP_PROCESS_NAME} не запущено")
            processes_ok = False
        
        # Обновляем файл здоровья с текущим временем
        if health_file_ok and api_ok and processes_ok:
            logger.info("Система работает нормально")
            update_health_file()
            return True
        
        # Если что-то не работает, перезапускаем систему
        logger.warning("Обнаружены проблемы с системой, требуется перезапуск")
        restart_system()
        return False
    except Exception as e:
        logger.error(f"Ошибка при проверке здоровья системы: {e}")
        logger.error(traceback.format_exc())
        return False

def main():
    """Основная функция скрипта."""
    logger.info("Запуск скрипта автоматического восстановления")
    
    # Проверяем, существует ли скрипт перезапуска
    if not os.path.exists(RESTART_SCRIPT):
        logger.error(f"Скрипт перезапуска {RESTART_SCRIPT} не найден")
        return
    
    try:
        while True:
            check_system_health()
            
            # Случайное время ожидания до следующей проверки (30-90 секунд)
            wait_time = CHECK_INTERVAL
            logger.info(f"Следующая проверка через {wait_time} секунд")
            time.sleep(wait_time)
    except KeyboardInterrupt:
        logger.info("Скрипт остановлен пользователем")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    main()