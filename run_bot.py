#!/usr/bin/env python
"""
Скрипт для запуска и поддержания работы Telegram бота.
Этот скрипт служит основной точкой входа для запуска бота.
"""
import os
import sys
import subprocess
import time
import signal
import logging
from datetime import datetime

# Путь к основному скрипту бота
BOT_SCRIPT = "main.py"
# Путь к скрипту мониторинга
MONITOR_SCRIPT = "bot_health_monitor.py"
# Максимальное количество перезапусков
MAX_RESTARTS = 10
# Время между перезапусками (в секундах)
RESTART_DELAY = 60

# Настройка логирования
log_directory = "logs"
if not os.path.exists(log_directory):
    os.makedirs(log_directory)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_directory, "run_bot.log")),
        logging.StreamHandler(sys.stdout)
    ]
)

# Глобальная переменная для отслеживания процесса бота
bot_process = None

def signal_handler(sig, frame):
    """Обработчик сигналов для корректного завершения"""
    logging.info(f"Получен сигнал {sig}, завершаем работу...")
    if bot_process:
        logging.info(f"Останавливаем бота (PID: {bot_process.pid})...")
        try:
            os.killpg(os.getpgid(bot_process.pid), signal.SIGTERM)
            # Даем боту время на корректное завершение
            bot_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            logging.warning("Бот не завершился вовремя, принудительно закрываем...")
            os.killpg(os.getpgid(bot_process.pid), signal.SIGKILL)
        except Exception as e:
            logging.error(f"Ошибка при остановке бота: {e}")
    sys.exit(0)

def start_bot():
    """Запускает бота и возвращает объект процесса"""
    global bot_process
    try:
        logging.info(f"Запуск бота ({BOT_SCRIPT})...")
        # Запускаем бота в отдельном процессе
        bot_process = subprocess.Popen(
            [sys.executable, BOT_SCRIPT],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid  # Создаем новую группу процессов
        )
        logging.info(f"Бот запущен с PID {bot_process.pid}")
        return bot_process
    except Exception as e:
        logging.error(f"Ошибка при запуске бота: {e}")
        return None

def start_monitor():
    """Запускает скрипт мониторинга здоровья"""
    try:
        logging.info(f"Запуск скрипта мониторинга ({MONITOR_SCRIPT})...")
        # Запускаем скрипт мониторинга в фоновом режиме
        monitor_process = subprocess.Popen(
            [sys.executable, MONITOR_SCRIPT],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid  # Создаем новую группу процессов
        )
        logging.info(f"Скрипт мониторинга запущен с PID {monitor_process.pid}")
        return monitor_process
    except Exception as e:
        logging.error(f"Ошибка при запуске скрипта мониторинга: {e}")
        return None

def main():
    """Основная функция для запуска и поддержания работы бота"""
    # Устанавливаем обработчик сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logging.info("===== ЗАПУСК СИСТЕМЫ УПРАВЛЕНИЯ БОТОМ =====")
    
    # Запускаем скрипт для проверки и остановки существующих экземпляров бота
    logging.info("Проверка наличия запущенных экземпляров бота...")
    try:
        import ensure_single_instance
        ensure_single_instance.main()
        logging.info("Проверка завершена, запуск бота...")
    except Exception as e:
        logging.error(f"Ошибка при проверке существующих экземпляров бота: {e}")
    
    # Небольшая пауза для того, чтобы все процессы корректно остановились
    time.sleep(5)
    
    restart_count = 0
    
    # Запускаем скрипт мониторинга
    monitor_process = start_monitor()
    
    # Запускаем бота первый раз
    process = start_bot()
    
    try:
        # Основной цикл проверки состояния бота
        while restart_count < MAX_RESTARTS:
            # Проверяем, работает ли бот
            if process and process.poll() is None:
                # Бот работает, просто ждем
                time.sleep(30)  # Проверяем каждые 30 секунд
            else:
                # Бот завершил работу или не был запущен
                if process:
                    returncode = process.poll()
                    stderr = process.stderr.read().decode('utf-8', errors='ignore')
                    logging.warning(f"Бот завершил работу с кодом {returncode}")
                    if stderr:
                        logging.error(f"Ошибка бота: {stderr}")
                
                # Увеличиваем счетчик перезапусков
                restart_count += 1
                
                if restart_count >= MAX_RESTARTS:
                    logging.critical(f"Достигнуто максимальное количество перезапусков ({MAX_RESTARTS})")
                    break
                
                # Ждем перед перезапуском
                wait_time = RESTART_DELAY * restart_count
                logging.info(f"Перезапуск бота ({restart_count}/{MAX_RESTARTS}) через {wait_time} секунд...")
                time.sleep(wait_time)
                
                # Перезапускаем бота
                process = start_bot()
        
        logging.critical("Система управления ботом завершает работу!")
    
    except KeyboardInterrupt:
        logging.info("Получен сигнал прерывания (Ctrl+C), завершаем работу...")
    except Exception as e:
        logging.error(f"Критическая ошибка в системе управления ботом: {e}")
    finally:
        # Останавливаем бота и скрипт мониторинга
        if process and process.poll() is None:
            logging.info(f"Останавливаем бота (PID: {process.pid})...")
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            except Exception as e:
                logging.error(f"Ошибка при остановке бота: {e}")
        
        if monitor_process and monitor_process.poll() is None:
            logging.info(f"Останавливаем скрипт мониторинга (PID: {monitor_process.pid})...")
            try:
                os.killpg(os.getpgid(monitor_process.pid), signal.SIGTERM)
            except Exception as e:
                logging.error(f"Ошибка при остановке скрипта мониторинга: {e}")
        
        logging.info("===== СИСТЕМА УПРАВЛЕНИЯ БОТОМ ЗАВЕРШЕНА =====")

if __name__ == "__main__":
    main()