#!/usr/bin/env python
"""
Скрипт запуска бота для Replit Deployment.
Этот скрипт создан специально для работы в режиме Background Worker на Reserved VM.
"""

import os
import sys
import time
import signal
import logging
import subprocess
import psutil

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger('deploy_bot')

def kill_running_bots():
    """Убивает все запущенные процессы бота."""
    try:
        logger.info("Поиск и завершение запущенных экземпляров бота...")
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # Ищем все процессы main.py или bot_monitor.py, но исключаем текущий скрипт
                if proc.info['cmdline'] and any(cmd in ' '.join(proc.info['cmdline']) 
                                                for cmd in ['main.py', 'bot_monitor.py']) and proc.info['pid'] != os.getpid():
                    logger.info(f"Убиваем процесс: {proc.info['pid']} - {' '.join(proc.info['cmdline'])}")
                    os.kill(proc.info['pid'], signal.SIGTERM)
                    time.sleep(1)
                    
                    # Проверяем, завершился ли процесс
                    if psutil.pid_exists(proc.info['pid']):
                        os.kill(proc.info['pid'], signal.SIGKILL)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
    except Exception as e:
        logger.error(f"Ошибка при убийстве процессов бота: {e}")

def start_bot_and_monitor():
    """Запускает бота и монитор здоровья."""
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
        
        logger.info(f"Бот (PID: {bot_process.pid}) и монитор здоровья (PID: {monitor_process.pid}) запущены")
        
        # Ждем некоторое время, чтобы убедиться, что процессы стартовали нормально
        time.sleep(5)
        
        # Проверяем, что оба процесса все еще работают
        bot_running = psutil.pid_exists(bot_process.pid)
        monitor_running = psutil.pid_exists(monitor_process.pid)
        
        if not bot_running or not monitor_running:
            logger.error(f"Не удалось запустить процессы: бот {'работает' if bot_running else 'не работает'}, "
                         f"монитор {'работает' if monitor_running else 'не работает'}")
            
            # Убиваем оставшиеся процессы
            for pid in [bot_process.pid, monitor_process.pid]:
                if psutil.pid_exists(pid):
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except:
                        pass
            return False
        
        return bot_process, monitor_process
    except Exception as e:
        logger.error(f"Ошибка при запуске бота с монитором: {e}")
        return False

def monitor_bot_processes(bot_process, monitor_process):
    """Мониторит процессы бота и монитора, перезапускает их при необходимости."""
    logger.info("Начинаем мониторинг процессов бота и монитора здоровья")
    
    while True:
        try:
            # Проверяем, работают ли процессы
            bot_running = psutil.pid_exists(bot_process.pid)
            monitor_running = psutil.pid_exists(monitor_process.pid)
            
            if not bot_running or not monitor_running:
                logger.warning(f"Обнаружена остановка процессов: бот {'работает' if bot_running else 'не работает'}, "
                             f"монитор {'работает' if monitor_running else 'не работает'}")
                
                # Перезапускаем процессы
                logger.info("Перезапускаем все процессы...")
                
                # Сначала убиваем оставшиеся процессы
                kill_running_bots()
                time.sleep(2)
                
                # Затем запускаем заново
                result = start_bot_and_monitor()
                if result:
                    bot_process, monitor_process = result
                    logger.info(f"Процессы успешно перезапущены: бот (PID: {bot_process.pid}), "
                               f"монитор (PID: {monitor_process.pid})")
                else:
                    logger.error("Не удалось перезапустить процессы")
            
            # Обновляем статус каждые 30 секунд
            logger.info(f"Процессы работают: бот (PID: {bot_process.pid}), монитор (PID: {monitor_process.pid})")
        except Exception as e:
            logger.error(f"Ошибка в цикле мониторинга: {e}")
        
        # Ждем 30 секунд перед следующей проверкой
        time.sleep(30)

def main():
    """Основная функция для запуска и мониторинга бота в режиме фонового процесса."""
    logger.info("Запуск бота для Replit Deployment (Reserved VM Background Worker)")
    
    # Удаляем лок-файлы, если они остались от предыдущих запусков
    for lock_file in ['./uv.lock', './bot.lock', './telegram.lock', './instance.lock']:
        try:
            if os.path.exists(lock_file):
                os.remove(lock_file)
                logger.info(f"Удален lock-файл: {lock_file}")
        except Exception as e:
            logger.error(f"Не удалось удалить lock-файл {lock_file}: {e}")
    
    # Запускаем бота и монитор
    result = start_bot_and_monitor()
    if result:
        bot_process, monitor_process = result
        logger.info("Бот и монитор здоровья успешно запущены")
        
        # Начинаем мониторинг процессов и держим скрипт запущенным
        monitor_bot_processes(bot_process, monitor_process)
    else:
        logger.error("Не удалось запустить бота с монитором")
        sys.exit(1)

if __name__ == "__main__":
    main()