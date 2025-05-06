#!/usr/bin/env python
"""
Специальный скрипт для запуска бота в продакшн режиме через Replit Deployments.
Этот скрипт создан с учетом особенностей среды Replit Deployments.

Основные преимущества:
1. Максимально агрессивная очистка сессий Telegram API
2. Надежное завершение всех конфликтующих процессов
3. Расширенное логирование и мониторинг
4. Автоматические перезапуски бота в случае сбоев
"""

import os
import sys
import time
import signal
import logging
import subprocess
import json
import requests
import psutil
from datetime import datetime

# Настройка логирования
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = f"{log_dir}/production_{timestamp}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file)
    ]
)

logger = logging.getLogger('production_bot')

def kill_all_python_processes():
    """
    Завершает все Python процессы, кроме текущего.
    """
    current_pid = os.getpid()
    terminated_count = 0
    
    logger.info(f"Текущий PID: {current_pid}")
    logger.info("Поиск и завершение всех Python процессов, кроме текущего...")
    
    try:
        # Сначала попробуем через psutil для большей точности
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['pid'] != current_pid:
                    # Проверяем, что это Python процесс, связанный с ботом
                    cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                    if 'python' in cmdline.lower() and any(x in cmdline.lower() for x in ['bot', 'telegram', 'main.py']):
                        logger.info(f"Завершение процесса {proc.info['pid']}: {cmdline}")
                        try:
                            # Сначала пробуем SIGTERM
                            os.kill(proc.info['pid'], signal.SIGTERM)
                            terminated_count += 1
                            time.sleep(2)
                            
                            # Если процесс все еще работает, используем SIGKILL
                            if psutil.pid_exists(proc.info['pid']):
                                os.kill(proc.info['pid'], signal.SIGKILL)
                        except Exception as kill_err:
                            logger.error(f"Ошибка при завершении процесса {proc.info['pid']}: {kill_err}")
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as err:
                continue
    except Exception as e:
        logger.error(f"Ошибка при поиске процессов через psutil: {e}")
    
    # Дополнительно используем более агрессивный системный подход
    try:
        os.system("pkill -9 -f 'python.*bot'")
        os.system("pkill -9 -f 'python.*main.py'")
        os.system("pkill -9 -f 'python.*telegram'")
    except Exception as e:
        logger.error(f"Ошибка при завершении процессов через pkill: {e}")
    
    logger.info(f"Завершено {terminated_count} Python процессов")
    
    # Даем время на завершение всех процессов
    time.sleep(5)
    
    return terminated_count

def reset_telegram_api_session():
    """
    Максимально тщательный сброс сессии Telegram API
    """
    token = os.environ.get('TELEGRAM_TOKEN')
    if not token:
        logger.error("TELEGRAM_TOKEN не найден в переменных окружения!")
        return False
    
    logger.info("Начинаем сброс сессии Telegram API...")
    
    # Проверяем статус вебхука
    try:
        webhook_response = requests.get(f"https://api.telegram.org/bot{token}/getWebhookInfo")
        logger.info(f"Информация о вебхуке: {webhook_response.text}")
    except Exception as e:
        logger.error(f"Ошибка при проверке вебхука: {e}")
    
    # Удаляем вебхук
    try:
        delete_response = requests.get(f"https://api.telegram.org/bot{token}/deleteWebhook?drop_pending_updates=true")
        logger.info(f"Удаление вебхука: {delete_response.text}")
    except Exception as e:
        logger.error(f"Ошибка при удалении вебхука: {e}")
    
    # Делаем несколько попыток сброса очереди обновлений
    success = False
    for attempt in range(1, 11):
        try:
            # Разные стратегии сброса для повышения вероятности успеха
            if attempt % 3 == 0:
                # Стратегия 1: простой запрос с offset -1
                url = f"https://api.telegram.org/bot{token}/getUpdates?offset=-1"
            elif attempt % 3 == 1:
                # Стратегия 2: запрос с большим положительным offset
                url = f"https://api.telegram.org/bot{token}/getUpdates?offset=100&limit=1"
            else:
                # Стратегия 3: запрос с указанием timeout
                url = f"https://api.telegram.org/bot{token}/getUpdates?timeout={attempt}&offset=1"
            
            reset_response = requests.get(url, timeout=20)
            status = reset_response.status_code
            
            try:
                response_json = reset_response.json()
                logger.info(f"Попытка сброса #{attempt}: Код {status}, Ответ: {json.dumps(response_json)}")
                
                if response_json.get("ok", False):
                    success = True
                    if attempt >= 5:  # После 5 успешных попыток можно остановиться
                        logger.info("Достаточно успешных сбросов, прерываем цикл")
                        break
            except Exception as json_err:
                logger.error(f"Ошибка при разборе JSON: {json_err}")
                logger.info(f"Попытка сброса #{attempt}: Код {status}, Ответ: {reset_response.text}")
            
            # Увеличиваем интервал между запросами
            time.sleep(3 + attempt)
        except Exception as e:
            logger.error(f"Ошибка при сбросе (попытка #{attempt}): {e}")
            time.sleep(5)
    
    if success:
        logger.info("Сессия Telegram API успешно сброшена")
    else:
        logger.warning("Не удалось полностью сбросить сессию Telegram API!")
    
    # Даем API дополнительное время на полный сброс сессии
    time.sleep(15)
    
    return success

def run_bot():
    """
    Запускает бота и отслеживает его работу
    """
    try:
        # Получаем настроенное приложение из bot_modified.py
        from bot_modified import setup_bot
        
        # Настраиваем и запускаем бота в режиме polling
        logger.info("Настройка приложения бота...")
        application = setup_bot()
        
        logger.info("Запуск бота в режиме polling...")
        application.run_polling(drop_pending_updates=True)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        return False

def main():
    """
    Основная функция для запуска бота в продакшн режиме
    """
    logger.info("=" * 60)
    logger.info("ЗАПУСК БОТА В ПРОДАКШН РЕЖИМЕ (REPLIT DEPLOYMENTS)")
    logger.info("=" * 60)
    
    # Проверяем наличие токена
    if not os.environ.get('TELEGRAM_TOKEN'):
        logger.error("TELEGRAM_TOKEN не найден в переменных окружения! Бот не может быть запущен.")
        sys.exit(1)
    
    # Убиваем все запущенные процессы Python
    kill_all_python_processes()
    
    # Сбрасываем сессию API
    reset_telegram_api_session()
    
    # Удаляем лок-файлы, если они есть
    lock_files = ['./uv.lock', './bot.lock', './telegram.lock', './instance.lock', './bot_lock.pid']
    for lock_file in lock_files:
        try:
            if os.path.exists(lock_file):
                os.remove(lock_file)
                logger.info(f"Удален лок-файл: {lock_file}")
        except Exception as e:
            logger.error(f"Ошибка при удалении лок-файла {lock_file}: {e}")
    
    # Максимальное количество попыток перезапуска
    max_restarts = 10
    restart_count = 0
    
    while restart_count < max_restarts:
        restart_count += 1
        logger.info(f"Запуск бота (попытка {restart_count}/{max_restarts})...")
        
        try:
            # Запускаем бота
            if run_bot():
                break
            else:
                logger.error(f"Запуск бота завершился с ошибкой. Перезапуск через 30 секунд...")
                time.sleep(30)
        except Exception as e:
            logger.error(f"Критическая ошибка при запуске бота: {e}")
            time.sleep(30)
    
    if restart_count >= max_restarts:
        logger.critical(f"Достигнуто максимальное количество попыток перезапуска ({max_restarts}). Завершение работы.")
        sys.exit(1)

if __name__ == "__main__":
    main()