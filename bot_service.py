#!/usr/bin/env python
"""
Сервисный скрипт для постоянной работы бота.
Этот скрипт автоматически перезапускает бота при его падении.
"""

import os
import sys
import time
import logging
import subprocess
import signal
import requests
import json
import atexit

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/bot_service.log")
    ]
)

logger = logging.getLogger('bot_service')

def reset_telegram_api():
    """Простой сброс API Telegram"""
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        logger.error("TELEGRAM_TOKEN отсутствует!")
        return False
        
    try:
        # 1. Удаляем вебхук и сбрасываем ожидающие обновления
        url = f"https://api.telegram.org/bot{token}/deleteWebhook?drop_pending_updates=true"
        response = requests.get(url, timeout=10)
        logger.info(f"Webhook delete: {response.text}")
        
        # 2. Сбрасываем очередь обновлений
        url = f"https://api.telegram.org/bot{token}/getUpdates?offset=1"
        response = requests.get(url, timeout=10)
        logger.info(f"Reset queue: {response.status_code}")
        
        return True
    except Exception as e:
        logger.error(f"Ошибка при сбросе API: {e}")
        return False

def cleanup():
    """Функция очистки при выходе"""
    logger.info("Выход из сервиса бота, очистка...")

def start_bot_process():
    """Запускает процесс бота и возвращает его"""
    try:
        # Запускаем бота как отдельный процесс
        process = subprocess.Popen(
            ["python", "-c", 
             "from bot_modified import setup_bot; app = setup_bot(); app.run_polling(drop_pending_updates=True)"],
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            start_new_session=True,
            bufsize=1,
            universal_newlines=True
        )
        
        logger.info(f"Бот запущен с PID {process.pid}")
        return process
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        return None

def monitor_and_restart():
    """Мониторит бота и перезапускает его при необходимости"""
    # Регистрируем функцию очистки
    atexit.register(cleanup)
    
    # Первичный сброс API
    logger.info("Начальный сброс API...")
    reset_telegram_api()
    time.sleep(3)  # Даем время на полный сброс

    max_restarts = 5
    restart_count = 0
    
    while restart_count < max_restarts:
        logger.info(f"Запуск бота (попытка {restart_count + 1}/{max_restarts})...")
        
        # Запускаем бота
        bot_process = start_bot_process()
        if not bot_process:
            logger.error("Не удалось запустить бота!")
            time.sleep(10)
            restart_count += 1
            continue
        
        # Проверяем, что процесс запущен успешно
        time.sleep(3)
        if bot_process.poll() is not None:
            # Процесс уже завершился
            stdout, stderr = bot_process.communicate()
            logger.error(f"Бот завершился сразу после запуска! Код: {bot_process.returncode}")
            logger.error(f"STDOUT: {stdout}")
            logger.error(f"STDERR: {stderr}")
            
            # Сбрасываем API перед следующей попыткой
            reset_telegram_api()
            time.sleep(5)
            restart_count += 1
            continue
        
        # Мониторим процесс
        logger.info(f"Бот работает с PID {bot_process.pid}. Мониторинг...")
        
        # Ожидаем завершения процесса или проверяем его здоровье
        while bot_process.poll() is None:
            # Процесс работает, ждем
            time.sleep(30)
            
            # Здесь можно добавить проверку здоровья, если нужно
            logger.info(f"Бот все еще работает (PID {bot_process.pid})")
        
        # Процесс завершился, проверяем коды ошибок
        exit_code = bot_process.returncode
        stdout, stderr = bot_process.communicate()
        
        logger.error(f"Бот завершился с кодом {exit_code}")
        logger.error(f"STDOUT: {stdout}")
        logger.error(f"STDERR: {stderr}")
        
        # Сбрасываем API перед перезапуском
        reset_telegram_api()
        time.sleep(5)
        restart_count += 1
    
    logger.error(f"Достигнуто максимальное количество перезапусков ({max_restarts}). Завершение.")

if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("ЗАПУСК СЕРВИСА БОТА")
    logger.info("=" * 50)
    
    try:
        monitor_and_restart()
    except KeyboardInterrupt:
        logger.info("Получен сигнал прерывания. Завершение...")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        logger.exception("Подробная информация об ошибке:")