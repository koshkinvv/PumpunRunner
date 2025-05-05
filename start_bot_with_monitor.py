#!/usr/bin/env python
"""
Скрипт для запуска бота с монитором здоровья в Replit.
"""

import os
import sys
import time
import subprocess
import logging
import signal
import psutil

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger('bot_starter')

def kill_running_bots():
    """Убивает все запущенные процессы бота."""
    try:
        logger.info("Поиск и завершение запущенных экземпляров бота...")
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['cmdline'] and any('main.py' in cmd for cmd in proc.info['cmdline']):
                    logger.info(f"Убиваем процесс бота: {proc.info['pid']}")
                    os.kill(proc.info['pid'], signal.SIGTERM)
                    time.sleep(1)
                    
                    # Проверяем, завершился ли процесс
                    if psutil.pid_exists(proc.info['pid']):
                        os.kill(proc.info['pid'], signal.SIGKILL)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
    except Exception as e:
        logger.error(f"Ошибка при убийстве процессов бота: {e}")

def start_bot_with_monitor():
    """Запускает бота вместе с монитором здоровья."""
    try:
        # Сначала убиваем любые запущенные экземпляры бота
        kill_running_bots()
        
        # Создаем директорию для логов, если её нет
        os.makedirs("logs", exist_ok=True)
        
        # Запускаем бота
        logger.info("Запускаем бота...")
        bot_process = subprocess.Popen(
            ["python", "main.py"],
            stdout=open("logs/bot_output.log", "a"),
            stderr=open("logs/bot_error.log", "a")
        )
        
        # Запускаем монитор в отдельном процессе
        logger.info("Запускаем монитор здоровья...")
        monitor_process = subprocess.Popen(
            ["python", "bot_monitor.py"],
            stdout=open("logs/monitor_output.log", "a"),
            stderr=open("logs/monitor_error.log", "a")
        )
        
        logger.info("Бот и монитор здоровья запущены")
        
        # Ждем некоторое время, чтобы убедиться, что процессы стартовали нормально
        time.sleep(5)
        
        # Проверяем, что оба процесса все еще работают
        if not psutil.pid_exists(bot_process.pid) or not psutil.pid_exists(monitor_process.pid):
            logger.error("Не удалось запустить бота или монитор здоровья")
            
            # Убиваем оставшиеся процессы
            for pid in [bot_process.pid, monitor_process.pid]:
                if psutil.pid_exists(pid):
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except:
                        pass
            return False
        
        return True
    except Exception as e:
        logger.error(f"Ошибка при запуске бота с монитором: {e}")
        return False

def main():
    """Основная функция скрипта."""
    logger.info("Запуск скрипта запуска бота с монитором")
    
    success = start_bot_with_monitor()
    if success:
        logger.info("Бот с монитором успешно запущен. Выход из скрипта запуска.")
    else:
        logger.error("Не удалось запустить бота с монитором")
        sys.exit(1)

if __name__ == "__main__":
    main()