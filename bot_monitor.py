#!/usr/bin/env python
"""
Скрипт для мониторинга состояния Telegram бота и его автоматического перезапуска.
"""

import os
import sys
import time
import signal
import psutil
import logging
import subprocess
from datetime import datetime, timedelta

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger('bot_monitor')

# Параметры мониторинга
BOT_PROCESS_NAME = "main.py"
CHECK_INTERVAL = 60  # секунд между проверками
MAX_MEMORY_PERCENT = 90  # максимальный процент памяти
RESTART_COOLDOWN = 300  # минимальное время между перезапусками (5 минут)
HEALTH_CHECK_FILE = "bot_health.txt"
HEALTH_CHECK_TIMEOUT = 180  # время в секундах, после которого считаем бот неактивным

last_restart_time = datetime.now() - timedelta(seconds=RESTART_COOLDOWN * 2)

def kill_bot_processes():
    """Находит и завершает все процессы бота."""
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # Проверяем командную строку на наличие имени скрипта бота
                if proc.info['cmdline'] and any(BOT_PROCESS_NAME in cmd for cmd in proc.info['cmdline']):
                    logger.info(f"Завершаем процесс бота: {proc.info['pid']}")
                    os.kill(proc.info['pid'], signal.SIGTERM)
                    time.sleep(1)  # Даем процессу время на завершение
                    
                    # Если процесс все еще работает, принудительно завершаем
                    if psutil.pid_exists(proc.info['pid']):
                        os.kill(proc.info['pid'], signal.SIGKILL)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
    except Exception as e:
        logger.error(f"Ошибка при завершении процессов бота: {e}")

def start_bot():
    """Запускает бот в новом процессе."""
    try:
        logger.info("Запускаем бота...")
        # Запускаем бота в фоновом режиме
        subprocess.Popen(["python", "main.py"], 
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
        logger.info("Бот запущен")
        # Обновляем время последнего перезапуска
        global last_restart_time
        last_restart_time = datetime.now()
        
        # Создаем файл проверки здоровья
        update_health_check()
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")

def update_health_check():
    """Обновляет файл проверки здоровья текущим временем."""
    try:
        with open(HEALTH_CHECK_FILE, "w") as f:
            f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    except Exception as e:
        logger.error(f"Ошибка при обновлении файла проверки здоровья: {e}")

def check_bot_health():
    """Проверяет, что бот работает и отвечает."""
    try:
        # Проверяем, существует ли файл здоровья
        if not os.path.exists(HEALTH_CHECK_FILE):
            logger.warning("Файл проверки здоровья не найден")
            return False
        
        # Проверяем время последнего обновления
        with open(HEALTH_CHECK_FILE, "r") as f:
            health_time_str = f.read().strip()
        
        health_time = datetime.strptime(health_time_str, "%Y-%m-%d %H:%M:%S")
        current_time = datetime.now()
        
        # Если файл не обновлялся слишком долго, считаем бот неактивным
        if (current_time - health_time).total_seconds() > HEALTH_CHECK_TIMEOUT:
            logger.warning(f"Последнее обновление здоровья: {health_time_str}, текущее время: {current_time}. Бот неактивен.")
            return False
        
        # Проверяем использование памяти
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'memory_percent']):
            try:
                if proc.info['cmdline'] and any(BOT_PROCESS_NAME in cmd for cmd in proc.info['cmdline']):
                    if proc.info['memory_percent'] > MAX_MEMORY_PERCENT:
                        logger.warning(f"Бот использует слишком много памяти: {proc.info['memory_percent']}%")
                        return False
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        # Если все проверки прошли, бот здоров
        return True
    except Exception as e:
        logger.error(f"Ошибка при проверке здоровья бота: {e}")
        return False

def is_bot_running():
    """Проверяет, запущен ли бот."""
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['cmdline'] and any(BOT_PROCESS_NAME in cmd for cmd in proc.info['cmdline']):
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return False
    except Exception as e:
        logger.error(f"Ошибка при проверке запуска бота: {e}")
        return False

def check_and_restart_if_needed():
    """Проверяет состояние бота и перезапускает его при необходимости."""
    global last_restart_time
    
    # Проверяем, не слишком ли часто перезапускается бот
    if (datetime.now() - last_restart_time).total_seconds() < RESTART_COOLDOWN:
        logger.info("Охлаждение перезапуска активно, пропускаем проверку")
        return
    
    # Если бот не запущен, запускаем его
    if not is_bot_running():
        logger.warning("Бот не запущен, запускаем")
        kill_bot_processes()  # На всякий случай убиваем все процессы
        start_bot()
        return
    
    # Если бот запущен, проверяем его здоровье
    if not check_bot_health():
        logger.warning("Бот нездоров, перезапускаем")
        kill_bot_processes()
        time.sleep(2)  # Даем время на корректное завершение
        start_bot()

def main():
    """Основная функция мониторинга."""
    logger.info("Запуск монитора бота")
    
    # Инициализируем файл здоровья
    update_health_check()
    
    # Проверяем, запущен ли бот, и запускаем, если нет
    if not is_bot_running():
        logger.info("Бот не запущен, запускаем")
        start_bot()
    
    # Основной цикл мониторинга
    try:
        while True:
            check_and_restart_if_needed()
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        logger.info("Монитор остановлен пользователем")
    except Exception as e:
        logger.error(f"Неожиданная ошибка в мониторе: {e}")
        raise

if __name__ == "__main__":
    main()