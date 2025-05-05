#!/usr/bin/env python
"""
Скрипт для полной очистки и запуска бота с нуля.
В отличие от других скриптов:
1. Не использует промежуточные процессы запуска
2. Максимально тщательно очищает Telegram API сессию
3. Использует прямое подключение к API в режиме long polling

Этот скрипт должен решить проблему ошибки:
"Conflict: terminated by other getUpdates request; make sure that only one bot instance is running"
"""

import os
import sys
import time
import signal
import logging
import requests
import json
import psutil
import atexit
import telegram
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from telegram.ext import ConversationHandler

# Импортируем необходимые модули для бота
from bot_modified import setup_bot

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/clean_start.log")
    ]
)

logger = logging.getLogger('clean_start')

def kill_all_bot_processes():
    """
    Завершает все процессы Python, связанные с ботом.
    """
    current_pid = os.getpid()
    killed_processes = []
    
    logger.info(f"Текущий PID: {current_pid}, поиск других процессов бота...")
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['pid'] == current_pid:
                continue
                
            if proc.info['name'] and 'python' in proc.info['name'].lower():
                cmdline = proc.info.get('cmdline', [])
                cmd_str = ' '.join(cmdline) if cmdline else ''
                
                # Проверяем, связан ли процесс с ботом
                if any(x in cmd_str for x in ['bot_', 'bot.py', 'deploy_bot', 'main.py', 'run_', 'start_']):
                    logger.info(f"Завершение процесса бота: PID {proc.info['pid']}, CMD: {cmd_str[:50]}...")
                    try:
                        os.kill(proc.info['pid'], signal.SIGKILL)
                        killed_processes.append(proc.info['pid'])
                    except Exception as e:
                        logger.error(f"Ошибка при завершении процесса {proc.info['pid']}: {e}")
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
            
    logger.info(f"Завершено {len(killed_processes)} процессов бота")
    if killed_processes:
        # Даем время на завершение процессов
        time.sleep(3)
        
    return killed_processes

def reset_telegram_session():
    """
    Максимально тщательно сбрасывает сессию Telegram API.
    """
    token = os.environ.get('TELEGRAM_TOKEN')
    if not token:
        logger.error("TELEGRAM_TOKEN не найден в переменных окружения!")
        return False
        
    logger.info("Начинаем полный сброс сессии Telegram API...")
    
    # 1. Удаляем вебхук и все ожидающие обновления
    try:
        deletewebhook_url = f"https://api.telegram.org/bot{token}/deleteWebhook?drop_pending_updates=true"
        response = requests.get(deletewebhook_url, timeout=10)
        logger.info(f"Удаление вебхука: {response.text}")
    except Exception as e:
        logger.error(f"Ошибка при удалении вебхука: {e}")
    
    # 2. Сбрасываем очередь обновлений с разными смещениями
    max_attempts = 10  # Увеличиваем количество попыток
    success_counter = 0
    
    for attempt in range(1, max_attempts + 1):
        try:
            # Используем увеличивающийся offset для полного сброса
            offset = attempt * 10  # Больший шаг для охвата всех сообщений
            url = f"https://api.telegram.org/bot{token}/getUpdates?offset={offset}&limit=100&timeout=1"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = json.loads(response.text)
                if data.get("ok", False):
                    success_counter += 1
                    logger.info(f"Попытка {attempt}: успешно, offset={offset}")
                    
                    # Если 3 попытки подряд успешны, можно прекратить
                    if success_counter >= 3:
                        logger.info("Достигнуто 3 успешных попытки подряд, сброс завершен")
                        break
                else:
                    logger.warning(f"Попытка {attempt}: ошибка API - {data.get('description', 'неизвестная ошибка')}")
                    success_counter = 0  # Сбрасываем счетчик успешных попыток
            else:
                logger.warning(f"Попытка {attempt}: HTTP ошибка {response.status_code}")
                success_counter = 0
        except Exception as e:
            logger.error(f"Исключение при сбросе (попытка {attempt}): {e}")
            success_counter = 0
        
        # Увеличенная пауза между запросами
        time.sleep(3)
    
    # 3. Финальный сброс с нулевым смещением
    try:
        url = f"https://api.telegram.org/bot{token}/getUpdates?offset=0&limit=100&timeout=1"
        response = requests.get(url, timeout=5)
        logger.info(f"Финальный сброс (offset=0): {response.status_code}")
    except Exception as e:
        logger.error(f"Ошибка при финальном сбросе: {e}")
    
    # Даем API время полностью обработать наши запросы
    logger.info("Ожидание 15 секунд для полного сброса API сессии...")
    time.sleep(15)
    
    return True

def start_bot():
    """
    Запускает бота напрямую, без промежуточных скриптов.
    """
    logger.info("Запуск бота напрямую...")
    
    token = os.environ.get('TELEGRAM_TOKEN')
    if not token:
        logger.error("TELEGRAM_TOKEN не найден в переменных окружения!")
        return False
    
    try:
        # Получаем настроенное приложение бота
        application = setup_bot()
        
        logger.info("Бот настроен, запуск в режиме polling...")
        
        # Запускаем бота и блокируем выполнение до завершения
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=telegram.Update.ALL_TYPES,
            pool_timeout=30,
            read_timeout=30,
            connect_timeout=30,
            write_timeout=30
        )
        
        return True
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        return False

def cleanup_on_exit():
    """
    Функция очистки при выходе из скрипта.
    """
    logger.info("Выход из скрипта, выполняем очистку...")

def main():
    """
    Основная функция для полного сброса и запуска бота.
    """
    logger.info("=" * 60)
    logger.info("ЗАПУСК БОТА С НУЛЯ (ПОЛНАЯ ОЧИСТКА)")
    logger.info("=" * 60)
    
    # Регистрируем функцию очистки при выходе
    atexit.register(cleanup_on_exit)
    
    # 1. Завершаем все связанные процессы
    kill_all_bot_processes()
    
    # 2. Сбрасываем сессию Telegram API
    if not reset_telegram_session():
        logger.error("Ошибка при сбросе сессии Telegram API")
        return
    
    # 3. Запускаем бота напрямую
    logger.info("Все подготовительные шаги выполнены, запускаем бота...")
    success = start_bot()
    
    if success:
        logger.info("Бот успешно запущен и работает!")
    else:
        logger.error("Не удалось запустить бота")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Получен сигнал прерывания, завершение работы...")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        sys.exit(1)