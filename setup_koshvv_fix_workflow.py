"""
Скрипт для настройки Replit workflow для запуска бота с исправлениями
для пользователя koshvv и других пользователей.
"""
import os
import json
import subprocess
import time

def setup_workflow():
    """Настраивает workflow для запуска бота с исправлениями"""
    print("Настройка workflow для запуска бота с исправлениями...")
    
    # Создаем скрипт запуска
    workflow_script = """#!/bin/bash
# Workflow script для запуска бота с исправлениями
# Автоматически сбрасывает API и перезапускает бота при необходимости

# Останавливаем все запущенные процессы бота
pkill -f "python.*bot.*py" || true

# Сбрасываем сессию Telegram API
python <<EOF
import os
import requests
import time

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
if not TELEGRAM_TOKEN:
    print("Ошибка: TELEGRAM_TOKEN не найден в переменных окружения")
    exit(1)

# Удаляем веб-хук, если он установлен
response = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteWebhook")
print(f"Вебхук удален: {response.json()}")

# Получаем текущий offset
response = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset=-1&limit=1")
updates = response.json().get('result', [])
if updates:
    # Увеличиваем offset на 1, чтобы очистить очередь
    next_offset = updates[0]['update_id'] + 1
    response = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={next_offset}")
    print(f"Очистка очереди обновлений с offset={next_offset}: {response.json()}")
EOF

# Запускаем бота с нуля
echo "Запуск бота с исправленной обработкой ошибок..."
python run_koshvv_fix.py
"""
    
    # Записываем скрипт в файл
    with open("koshvv_fix_workflow.sh", "w") as f:
        f.write(workflow_script)
    
    # Делаем скрипт исполняемым
    os.chmod("koshvv_fix_workflow.sh", 0o755)
    print("Скрипт koshvv_fix_workflow.sh создан и настроен")
    
    # Создаем или обновляем run_koshvv_fix.py, если его еще нет
    if not os.path.exists("run_koshvv_fix.py"):
        runner_script = """#!/usr/bin/env python3
'''
Скрипт для запуска бота с исправлениями для пользователя koshvv и других пользователей.
Включает дополнительную обработку ошибок и мониторинг.
'''
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
    '''Завершает существующие процессы бота'''
    logging.info("Завершение существующих процессов бота...")
    try:
        subprocess.run(['pkill', '-f', 'python.*bot.*py'], check=False)
        time.sleep(0.5)  # Даем процессам время на завершение
    except Exception as e:
        logging.error(f"Ошибка при завершении процессов: {e}")

def reset_telegram_api():
    '''Сбрасывает сессию Telegram API'''
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
    '''Запускает бота с исправлениями'''
    logging.info("Запуск бота с исправлениями для koshvv...")
    try:
        # Запускаем бота в отдельном процессе
        bot_process = subprocess.Popen(
            [sys.executable, "bot_modified.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        logging.info(f"Бот запущен с PID {bot_process.pid}")
        
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
    '''Основная функция запуска'''
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
"""
        with open("run_koshvv_fix.py", "w") as f:
            f.write(runner_script)
        os.chmod("run_koshvv_fix.py", 0o755)
        print("Скрипт run_koshvv_fix.py создан и настроен")
    
    # Запускаем workflow
    try:
        print("Запуск workflow для бота...")
        subprocess.Popen(["./koshvv_fix_workflow.sh"], 
                        stdout=subprocess.PIPE, 
                        stderr=subprocess.PIPE)
        print("Workflow запущен успешно! Бот должен работать в фоновом режиме.")
    except Exception as e:
        print(f"Ошибка при запуске workflow: {e}")

if __name__ == "__main__":
    setup_workflow()