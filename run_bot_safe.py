#!/usr/bin/env python
"""
Скрипт-обертка для безопасного запуска Telegram бота.
Предотвращает запуск нескольких экземпляров и обновляет файл состояния здоровья.
"""

import os
import sys
import time
import threading
import fcntl
import logging
import datetime
import signal
import psutil
from contextlib import contextmanager

# Импортируем функции из bot_monitor для обновления файла здоровья
from bot_monitor import update_health_check, kill_bot_processes

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger('bot_safe_runner')

# Путь к файлу блокировки
LOCK_FILE = "/tmp/telegram_bot.lock"
# Интервал обновления файла здоровья (в секундах)
HEALTH_UPDATE_INTERVAL = 30

# Флаг для управления потоком обновления здоровья
health_update_running = True

def signal_handler(sig, frame):
    """Обработчик сигналов для корректного завершения."""
    global health_update_running
    logger.info(f"Получен сигнал {sig}, завершаем работу...")
    health_update_running = False
    sys.exit(0)

# Регистрируем обработчик сигналов
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

@contextmanager
def file_lock():
    """Контекстный менеджер для блокировки файла."""
    lock_file = open(LOCK_FILE, 'w')
    try:
        # Пытаемся получить эксклюзивную блокировку файла
        fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        logger.info("Блокировка файла получена")
        yield
    except IOError:
        # Если не удалось получить блокировку, значит другой экземпляр уже запущен
        logger.error("Не удалось получить блокировку. Возможно, другой экземпляр бота уже запущен")
        sys.exit(1)
    finally:
        # В любом случае разблокируем файл и закрываем его
        try:
            fcntl.lockf(lock_file, fcntl.LOCK_UN)
            lock_file.close()
            logger.info("Блокировка файла снята")
        except:
            pass

def health_update_thread():
    """Поток для регулярного обновления файла здоровья."""
    global health_update_running
    logger.info("Запущен поток обновления здоровья")
    
    while health_update_running:
        try:
            update_health_check()
        except Exception as e:
            logger.error(f"Ошибка при обновлении здоровья: {e}")
        
        # Спим заданное время, но с проверкой флага остановки
        for _ in range(HEALTH_UPDATE_INTERVAL):
            if not health_update_running:
                break
            time.sleep(1)
    
    logger.info("Поток обновления здоровья завершен")

def check_and_kill_other_instances():
    """Проверяет наличие других экземпляров бота и завершает их."""
    try:
        # Получаем PID текущего процесса
        current_pid = os.getpid()
        
        # Ищем и убиваем другие процессы с тем же именем скрипта
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # Пропускаем текущий процесс
                if proc.info['pid'] == current_pid:
                    continue
                
                # Проверяем, не является ли процесс экземпляром бота
                if proc.info['cmdline'] and any("main.py" in cmd for cmd in proc.info['cmdline']):
                    logger.warning(f"Найден другой экземпляр бота (PID: {proc.info['pid']}), завершаем его")
                    os.kill(proc.info['pid'], signal.SIGTERM)
                    time.sleep(1)  # Даем время на завершение
                    
                    # Если процесс все еще жив, применяем SIGKILL
                    if psutil.pid_exists(proc.info['pid']):
                        os.kill(proc.info['pid'], signal.SIGKILL)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
    except Exception as e:
        logger.error(f"Ошибка при проверке других экземпляров: {e}")

def main():
    """Основная функция запуска бота."""
    logger.info("Запуск безопасного запуска бота")
    
    # Сначала проверяем и убиваем другие экземпляры
    check_and_kill_other_instances()
    
    # Используем блокировку файла для предотвращения запуска нескольких экземпляров
    with file_lock():
        # Запускаем поток обновления здоровья
        health_thread = threading.Thread(target=health_update_thread)
        health_thread.daemon = True  # Делаем поток демоном, чтобы он завершился при выходе из программы
        health_thread.start()
        
        try:
            # Импортируем и запускаем основную функцию бота
            logger.info("Импортируем и запускаем основную функцию бота")
            from main import main as bot_main
            bot_main()
        except Exception as e:
            logger.error(f"Ошибка при запуске бота: {e}")
        finally:
            # Останавливаем поток обновления здоровья
            global health_update_running
            health_update_running = False
            if health_thread.is_alive():
                health_thread.join(timeout=5)
            logger.info("Завершение работы безопасного запуска")

if __name__ == "__main__":
    main()