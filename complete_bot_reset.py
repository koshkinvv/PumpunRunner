#!/usr/bin/env python
"""
Скрипт для полного сброса всех процессов бота и инициализации нового экземпляра.
Этот скрипт намного более агрессивно завершает процессы и сбрасывает сессии.
"""

import os
import sys
import time
import signal
import subprocess
import logging
import psutil
import requests
import json

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/bot_reset.log")
    ]
)

logger = logging.getLogger('bot_reset')

def kill_all_python_processes():
    """
    Завершает все Python процессы, кроме текущего.
    Это очень радикальный подход - используйте с осторожностью.
    """
    logger.info("Завершение ВСЕХ процессов Python...")
    
    current_pid = os.getpid()
    killed_count = 0
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # Ищем Python процессы
            is_python = False
            
            # Проверяем имя процесса
            if proc.info['name'] and ('python' in proc.info['name'].lower()):
                is_python = True
            
            # Проверяем командную строку
            cmdline = ' '.join(proc.info['cmdline'] or [])
            if 'python' in cmdline.lower():
                is_python = True
            
            # Если это Python процесс и не текущий, завершаем его
            if is_python and proc.info['pid'] != current_pid:
                cmd = ' '.join(proc.info['cmdline'] or [])[:50]
                logger.info(f"Завершение Python процесса: PID {proc.info['pid']}, CMD: {cmd}...")
                
                try:
                    # Сначала пробуем мягкое завершение
                    os.kill(proc.info['pid'], signal.SIGTERM)
                    time.sleep(1)
                    
                    # Если процесс все еще работает, используем SIGKILL
                    if psutil.pid_exists(proc.info['pid']):
                        logger.info(f"SIGTERM не помог для PID {proc.info['pid']}, используем SIGKILL")
                        os.kill(proc.info['pid'], signal.SIGKILL)
                    
                    killed_count += 1
                except Exception as e:
                    logger.error(f"Ошибка при завершении процесса {proc.info['pid']}: {e}")
        except Exception as e:
            logger.error(f"Ошибка при получении информации о процессе: {e}")
    
    logger.info(f"Завершено {killed_count} Python процессов")
    
    # Даем время на завершение процессов
    time.sleep(5)

def reset_telegram_api():
    """
    Полный сброс Telegram API сессии.
    """
    logger.info("Сброс Telegram API сессии...")
    
    token = os.environ.get('TELEGRAM_TOKEN')
    
    if not token:
        logger.error("TELEGRAM_TOKEN не найден в переменных окружения!")
        return
    
    # 1. Удаляем вебхук
    try:
        webhook_url = f"https://api.telegram.org/bot{token}/deleteWebhook?drop_pending_updates=true"
        response = requests.get(webhook_url, timeout=10)
        logger.info(f"Удаление вебхука: {response.text}")
    except Exception as e:
        logger.error(f"Ошибка при удалении вебхука: {e}")
    
    # 2. Получаем offset последнего обновления
    try:
        updates_url = f"https://api.telegram.org/bot{token}/getUpdates?limit=1"
        response = requests.get(updates_url, timeout=10)
        data = response.json()
        
        # Если есть обновления, получаем последний offset и сбрасываем его
        if data.get('ok') and data.get('result'):
            last_update = data['result'][0]
            offset = last_update['update_id'] + 1
            
            logger.info(f"Сброс очереди с offset={offset}")
            reset_url = f"https://api.telegram.org/bot{token}/getUpdates?offset={offset}"
            requests.get(reset_url, timeout=10)
    except Exception as e:
        logger.error(f"Ошибка при сбросе очереди обновлений: {e}")
    
    # 3. Попытки сброса с разными offset
    for i in range(1, 10):
        try:
            reset_url = f"https://api.telegram.org/bot{token}/getUpdates?offset={i}&limit=1"
            response = requests.get(reset_url, timeout=5)
            logger.info(f"Сброс с offset={i}: {response.status_code}")
            time.sleep(1)
        except:
            pass
    
    logger.info("Ожидание 10 секунд после сброса API...")
    time.sleep(10)

def start_fresh_bot():
    """
    Запускает новый экземпляр бота через стандартные скрипты.
    """
    logger.info("Запуск нового экземпляра бота...")
    
    try:
        subprocess.run(["python", "run_one_bot.py"], check=True)
        logger.info("Команда запуска бота успешно выполнена")
    except subprocess.CalledProcessError as e:
        logger.error(f"Ошибка при запуске бота: {e}")

def main():
    """
    Основная функция для полного сброса и запуска бота.
    """
    logger.info("=" * 50)
    logger.info("ПОЛНЫЙ СБРОС И ПЕРЕЗАПУСК БОТА")
    logger.info("=" * 50)
    
    # 1. Завершаем все Python процессы
    kill_all_python_processes()
    
    # 2. Сбрасываем Telegram API
    reset_telegram_api()
    
    # 3. Запускаем новый экземпляр бота
    start_fresh_bot()
    
    logger.info("Процесс полного сброса и перезапуска бота завершен")

if __name__ == "__main__":
    main()