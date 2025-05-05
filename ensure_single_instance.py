#!/usr/bin/env python
"""
Скрипт для проверки и обеспечения запуска только одного экземпляра бота.
"""
import os
import sys
import signal
import logging
import psutil
import time

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def find_bot_processes():
    """
    Находит все процессы Python, связанные с Telegram ботом.
    Возвращает список PID процессов.
    """
    bot_pids = []
    keywords = ["main.py", "run_bot.py", "telegram", "bot_modified.py", "deploy_bot.py", "bot_monitor.py"]
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # Ищем процессы Python
            if 'python' in proc.info['name'].lower():
                cmdline = ' '.join(proc.info['cmdline'] if proc.info['cmdline'] else [])
                # Проверяем, относится ли процесс к боту
                if any(keyword in cmdline for keyword in keywords):
                    # Исключаем текущий процесс
                    if proc.pid != os.getpid():
                        bot_pids.append(proc.pid)
                        logging.info(f"Найден процесс бота: PID {proc.pid}, командная строка: {cmdline}")
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    
    return bot_pids

def terminate_process(pid, timeout=5):
    """
    Корректно завершает процесс по его PID.
    Сначала отправляет SIGTERM, затем если процесс не завершился - SIGKILL.
    """
    try:
        process = psutil.Process(pid)
        logging.info(f"Останавливаем процесс с PID {pid}...")
        
        # Отправляем сигнал SIGTERM для корректного завершения
        process.send_signal(signal.SIGTERM)
        
        # Ждем завершения процесса
        try:
            process.wait(timeout=timeout)
            logging.info(f"Процесс с PID {pid} успешно остановлен")
            return True
        except psutil.TimeoutExpired:
            # Если процесс не завершился за отведенное время, используем SIGKILL
            logging.warning(f"Процесс с PID {pid} не завершился за {timeout} секунд, применяем SIGKILL")
            process.send_signal(signal.SIGKILL)
            time.sleep(1)
            return not psutil.pid_exists(pid)
    except psutil.NoSuchProcess:
        logging.info(f"Процесс с PID {pid} уже не существует")
        return True
    except Exception as e:
        logging.error(f"Ошибка при остановке процесса с PID {pid}: {e}")
        return False

def main():
    """
    Основная функция для проверки и остановки существующих экземпляров бота.
    """
    logging.info("Проверка и остановка существующих экземпляров бота...")
    
    # Находим все процессы бота
    bot_pids = find_bot_processes()
    
    if not bot_pids:
        logging.info("Активных экземпляров бота не найдено")
        return
    
    logging.info(f"Найдено {len(bot_pids)} активных экземпляров бота: {bot_pids}")
    
    # Останавливаем найденные процессы
    for pid in bot_pids:
        terminate_process(pid)
    
    # Проверяем, остались ли еще процессы бота
    remaining_pids = find_bot_processes()
    if remaining_pids:
        logging.warning(f"Не удалось остановить все экземпляры бота. Оставшиеся PID: {remaining_pids}")
    else:
        logging.info("Все экземпляры бота успешно остановлены")

if __name__ == "__main__":
    main()