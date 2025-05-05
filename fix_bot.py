#!/usr/bin/env python
"""
Скрипт для полного сброса конфликтующих процессов бота и запуска единственного экземпляра.
Более агрессивная версия очистки сессии Telegram API.
"""

import os
import sys
import time
import logging
import subprocess
import requests
import json
import psutil
import signal

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/fix_bot.log")
    ]
)

logger = logging.getLogger('fix_bot')

def kill_all_python_processes():
    """
    Завершает все процессы Python, связанные с ботом.
    """
    logger.info("Завершение всех процессов Python для бота...")
    current_pid = os.getpid()
    
    killed_count = 0
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # Пропускаем текущий процесс
            if proc.info['pid'] == current_pid:
                continue
                
            # Проверяем только процессы Python
            if proc.info['name'] and 'python' in proc.info['name'].lower():
                cmdline = proc.info.get('cmdline', [])
                cmd_str = ' '.join(cmdline) if cmdline else ''
                
                # Завершаем процессы, связанные с ботом
                if any(x in cmd_str for x in ['bot_', 'bot.py', 'deploy_bot', 'main.py', 'run_', 'start_']):
                    logger.info(f"Завершение процесса: PID {proc.info['pid']}, CMD: {cmd_str[:50]}...")
                    try:
                        os.kill(proc.info['pid'], signal.SIGKILL)
                        killed_count += 1
                    except Exception as e:
                        logger.error(f"Ошибка при завершении процесса {proc.info['pid']}: {e}")
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
    logger.info(f"Завершено {killed_count} процессов, связанных с ботом")
    # Даем время на завершение процессов
    time.sleep(3)

def reset_telegram_api():
    """
    Полный сброс Telegram API сессии.
    """
    logger.info("Запуск сброса Telegram API сессии...")
    
    token = os.environ.get('TELEGRAM_TOKEN')
    if not token:
        logger.error("TELEGRAM_TOKEN не найден в переменных окружения!")
        return False
    
    # 1. Проверяем и удаляем вебхук
    try:
        webhookinfo_url = f"https://api.telegram.org/bot{token}/getWebhookInfo"
        response = requests.get(webhookinfo_url)
        logger.info(f"Webhook info: {response.text}")
        
        deletewebhook_url = f"https://api.telegram.org/bot{token}/deleteWebhook?drop_pending_updates=true"
        response = requests.get(deletewebhook_url)
        logger.info(f"Delete webhook result: {response.text}")
    except Exception as e:
        logger.error(f"Ошибка при сбросе вебхука: {e}")
    
    # 2. Сбрасываем очередь сообщений с несколькими попытками
    for attempt in range(1, 6):
        try:
            # Каждый раз увеличиваем смещение, чтобы точно сбросить все
            url = f"https://api.telegram.org/bot{token}/getUpdates?offset={attempt}&limit=100"
            response = requests.get(url)
            logger.info(f"Reset attempt {attempt}: {response.text}")
            
            # Если сброс был успешным, можно выйти из цикла раньше
            if response.status_code == 200 and json.loads(response.text).get("ok", False):
                data = json.loads(response.text)
                if len(data.get("result", [])) == 0:
                    if attempt >= 2:  # Минимум две успешные попытки для уверенности
                        logger.info(f"Успешный сброс после {attempt} попыток")
                        break
            
            # Пауза между запросами
            time.sleep(5)
        except Exception as e:
            logger.error(f"Ошибка при сбросе очереди (попытка {attempt}): {e}")
    
    # Дополнительное ожидание для полного сброса всех сессий
    logger.info("Ожидание 10 секунд после сброса сессии Telegram API...")
    time.sleep(10)
    return True

def start_direct_bot():
    """
    Запускает бота напрямую через упрощенный скрипт.
    """
    logger.info("Запуск бота напрямую через direct_start.py...")
    
    try:
        # Запускаем процесс в фоновом режиме и не ждем его завершения
        process = subprocess.Popen(
            ["python", "direct_start.py"],
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            start_new_session=True
        )
        
        # Ждем немного, чтобы увидеть, запустился ли процесс успешно
        time.sleep(2)
        
        if process.poll() is None:  # Процесс все еще работает
            logger.info(f"Бот успешно запущен, PID: {process.pid}")
            return True
        else:
            # Процесс завершился слишком быстро - это ошибка
            stdout, stderr = process.communicate()
            logger.error(f"Ошибка при запуске бота: код {process.returncode}")
            logger.error(f"STDOUT: {stdout.decode('utf-8', errors='replace')}")
            logger.error(f"STDERR: {stderr.decode('utf-8', errors='replace')}")
            return False
    except Exception as e:
        logger.error(f"Исключение при запуске бота: {e}")
        return False

def main():
    """
    Основная функция для полного сброса и запуска бота.
    """
    logger.info("=" * 50)
    logger.info("ИСПРАВЛЕНИЕ БОТА: СБРОС И ПРЯМОЙ ПЕРЕЗАПУСК")
    logger.info("=" * 50)
    
    # 1. Завершение всех процессов бота
    kill_all_python_processes()
    
    # 2. Полный сброс сессии API
    if not reset_telegram_api():
        logger.error("Не удалось сбросить сессию API - отмена запуска")
        return
    
    # 3. Прямой запуск бота
    if start_direct_bot():
        logger.info("Бот успешно сброшен и перезапущен напрямую")
    else:
        logger.error("Не удалось перезапустить бота напрямую")

if __name__ == "__main__":
    main()