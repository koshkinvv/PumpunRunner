#!/usr/bin/env python
"""
Скрипт для полной очистки сессий Telegram API и корректного перезапуска бота.
Этот скрипт выполняет:
1. Остановку всех запущенных процессов бота
2. Удаление веб-хука, если он установлен
3. Полный сброс очереди обновлений (offset) через API
4. Запуск единственного экземпляра бота с нуля
"""
import os
import sys
import time
import signal
import logging
import requests
import json
import psutil
import subprocess

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Получаем токен из переменных окружения
TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    logger.error("Переменная окружения TELEGRAM_TOKEN не найдена")
    sys.exit(1)


def find_and_kill_all_bot_processes():
    """
    Находит и завершает все процессы, связанные с ботом
    """
    logger.info("Поиск и завершение всех процессов бота...")
    
    keywords = ["main.py", "run_bot.py", "telegram", "bot_modified.py", "deploy_bot.py", "bot_monitor.py"]
    killed_count = 0
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.pid == os.getpid():  # Пропускаем текущий процесс
                continue
                
            if 'python' in proc.info['name'].lower():
                cmdline = ' '.join(proc.info['cmdline'] if proc.info['cmdline'] else [])
                
                if any(keyword in cmdline for keyword in keywords):
                    logger.info(f"Завершаем процесс: PID {proc.pid}, командная строка: {cmdline}")
                    try:
                        proc.send_signal(signal.SIGTERM)
                        try:
                            proc.wait(timeout=3)  # Ждем завершения
                        except psutil.TimeoutExpired:
                            proc.send_signal(signal.SIGKILL)  # Принудительное завершение
                            
                        killed_count += 1
                        logger.info(f"Процесс с PID {proc.pid} завершен")
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        logger.warning(f"Не удалось завершить процесс с PID {proc.pid}")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    # Даем время на завершение процессов
    if killed_count > 0:
        logger.info(f"Завершено {killed_count} процессов бота. Ожидание 5 секунд...")
        time.sleep(5)
    else:
        logger.info("Процессы бота не найдены")


def reset_telegram_api_session():
    """
    Полный сброс сессии Telegram API
    """
    logger.info("Начинаем полный сброс сессии Telegram API...")
    
    # 1. Удаляем веб-хук
    webhook_url = f"https://api.telegram.org/bot{TOKEN}/deleteWebhook"
    try:
        response = requests.get(webhook_url)
        result = response.json()
        logger.info(f"Результат удаления вебхука: {json.dumps(result)}")
    except Exception as e:
        logger.error(f"Ошибка при удалении вебхука: {e}")
    
    # 2. Получаем последние обновления, чтобы узнать текущий offset
    getUpdates_url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    try:
        response = requests.get(getUpdates_url)
        result = response.json()
        logger.info(f"Результат getUpdates: {json.dumps(result)}")
        
        # 3. Если есть обновления, сбрасываем очередь
        if result.get('ok') and result.get('result'):
            updates = result['result']
            if updates:
                # Получаем последний update_id и увеличиваем на 1
                last_update_id = max(update['update_id'] for update in updates)
                next_offset = last_update_id + 1
                
                # Сбрасываем все обновления
                logger.info(f"Сбрасываем очередь обновлений с offset={next_offset}")
                reset_url = f"{getUpdates_url}?offset={next_offset}"
                response = requests.get(reset_url)
                result = response.json()
                logger.info(f"Результат сброса очереди: {json.dumps(result)}")
    except Exception as e:
        logger.error(f"Ошибка при сбросе очереди обновлений: {e}")
    
    # 4. Дополнительная очистка: делаем несколько вызовов с разными offset для надежности
    for offset in range(1, 5):
        try:
            reset_url = f"{getUpdates_url}?offset={offset}"
            response = requests.get(reset_url)
            result = response.json()
            logger.info(f"Дополнительный сброс с offset={offset}: {json.dumps(result)}")
        except Exception as e:
            logger.error(f"Ошибка при дополнительном сбросе: {e}")
    
    # 5. Ожидаем, чтобы сервер Telegram обработал все изменения
    logger.info("Ожидаем 15 секунд для полной очистки сессии Telegram API...")
    time.sleep(15)


def start_fresh_bot():
    """
    Запускает новый экземпляр бота
    """
    logger.info("Запускаем чистый экземпляр бота...")
    
    try:
        bot_process = subprocess.Popen(
            ["python", "run_one_bot.py"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE
        )
        logger.info(f"Бот запущен с PID: {bot_process.pid}")
        
        # Ожидаем немного, чтобы убедиться, что процесс стартовал
        time.sleep(2)
        
        if bot_process.poll() is not None:
            # Процесс уже завершился - что-то пошло не так
            stdout, stderr = bot_process.communicate()
            logger.error(f"Бот завершился сразу после запуска со статусом {bot_process.returncode}")
            logger.error(f"STDOUT: {stdout.decode()}")
            logger.error(f"STDERR: {stderr.decode()}")
            return False
        
        return True
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        return False


def main():
    """
    Основная функция для очистки и перезапуска бота
    """
    logger.info("Начинаем полную очистку сессий Telegram API и перезапуск бота...")
    
    # Шаг 1: Остановить все запущенные экземпляры бота
    find_and_kill_all_bot_processes()
    
    # Шаг 2: Сбросить сессию Telegram API
    reset_telegram_api_session()
    
    # Шаг 3: Запустить новый экземпляр бота
    if start_fresh_bot():
        logger.info("Бот успешно перезапущен с чистой сессией!")
    else:
        logger.error("Не удалось запустить бота после очистки сессии")


if __name__ == "__main__":
    main()