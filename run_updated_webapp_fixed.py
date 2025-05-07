#!/usr/bin/env python3
"""
Улучшенная версия скрипта запуска веб-сервера с управлением ботом.
Эта версия исправляет проблемы конфликтов и стабильности запуска бота.
"""
import os
import sys
import subprocess
import time
import signal
import threading
import logging
import psutil
from app import app

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/webapp_fixed.log')
    ]
)
logger = logging.getLogger(__name__)

# Глобальная переменная для хранения процесса бота
bot_process = None

def find_and_kill_all_bot_processes():
    """Находит и завершает все запущенные процессы бота"""
    try:
        current_pid = os.getpid()
        logger.info(f"Текущий PID: {current_pid}")
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # Пропускаем текущий процесс
                if proc.pid == current_pid:
                    continue
                    
                # Проверяем командную строку процесса
                if proc.info['cmdline']:
                    cmdline = ' '.join(proc.info['cmdline'])
                    if 'python' in cmdline and ('bot.py' in cmdline or 'bot_modified.py' in cmdline or 'run_' in cmdline):
                        logger.info(f"Завершение процесса бота: {proc.pid}, {cmdline}")
                        os.kill(proc.pid, signal.SIGTERM)
                        time.sleep(0.5)  # Даем процессу время завершиться
                        
                        # Проверка, завершился ли процесс
                        if psutil.pid_exists(proc.pid):
                            logger.warning(f"Процесс {proc.pid} не завершился по SIGTERM, отправляем SIGKILL")
                            os.kill(proc.pid, signal.SIGKILL)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
                
        logger.info("Все процессы бота завершены")
    except Exception as e:
        logger.error(f"Ошибка при поиске и завершении процессов бота: {e}")

def start_bot():
    """Запускает процесс бота"""
    global bot_process
    
    # Завершаем все запущенные экземпляры бота
    find_and_kill_all_bot_processes()
    
    try:
        # Запускаем бота с использованием нашего нового скрипта
        logger.info("Запуск бота...")
        bot_process = subprocess.Popen(
            ["python", "run_fixed_bot.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        logger.info(f"Бот запущен с PID {bot_process.pid}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        return False

def stop_bot():
    """Останавливает процесс бота"""
    global bot_process
    
    if bot_process:
        try:
            logger.info(f"Остановка бота (PID: {bot_process.pid})...")
            bot_process.terminate()
            
            # Даем процессу 5 секунд на корректное завершение
            for _ in range(10):
                if bot_process.poll() is not None:
                    break
                time.sleep(0.5)
            
            # Если процесс не завершился, убиваем его
            if bot_process.poll() is None:
                logger.warning("Бот не завершился через SIGTERM, отправляем SIGKILL...")
                bot_process.kill()
            
            logger.info("Бот остановлен")
            bot_process = None
            return True
        except Exception as e:
            logger.error(f"Ошибка при остановке бота: {e}")
            return False
    else:
        logger.warning("Бот не был запущен")
        return False

def bot_status():
    """Проверяет статус бота"""
    global bot_process
    
    if bot_process:
        # Проверяем, жив ли процесс
        if bot_process.poll() is None:
            return True, f"Бот запущен (PID: {bot_process.pid})"
        else:
            return_code = bot_process.poll()
            return False, f"Бот завершился с кодом {return_code}"
    else:
        return False, "Бот не запущен"

def cleanup_on_exit():
    """Очистка ресурсов при выходе"""
    logger.info("Завершение работы, очистка ресурсов...")
    stop_bot()

# Регистрируем функцию очистки
import atexit
atexit.register(cleanup_on_exit)

# Обработчик сигналов для корректного завершения
def signal_handler(sig, frame):
    logger.info(f"Получен сигнал {sig}, завершение работы...")
    cleanup_on_exit()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def main():
    """Основная функция запуска веб-сервера"""
    try:
        # Убедимся, что директория для логов существует
        os.makedirs('logs', exist_ok=True)
        
        # При запуске сервера также запускаем бота
        start_bot()
        
        # Запускаем веб-сервер
        logger.info("Запуск веб-сервера...")
        app.run(host='0.0.0.0', port=5000)
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске сервера: {e}")
        cleanup_on_exit()
        sys.exit(1)

if __name__ == "__main__":
    main()