#!/usr/bin/env python
"""
Скрипт для остановки всех запущенных экземпляров бота и запуска только одного через deploy_bot.py.
Предотвращает конфликты при запуске нескольких экземпляров бота.
"""

import os
import sys
import time
import signal
import subprocess
import logging
import psutil

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger('run_one_bot')

def kill_all_bot_processes():
    """Найти и завершить все запущенные процессы бота."""
    logger.info("Поиск и остановка всех запущенных экземпляров бота...")
    
    # Список ключевых слов для поиска процессов бота
    bot_keywords = ["main.py", "bot_monitor.py", "deploy_bot.py", "bot_runner"]
    
    # Завершаем все запущенные экземпляры
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # Ищем только процессы python
            if proc.info['name'] and 'python' in proc.info['name'].lower():
                cmdline = ' '.join(proc.info['cmdline'] or [])
                
                # Проверяем, относится ли процесс к боту
                if any(keyword in cmdline for keyword in bot_keywords):
                    # Исключаем текущий процесс
                    if proc.info['pid'] != os.getpid():
                        logger.info(f"Остановка процесса бота: PID {proc.info['pid']}")
                        try:
                            os.kill(proc.info['pid'], signal.SIGTERM)
                            time.sleep(1)  # Даем процессу время завершиться
                            
                            # Если процесс все еще работает, применяем SIGKILL
                            if psutil.pid_exists(proc.info['pid']):
                                logger.warning(f"Процесс {proc.info['pid']} не остановился. Применяем SIGKILL.")
                                os.kill(proc.info['pid'], signal.SIGKILL)
                        except Exception as e:
                            logger.error(f"Ошибка при остановке процесса {proc.info['pid']}: {e}")
        except Exception as e:
            logger.error(f"Ошибка при проверке процесса: {e}")

def run_deploy_bot():
    """Запускает основной скрипт deploy_bot.py."""
    logger.info("Запуск основного скрипта deploy_bot.py...")
    
    # Создаем директорию для логов, если её нет
    os.makedirs("logs", exist_ok=True)
    
    # Запускаем deploy_bot.py
    try:
        deploy_process = subprocess.Popen(
            ["python", "deploy_bot.py"],
            stdout=open("logs/deploy_bot_output.log", "a"),
            stderr=open("logs/deploy_bot_error.log", "a")
        )
        
        logger.info(f"Бот запущен успешно с PID: {deploy_process.pid}")
        
        # Ждем окончания работы скрипта
        deploy_process.wait()
        
    except Exception as e:
        logger.error(f"Ошибка при запуске deploy_bot.py: {e}")

if __name__ == "__main__":
    logger.info("Запуск единственного экземпляра бота...")
    
    # Останавливаем все запущенные процессы бота
    kill_all_bot_processes()
    
    # Даем время на полное завершение всех процессов
    time.sleep(3)
    
    # Запускаем deploy_bot.py
    run_deploy_bot()