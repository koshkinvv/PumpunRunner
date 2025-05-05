#!/usr/bin/env python3
"""
Скрипт для управления запуском бота через workflow bot_runner.
Этот скрипт запускается через воркфлоу и обеспечивает корректную настройку webhook.
"""

import logging
import os
import sys
import time
import subprocess
import signal
import requests

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Константы
HEALTH_FILE = "bot_health.txt"

def update_health_check():
    """Обновляет файл проверки здоровья текущим временем."""
    try:
        import datetime
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(HEALTH_FILE, "w") as f:
            f.write(now)
        logging.info(f"Файл здоровья обновлен: {now}")
    except Exception as e:
        logging.error(f"Ошибка при обновлении файла здоровья: {e}")

def run_bot_process():
    """Запускает процесс бота через run_bot_simple.py"""
    try:
        logging.info("Запускаем run_bot_simple.py...")
        # Используем subprocess.Popen для запуска процесса в фоне
        process = subprocess.Popen(["python", "run_bot_simple.py"])
        
        # Настраиваем обработчик сигналов для корректного завершения дочернего процесса
        def signal_handler(sig, frame):
            logging.info("Получен сигнал остановки. Завершаем дочерний процесс...")
            if process.poll() is None:  # Если процесс еще жив
                process.terminate()
                process.wait(timeout=5)
            logging.info("Завершение работы.")
            sys.exit(0)
        
        # Регистрируем обработчики сигналов
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Основной цикл мониторинга процесса
        while True:
            # Проверяем, жив ли процесс
            if process.poll() is not None:
                exit_code = process.returncode
                logging.error(f"Процесс бота завершился с кодом {exit_code}. Перезапускаем...")
                # Перезапускаем процесс
                process = subprocess.Popen(["python", "run_bot_simple.py"])
            
            # Обновляем файл здоровья
            update_health_check()
            
            # Ждем перед следующей проверкой
            time.sleep(30)
    
    except Exception as e:
        logging.error(f"Ошибка при запуске процесса бота: {e}")
        return False
    
    return True

def main():
    """Основная функция запуска и мониторинга бота."""
    logging.info("Запуск bot_runner.py через workflow...")
    
    # Запускаем процесс бота и мониторим его
    while True:
        success = run_bot_process()
        if not success:
            logging.error("Не удалось запустить процесс бота. Повторная попытка через 5 секунд...")
            time.sleep(5)
        else:
            # Если run_bot_process() вернул True, значит цикл мониторинга был прерван
            # и нам нужно его перезапустить
            logging.info("Цикл мониторинга бота завершен. Перезапуск...")
            time.sleep(5)

if __name__ == "__main__":
    main()