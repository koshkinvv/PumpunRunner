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

def kill_monitors():
    """Убивает все запущенные процессы монитора."""
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['cmdline'] and any('bot_monitor.py' in cmd for cmd in proc.info['cmdline']):
                    logger.info(f"Убиваем процесс монитора: {proc.info['pid']}")
                    os.kill(proc.info['pid'], signal.SIGTERM)
                    time.sleep(1)
                    if psutil.pid_exists(proc.info['pid']):
                        os.kill(proc.info['pid'], signal.SIGKILL)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
    except Exception as e:
        logger.error(f"Ошибка при убийстве процессов монитора: {e}")

def create_monitor_watchdog():
    """Запускает мониторинг монитора."""
    def watchdog_function():
        while True:
            try:
                # Проверяем, запущен ли монитор
                monitor_running = False
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        if proc.info['cmdline'] and any('bot_monitor.py' in cmd for cmd in proc.info['cmdline']):
                            monitor_running = True
                            break
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass
                
                # Если монитор не запущен, перезапускаем его
                if not monitor_running:
                    logger.warning("Монитор не запущен, перезапускаем...")
                    
                    # Создаем директорию для логов, если её нет
                    os.makedirs("logs", exist_ok=True)
                    
                    # Генерируем временную метку для файла логов
                    timestamp = time.strftime("%Y%m%d-%H%M%S")
                    
                    # Запускаем монитор в отдельном процессе
                    monitor_process = subprocess.Popen(
                        ["python", "bot_monitor.py"],
                        stdout=open(f"logs/monitor_output_{timestamp}.log", "a"),
                        stderr=open(f"logs/monitor_error_{timestamp}.log", "a"),
                        env=dict(os.environ),
                        cwd=os.getcwd()
                    )
                    logger.info(f"Монитор перезапущен (PID: {monitor_process.pid})")
            except Exception as e:
                logger.error(f"Ошибка в мониторинге монитора: {e}")
            
            # Проверяем каждые 60 секунд
            time.sleep(60)
    
    # Запускаем функцию в отдельном потоке
    import threading
    watchdog_thread = threading.Thread(target=watchdog_function, daemon=True)
    watchdog_thread.start()
    return watchdog_thread

def start_bot_with_monitor():
    """Запускает бота вместе с монитором здоровья."""
    try:
        # Сначала убиваем любые запущенные экземпляры бота и монитора
        kill_running_bots()
        kill_monitors()
        
        # Создаем директорию для логов, если её нет
        os.makedirs("logs", exist_ok=True)
        
        # Генерируем временную метку для логов
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        
        # Запускаем бота с перенаправлением выхода в файлы логов
        logger.info("Запускаем бота...")
        bot_process = subprocess.Popen(
            ["python", "main.py"],
            stdout=open(f"logs/bot_output_{timestamp}.log", "a"),
            stderr=open(f"logs/bot_error_{timestamp}.log", "a"),
            env=dict(os.environ),  # Передаем все текущие переменные окружения
            cwd=os.getcwd()        # Запускаем из текущей директории
        )
        
        # Запускаем монитор в отдельном процессе
        logger.info("Запускаем монитор здоровья...")
        monitor_process = subprocess.Popen(
            ["python", "bot_monitor.py"],
            stdout=open(f"logs/monitor_output_{timestamp}.log", "a"),
            stderr=open(f"logs/monitor_error_{timestamp}.log", "a"),
            env=dict(os.environ),
            cwd=os.getcwd()
        )
        
        logger.info(f"Бот (PID: {bot_process.pid}) и монитор здоровья (PID: {monitor_process.pid}) запущены")
        logger.info(f"Логи бота: logs/bot_output_{timestamp}.log, logs/bot_error_{timestamp}.log")
        logger.info(f"Логи монитора: logs/monitor_output_{timestamp}.log, logs/monitor_error_{timestamp}.log")
        
        # Запускаем мониторинг монитора
        create_monitor_watchdog()
        
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
        
        logger.info("Все компоненты успешно запущены")
        return True
    except Exception as e:
        logger.error(f"Ошибка при запуске бота с монитором: {e}")
        import traceback
        logger.error(traceback.format_exc())
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