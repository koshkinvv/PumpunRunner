#!/usr/bin/env python
"""
Скрипт для предотвращения "засыпания" Replit при использовании без Reserved VM.
Обратите внимание, что для надежной работы бота рекомендуется использовать Reserved VM.
"""

import os
import sys
import time
import random
import logging
import datetime
import requests
import subprocess
import threading

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("keep_alive.log")
    ]
)

logger = logging.getLogger('keep_alive')

# URL для ping (можно создать Flask-приложение на порту 5000 внутри этого же Replit)
PING_URL = "http://localhost:5000"

# Частота проверки статуса бота (в секундах)
CHECK_INTERVAL = 300  # Каждые 5 минут

# Имя файла для проверки активности бота
HEALTH_FILE = "bot_health.txt"

def create_health_file_if_not_exists():
    """Создает файл здоровья, если он не существует."""
    if not os.path.exists(HEALTH_FILE):
        try:
            with open(HEALTH_FILE, "w") as f:
                f.write(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            logger.info(f"Создан файл здоровья: {HEALTH_FILE}")
        except Exception as e:
            logger.error(f"Ошибка при создании файла здоровья: {e}")

def check_bot_health():
    """Проверяет, активен ли бот, на основе файла здоровья."""
    if not os.path.exists(HEALTH_FILE):
        logger.warning("Файл здоровья не существует")
        return False
    
    try:
        with open(HEALTH_FILE, "r") as f:
            last_update = f.read().strip()
        
        last_time = datetime.datetime.strptime(last_update, "%Y-%m-%d %H:%M:%S")
        current_time = datetime.datetime.now()
        
        # Если файл не обновлялся более 5 минут, считаем бота неактивным
        if (current_time - last_time).total_seconds() > 300:
            logger.warning(f"Бот неактивен. Последнее обновление: {last_update}")
            return False
        
        logger.info(f"Бот активен. Последнее обновление: {last_update}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при проверке здоровья бота: {e}")
        return False

def ping_web_app():
    """Выполняет ping к веб-приложению для поддержания активности."""
    try:
        # Добавляем случайный параметр для предотвращения кеширования
        random_param = random.randint(1, 1000000)
        response = requests.get(f"{PING_URL}?r={random_param}", timeout=10)
        
        if response.status_code == 200:
            logger.info(f"Успешный ping к {PING_URL}")
            return True
        else:
            logger.warning(f"Неуспешный ping к {PING_URL}, статус: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Ошибка при ping: {e}")
        return False

def check_and_restart_bot():
    """Проверяет состояние бота и перезапускает его при необходимости."""
    if not check_bot_health():
        logger.warning("Бот неактивен, пытаемся перезапустить")
        
        try:
            # Останавливаем все существующие процессы бота
            os.system("pkill -f 'python.*main.py'")
            os.system("pkill -f 'python.*bot_monitor.py'")
            os.system("pkill -f 'python.*start_bot_with_monitor.py'")
            
            # Даем немного времени на завершение процессов
            time.sleep(5)
            
            # Запускаем скрипт run.py для перезапуска бота
            logger.info("Запускаем run.py для перезапуска бота")
            
            # Создаем директорию для логов, если её нет
            os.makedirs("logs", exist_ok=True)
            
            # Запускаем в отдельном процессе
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            subprocess.Popen(
                ["python", "run.py"],
                stdout=open(f"logs/restart_{timestamp}.log", "w"),
                stderr=open(f"logs/restart_error_{timestamp}.log", "w")
            )
            
            logger.info("Бот перезапущен")
        except Exception as e:
            logger.error(f"Ошибка при перезапуске бота: {e}")

def perform_system_activities():
    """
    Выполняет случайные системные действия для поддержания активности VM.
    """
    activities = [
        "ls -la",
        "ps aux | head -5",
        "free -m",
        "df -h",
        "date",
        "uptime",
        "echo 'Keep alive ping'",
        "head -1 /proc/meminfo",
        "head -1 /proc/loadavg"
    ]
    
    # Выбираем случайное действие
    activity = random.choice(activities)
    
    try:
        # Выполняем действие и записываем результат
        output = subprocess.check_output(activity, shell=True, text=True)
        logger.debug(f"Выполнено действие: {activity}")
        logger.debug(f"Результат: {output[:100]}..." if len(output) > 100 else f"Результат: {output}")
    except Exception as e:
        logger.error(f"Ошибка при выполнении действия {activity}: {e}")

def main():
    """Основная функция для поддержания активности Replit."""
    logger.info("Запуск скрипта поддержания активности Replit")
    
    create_health_file_if_not_exists()
    
    try:
        while True:
            # Проверяем и при необходимости перезапускаем бота
            check_and_restart_bot()
            
            # Выполняем ping к веб-приложению
            ping_web_app()
            
            # Выполняем случайные системные действия
            perform_system_activities()
            
            # Случайная задержка от 3 до 7 минут (для имитации разных паттернов активности)
            sleep_time = random.randint(CHECK_INTERVAL - 60, CHECK_INTERVAL + 60)
            logger.info(f"Следующая проверка через {sleep_time} секунд")
            time.sleep(sleep_time)
    except KeyboardInterrupt:
        logger.info("Скрипт остановлен пользователем")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        # В случае сбоя перезапускаем скрипт через несколько секунд
        time.sleep(10)
        os.execv(sys.executable, ['python'] + sys.argv)

if __name__ == "__main__":
    # Запускаем основную функцию в отдельном потоке
    main_thread = threading.Thread(target=main)
    main_thread.daemon = True
    main_thread.start()
    
    # Ждем бесконечно в основном потоке (или до прерывания пользователем)
    try:
        while True:
            time.sleep(3600)  # Проверка каждый час для возможности корректного прерывания
    except KeyboardInterrupt:
        logger.info("Программа завершена пользователем")
        sys.exit(0)