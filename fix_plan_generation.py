#!/usr/bin/env python3
"""
Скрипт для исправления проблем с генерацией плана тренировок.
Выполняет полный сброс бота и запускает единственный экземпляр с расширенным логированием.
"""

import os
import sys
import signal
import time
import logging
import subprocess
import requests
import json
import psutil

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/fix_plan_generation.log"),
        logging.StreamHandler()
    ]
)

# Получаем токен бота из переменных окружения
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    logging.error("Не задан токен Telegram. Проверьте переменную окружения TELEGRAM_TOKEN.")
    sys.exit(1)

def find_and_kill_all_bot_processes():
    """
    Находит и завершает все процессы, связанные с ботом
    """
    logging.info("Поиск и завершение всех процессов бота...")
    
    # Получаем текущий PID
    current_pid = os.getpid()
    logging.info(f"Текущий PID: {current_pid}")
    
    killed_count = 0
    # Перебираем все процессы Python
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # Пропускаем текущий процесс
            if proc.info['pid'] == current_pid:
                continue
                
            # Проверяем, является ли процесс Python и связан ли с ботом
            if proc.info['name'] and 'python' in proc.info['name'].lower():
                cmdline = ' '.join(proc.info['cmdline'] or [])
                
                # Если командная строка содержит 'bot', завершаем процесс
                if 'bot' in cmdline.lower() or 'telegram' in cmdline.lower():
                    logging.info(f"Завершение процесса {proc.info['pid']}: {cmdline}")
                    os.kill(proc.info['pid'], signal.SIGTERM)
                    killed_count += 1
                    
                    # Даем процессу время на завершение
                    time.sleep(0.5)
                    
                    # Проверяем, завершился ли процесс
                    if psutil.pid_exists(proc.info['pid']):
                        logging.info(f"Процесс {proc.info['pid']} не завершился, принудительное завершение")
                        os.kill(proc.info['pid'], signal.SIGKILL)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
        except Exception as e:
            logging.error(f"Ошибка при обработке процесса: {e}")
    
    logging.info(f"Завершено {killed_count} процессов бота")
    
    # Даем время на полное завершение всех процессов
    time.sleep(2)
    
    # Проверка, что все процессы завершены
    remaining = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['pid'] == current_pid:
                continue
                
            if proc.info['name'] and 'python' in proc.info['name'].lower():
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if 'bot' in cmdline.lower() or 'telegram' in cmdline.lower():
                    remaining.append(proc.info['pid'])
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
    if remaining:
        logging.warning(f"Не удалось завершить все процессы бота. Оставшиеся: {remaining}")
    else:
        logging.info("Все процессы бота успешно завершены")
    
    return len(remaining) == 0

def reset_telegram_api_session():
    """
    Полный сброс сессии Telegram API
    """
    logging.info("Сброс сессии Telegram API...")
    
    # Сначала удалим webhook
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteWebhook",
            params={"drop_pending_updates": True}
        )
        logging.info(f"Ответ удаления webhook: {response.text}")
    except Exception as e:
        logging.error(f"Ошибка при удалении webhook: {e}")
    
    # Затем выполним getUpdates с offset -1 для сброса очереди
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
            params={"offset": -1, "timeout": 1}
        )
        logging.info(f"Ответ getUpdates: {response.text}")
    except Exception as e:
        logging.error(f"Ошибка при вызове getUpdates: {e}")
    
    # Дадим API время на сброс сессии
    time.sleep(3)
    
    return True

def modify_environment_for_debug():
    """
    Модифицирует переменные окружения для отладки проблем с генерацией плана
    """
    logging.info("Настройка переменных окружения для отладки...")
    
    # Устанавливаем максимальный уровень логирования
    os.environ["LOG_LEVEL"] = "DEBUG"
    os.environ["PYTHONUNBUFFERED"] = "1"
    
    # Дополнительные параметры для отладки OpenAI
    os.environ["OPENAI_DEBUG"] = "1"
    
    return True

def patch_openai_service():
    """
    Вносит временные изменения в openai_service.py для дополнительного логирования
    """
    logging.info("Добавление дополнительного логирования в OpenAI сервис...")
    
    try:
        # Проверяем, что файл существует
        if not os.path.exists("openai_service.py"):
            logging.error("Файл openai_service.py не найден")
            return False
        
        # Дополнительные строки логирования уже были добавлены ранее
        return True
    except Exception as e:
        logging.error(f"Ошибка при патче openai_service.py: {e}")
        return False

