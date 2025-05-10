#!/usr/bin/env python3
"""
Скрипт для прямого запуска бота с исправлениями и улучшенной обработкой ошибок.
"""
import os
import sys
import time
import signal
import subprocess
import logging
import requests

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def kill_existing_bots():
    """Завершает существующие процессы бота"""
    logging.info("Завершение существующих процессов бота...")
    try:
        subprocess.run(['pkill', '-f', 'python.*bot.*py'], check=False)
        time.sleep(0.5)  # Даем процессам время на завершение
    except Exception as e:
        logging.error(f"Ошибка при завершении процессов: {e}")

def reset_telegram_api():
    """Сбрасывает сессию Telegram API"""
    logging.info("Сброс сессии Telegram API...")
    token = os.environ.get('TELEGRAM_TOKEN')
    if not token:
        logging.error("TELEGRAM_TOKEN не найден в переменных окружения")
        return False
    
    try:
        # Удаляем веб-хук
        response = requests.get(f"https://api.telegram.org/bot{token}/deleteWebhook")
        if response.status_code == 200 and response.json().get('ok'):
            logging.info("Вебхук успешно удален")
        else:
            logging.error(f"Ошибка при удалении вебхука: {response.json()}")
        
        # Получаем текущий offset и очищаем очередь
        time.sleep(1)  # Ждем для обработки предыдущего запроса
        response = requests.get(f"https://api.telegram.org/bot{token}/getUpdates?offset=-1&limit=1")
        if response.status_code == 200:
            updates = response.json().get('result', [])
            if updates:
                next_offset = updates[0]['update_id'] + 1
                response = requests.get(f"https://api.telegram.org/bot{token}/getUpdates?offset={next_offset}")
                logging.info(f"Очистка очереди обновлений с offset={next_offset}")
        
        return True
    except Exception as e:
        logging.error(f"Ошибка при сбросе API: {e}")
        return False

def start_bot():
    """Запускает бота с исправлениями"""
    logging.info("Запуск бота с исправлениями...")
    try:
        # Запускаем бота напрямую в текущем процессе
        # Импортируем модуль бота
        try:
            from bot_modified import setup_bot
            
            # Запускаем бота
            bot = setup_bot()
            bot.run_polling()
            return True
        except Exception as e:
            logging.exception(f"Ошибка при запуске бота через import: {e}")
            
            # Если не удалось импортировать, запускаем как отдельный процесс
            bot_process = subprocess.Popen(
                [sys.executable, "bot_modified.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            logging.info(f"Бот запущен как процесс с PID {bot_process.pid}")
            
            # Читаем и логируем вывод процесса
            while bot_process.poll() is None:
                line = bot_process.stdout.readline().strip()
                if line:
                    logging.info(f"BOT: {line}")
            
            # Если процесс завершился, проверяем код возврата
            return_code = bot_process.returncode
            if return_code != 0:
                logging.error(f"Бот завершился с ошибкой, код: {return_code}")
                return False
            else:
                logging.info("Бот завершил работу корректно")
                return True
    
    except Exception as e:
        logging.exception(f"Критическая ошибка при запуске бота: {e}")
        return False

def main():
    """Основная функция запуска"""
    try:
        # Завершаем существующие процессы
        kill_existing_bots()
        
        # Сбрасываем сессию API
        if not reset_telegram_api():
            logging.error("Не удалось сбросить сессию API, продолжаем запуск...")
        
        # Запускаем бота
        start_bot()
        
    except KeyboardInterrupt:
        logging.info("Прервано пользователем")
    except Exception as e:
        logging.exception(f"Неперехваченная ошибка: {e}")

if __name__ == "__main__":
    main()