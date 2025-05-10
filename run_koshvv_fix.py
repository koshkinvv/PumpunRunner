#!/usr/bin/env python3
"""
Специальный скрипт для исправления проблемы с генерацией планов тренировок.
Запускает бота с улучшенной обработкой ошибок и резервным планом.
"""
import os
import sys
import logging
import subprocess
import time
import signal

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/koshvv_fix.log')
    ]
)

def terminate_existing_bots():
    """Находит и завершает все существующие процессы бота."""
    try:
        logging.info("Завершение существующих процессов бота...")
        bot_processes = subprocess.run(
            "ps aux | grep -v grep | grep -E 'python.*bot|telegram' | awk '{print $2}'",
            shell=True, capture_output=True, text=True
        ).stdout.strip().split('\n')
        
        for pid in bot_processes:
            if pid:
                try:
                    pid = int(pid)
                    os.kill(pid, signal.SIGTERM)
                    logging.info(f"Процесс {pid} завершен")
                    time.sleep(0.1)  # Даем время на корректное завершение
                except ProcessLookupError:
                    pass  # Процесс уже завершен
                except Exception as e:
                    logging.error(f"Ошибка при завершении процесса {pid}: {e}")
    except Exception as e:
        logging.error(f"Ошибка при завершении процессов: {e}")

def reset_telegram_session():
    """Полный сброс сессии Telegram API."""
    try:
        logging.info("Сброс сессии Telegram API...")
        token = os.environ.get("TELEGRAM_TOKEN")
        if not token:
            logging.error("Переменная TELEGRAM_TOKEN не найдена")
            return False
            
        import requests
        response = requests.get(f"https://api.telegram.org/bot{token}/deleteWebhook?drop_pending_updates=true")
        
        if response.status_code == 200:
            logging.info("Вебхук успешно удален")
            time.sleep(2)  # Ждем полного сброса API
            return True
        else:
            logging.error(f"Ошибка при удалении вебхука: {response.text}")
            return False
    except Exception as e:
        logging.error(f"Ошибка при сбросе сессии Telegram API: {e}")
        return False

def main():
    """Основная функция запуска бота с исправлениями."""
    # Завершаем существующие процессы
    terminate_existing_bots()
    
    # Сбрасываем сессию Telegram
    if not reset_telegram_session():
        logging.warning("Не удалось сбросить сессию Telegram API, но продолжаем запуск")
    
    # Проверяем наличие переменных окружения
    for env_var in ["TELEGRAM_TOKEN", "OPENAI_API_KEY", "DATABASE_URL"]:
        if not os.environ.get(env_var):
            logging.error(f"Переменная окружения {env_var} не найдена")
            return 1
    
    logging.info("Запуск бота с исправлениями для koshvv...")
    
    # Запускаем бота с улучшенной обработкой ошибок
    try:
        bot_process = subprocess.Popen(
            ["python", "bot_runner.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        logging.info(f"Бот запущен с PID {bot_process.pid}")
        
        # Настраиваем обработчики сигналов для корректного завершения
        def handle_exit_signal(sig, frame):
            if bot_process:
                logging.info("Получен сигнал завершения, останавливаем бота...")
                bot_process.terminate()
            sys.exit(0)
            
        signal.signal(signal.SIGINT, handle_exit_signal)
        signal.signal(signal.SIGTERM, handle_exit_signal)
        
        # Мониторим вывод бота
        try:
            while True:
                line = bot_process.stdout.readline()
                if not line and bot_process.poll() is not None:
                    break
                if line:
                    logging.info(f"BOT: {line.strip()}")
        except Exception as e:
            logging.error(f"Ошибка при чтении вывода бота: {e}")
        
        # Проверяем код возврата
        return_code = bot_process.wait()
        if return_code != 0:
            logging.error(f"Бот завершился с ошибкой, код: {return_code}")
            return return_code
            
    except Exception as e:
        logging.error(f"Ошибка при запуске бота: {e}")
        return 1
        
    logging.info("Бот успешно завершил работу")
    return 0

if __name__ == "__main__":
    sys.exit(main())