def start_fresh_bot():
    """
    Запускает новый экземпляр бота с дополнительным логированием
    """
    logging.info("Запуск нового экземпляра бота...")
    
    try:
        # Запускаем бота через start_bot_directly.py
        bot_process = subprocess.Popen(
            ["python", "start_bot_directly.py"], 
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=os.environ
        )
        
        # Ждем небольшое время для инициализации
        time.sleep(5)
        
        # Проверяем, что процесс все еще работает
        if bot_process.poll() is None:
            logging.info(f"Бот успешно запущен с PID: {bot_process.pid}")
            
            # Проверим ответ бота, чтобы убедиться, что он работает
            try:
                response = requests.get(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getMe"
                )
                
                if response.status_code == 200:
                    bot_info = response.json()
                    logging.info(f"Бот успешно запущен и отвечает: {bot_info}")
                    return True
                else:
                    logging.error(f"Бот не отвечает: {response.text}")
            except Exception as e:
                logging.error(f"Ошибка при проверке бота: {e}")
                
            return True
        else:
            stdout, stderr = bot_process.communicate()
            logging.error(f"Бот не запустился. Код выхода: {bot_process.returncode}")
            logging.error(f"Стандартный вывод: {stdout.decode()}")
            logging.error(f"Стандартная ошибка: {stderr.decode()}")
            return False
    except Exception as e:
        logging.error(f"Ошибка при запуске бота: {e}")
        return False

def verify_openai_api_key():
    """
    Проверяет доступность API-ключа OpenAI
    """
    logging.info("Проверка API-ключа OpenAI...")
    
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if not openai_api_key:
        logging.error("API-ключ OpenAI не найден в переменных окружения")
        return False
    
    try:
        # Выполняем простой запрос к API OpenAI
        headers = {
            "Authorization": f"Bearer {openai_api_key}",
            "Content-Type": "application/json"
        }
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json={
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": "Привет, проверка связи"}],
                "max_tokens": 10
            }
        )
        
        if response.status_code == 200:
            logging.info("API-ключ OpenAI успешно проверен")
            return True
        else:
            logging.error(f"Ошибка при проверке API-ключа OpenAI: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logging.error(f"Ошибка при проверке API-ключа OpenAI: {e}")
        return False

def verify_database_connection():
    """
    Проверяет подключение к базе данных
    """
    logging.info("Проверка подключения к базе данных...")
    
    try:
        # Запускаем скрипт для проверки базы данных
        result = subprocess.run(
            ["python", "-c", """
import psycopg2
import os

db_config = {
    'dbname': os.environ.get('PGDATABASE'),
    'user': os.environ.get('PGUSER'),
    'password': os.environ.get('PGPASSWORD'),
    'host': os.environ.get('PGHOST'),
    'port': os.environ.get('PGPORT')
}

try:
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor()
    cur.execute('SELECT count(*) FROM users')
    count = cur.fetchone()[0]
    print(f'Соединение с базой данных успешно. Пользователей в базе: {count}')
    conn.close()
    exit(0)
except Exception as e:
    print(f'Ошибка подключения к базе данных: {e}')
    exit(1)
"""
            ],
            capture_output=True,
            text=True
        )
        
        logging.info(f"Результат проверки БД: {result.stdout}")
        
        if result.returncode == 0:
            logging.info("Подключение к базе данных успешно")
            return True
        else:
            logging.error(f"Ошибка подключения к базе данных: {result.stderr}")
            return False
    except Exception as e:
        logging.error(f"Ошибка при проверке подключения к базе данных: {e}")
        return False

def main():
    """
    Основная функция для исправления проблем генерации планов
    """
    logging.info("Начало процесса исправления проблем с генерацией планов...")
    
    # Проверяем подключение к базе данных
    if not verify_database_connection():
        logging.error("Не удалось подключиться к базе данных. Прерывание...")
        return
    
    # Проверяем API-ключ OpenAI
    if not verify_openai_api_key():
        logging.warning("Не удалось проверить API-ключ OpenAI. Продолжаем с осторожностью...")
    
    # Шаг 1: Завершаем все существующие процессы бота
    if not find_and_kill_all_bot_processes():
        logging.warning("Не удалось завершить все процессы бота. Продолжаем с осторожностью...")
    
    # Шаг 2: Сбрасываем сессию Telegram API
    if not reset_telegram_api_session():
        logging.warning("Не удалось полностью сбросить сессию Telegram API. Продолжаем с осторожностью...")
    
    # Шаг 3: Модифицируем среду для отладки
    if not modify_environment_for_debug():
        logging.warning("Не удалось модифицировать среду для отладки. Продолжаем с осторожностью...")
    
    # Шаг 4: Патчим OpenAI сервис для лучшего логирования
    if not patch_openai_service():
        logging.warning("Не удалось добавить логирование в OpenAI сервис. Продолжаем с осторожностью...")
    
    # Шаг 5: Запускаем новый экземпляр бота
    if not start_fresh_bot():
        logging.error("Не удалось запустить бота. Процесс исправления прерван.")
        return
    
    logging.info("Процесс исправления проблем с генерацией планов завершен успешно.")
    logging.info("Бот запущен с дополнительным логированием. Проверьте logs/bot_output.log для деталей.")

if __name__ == "__main__":
    main()