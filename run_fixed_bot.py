#!/usr/bin/env python3
"""
Запускает исправленный бот с улучшенной обработкой форматов планов тренировок.
"""
import os
import subprocess
import time
import logging
import signal
import sys

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/fixed_bot.log"),
        logging.StreamHandler()
    ]
)

def find_and_kill_processes():
    """Находит и завершает все процессы бота."""
    logging.info("Останавливаем существующие процессы бота...")
    
    try:
        # Ищем все процессы Python, связанные с ботом
        result = subprocess.run(
            "ps aux | grep -v grep | grep -E 'python.*bot' | awk '{print $2}'",
            shell=True, text=True, capture_output=True
        )
        
        pids = result.stdout.strip().split('\n')
        for pid in pids:
            if pid:
                try:
                    os.kill(int(pid), signal.SIGTERM)
                    logging.info(f"Процесс {pid} остановлен")
                except Exception as e:
                    if "No such process" not in str(e):
                        logging.error(f"Ошибка при остановке процесса {pid}: {e}")
    except Exception as e:
        logging.error(f"Ошибка при поиске процессов: {e}")

def reset_telegram_api():
    """Очищает сессию Telegram API."""
    logging.info("Очищаем сеанс Telegram API...")
    
    try:
        # Получаем токен из переменной окружения
        token = os.environ.get("TELEGRAM_TOKEN")
        if not token:
            logging.error("Переменная TELEGRAM_TOKEN не установлена")
            return
        
        # Выполняем запрос к API для удаления вебхука
        import requests
        requests.get(f"https://api.telegram.org/bot{token}/deleteWebhook?drop_pending_updates=true")
        
        # Ждем немного для полного сброса
        time.sleep(1)
    except Exception as e:
        logging.error(f"Ошибка при сбросе Telegram API: {e}")

def start_bot():
    """Запускает бот с исправленной обработкой форматов тренировок."""
    logging.info("Запускаем бота с исправленной обработкой форматов тренировок...")
    
    try:
        # Запускаем скрипт запуска бота
        bot_process = subprocess.Popen(
            ["python", "bot_runner.py"], 
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        # Логируем запуск процесса
        logging.info(f"Бот запущен, PID: {bot_process.pid}")
        
        # Возвращаем процесс для дальнейшего мониторинга
        return bot_process
    except Exception as e:
        logging.error(f"Ошибка при запуске бота: {e}")
        return None

def main():
    """Основная функция для запуска и мониторинга бота."""
    # Останавливаем все существующие процессы
    find_and_kill_processes()
    
    # Сбрасываем Telegram API сессию
    reset_telegram_api()
    
    # Запускаем бот
    bot_process = start_bot()
    
    if not bot_process:
        logging.error("Не удалось запустить бота")
        return 1
    
    # Настраиваем обработчик сигналов для корректного завершения
    def signal_handler(sig, frame):
        logging.info("Получен сигнал завершения, останавливаем бота...")
        try:
            bot_process.terminate()
        except:
            pass
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Мониторим процесс бота
        while True:
            # Читаем и логируем вывод
            line = bot_process.stdout.readline()
            if not line and bot_process.poll() is not None:
                break
            
            if line:
                logging.info(line.strip())
            
            # Проверяем состояние процесса
            if bot_process.poll() is not None:
                logging.warning(f"Бот остановился с кодом: {bot_process.returncode}")
                
                # Перезапускаем бот, если он остановился
                logging.info("Перезапускаем бота...")
                bot_process = start_bot()
                
                if not bot_process:
                    logging.error("Не удалось перезапустить бота")
                    return 1
    except Exception as e:
        logging.error(f"Ошибка в основном цикле: {e}")
    finally:
        # Корректно останавливаем бот при выходе
        try:
            bot_process.terminate()
        except:
            pass
    
    return 0

if __name__ == "__main__":
    sys.exit(main())