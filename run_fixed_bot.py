#!/usr/bin/env python
"""
Запускает бота с исправленной обработкой обновления профиля.

Этот скрипт обеспечивает:
1. Корректное завершение других запущенных экземпляров бота
2. Полный сброс сессии Telegram API для предотвращения конфликтов
3. Запуск единственного экземпляра бота с исправленной функциональностью
"""
import logging
import os
import subprocess
import sys
import time
import signal
import requests
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters
import psutil

# Настраиваем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Получаем токен бота
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    logger.error("TELEGRAM_TOKEN не найден в переменных окружения.")
    sys.exit(1)

def find_and_kill_all_bot_processes():
    """
    Находит и завершает все запущенные процессы бота
    """
    try:
        current_pid = os.getpid()
        logger.info(f"Текущий PID: {current_pid}")
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # Пропускаем текущий процесс
                if proc.pid == current_pid:
                    continue
                    
                # Проверяем командную строку процесса
                if proc.info['cmdline']:
                    cmdline = ' '.join(proc.info['cmdline'])
                    if 'python' in cmdline and ('bot.py' in cmdline or 'bot_modified.py' in cmdline or 'run_' in cmdline):
                        logger.info(f"Завершение процесса бота: {proc.pid}, {cmdline}")
                        os.kill(proc.pid, signal.SIGTERM)
                        time.sleep(0.5)  # Даем процессу время завершиться
                        
                        # Проверка, завершился ли процесс
                        if psutil.pid_exists(proc.pid):
                            logger.warning(f"Процесс {proc.pid} не завершился по SIGTERM, отправляем SIGKILL")
                            os.kill(proc.pid, signal.SIGKILL)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
                
        logger.info("Все процессы бота завершены")
    except Exception as e:
        logger.error(f"Ошибка при поиске и завершении процессов бота: {e}")

def reset_telegram_api_session():
    """
    Полный сброс сессии Telegram API
    """
    try:
        # Удаляем webhook если он установлен
        requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteWebhook")
        
        # Получаем текущие обновления с максимальным значением offset
        # Это позволяет отметить все текущие обновления как обработанные
        logger.info("Сброс очереди обновлений Telegram API...")
        response = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset=-1&limit=1")
        data = response.json()
        
        if data.get('ok') and data.get('result'):
            # Если есть обновления, получаем последний update_id и увеличиваем его на 1
            last_update_id = data['result'][0]['update_id']
            next_update_id = last_update_id + 1
            
            # Вызываем getUpdates с новым offset, чтобы сбросить все старые обновления
            requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={next_update_id}")
            logger.info(f"API сессия сброшена, последний update_id: {last_update_id}")
        else:
            # Если обновлений нет, просто вызываем getUpdates с offset=0
            requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset=0")
            logger.info("API сессия сброшена, обновлений не было")
            
        # Ждем небольшую паузу для стабилизации
        time.sleep(1)
    except Exception as e:
        logger.error(f"Ошибка при сбросе API сессии: {e}")

def start_bot():
    """
    Запускает бота с исправленной функциональностью
    """
    try:
        logger.info("Подготовка к запуску бота...")
        
        # Импортируем функцию настройки бота из bot_modified.py
        from bot_modified import setup_bot
        
        # Создаем и запускаем приложение бота
        logger.info("Настройка бота...")
        application = setup_bot()
        
        # Запускаем бота
        logger.info("Запуск бота...")
        application.run_polling(allowed_updates=["message", "callback_query", "edited_message"])
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        raise

def main():
    """
    Основная функция полного сброса и запуска бота
    """
    try:
        # Завершаем все запущенные экземпляры бота
        logger.info("Завершение запущенных экземпляров бота...")
        find_and_kill_all_bot_processes()
        
        # Сбрасываем сессию Telegram API
        logger.info("Сброс сессии Telegram API...")
        reset_telegram_api_session()
        
        # Запускаем бот
        logger.info("Подготовка к запуску бота...")
        start_bot()
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске бота: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Обрабатываем прерывание Ctrl+C
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Получен сигнал прерывания, завершение работы...")
        sys.exit(0)