#!/usr/bin/env python3
"""
Скрипт для запуска Telegram бота в режиме webhook.
Адаптирован для работы с Flask-приложением и регистрации webhook в Telegram API.
"""

import os
import sys
import logging
import time
import signal
import subprocess
import requests
import json

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Файл для проверки здоровья бота
HEALTH_FILE = "bot_health.txt"

def update_health_check():
    """Обновляет файл проверки здоровья текущим временем."""
    try:
        import datetime
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(HEALTH_FILE, "w") as f:
            f.write(now)
        logging.info(f"Файл здоровья обновлен: {now}")
    except Exception as e:
        logging.error(f"Ошибка при обновлении файла здоровья: {e}")

# Основная функция запуска бота
def main():
    """Запускает Telegram бота в режиме webhook."""
    
    # Убиваем только конфликтующие процессы бота, сохраняя Flask-приложение
    try:
        logging.info("Останавливаем конфликтующие процессы бота...")
        # НЕ останавливаем main.py, так как это Flask-приложение, которое должно работать параллельно
        os.system("pkill -f 'python.*bot_modified.py'")
        os.system("pkill -f 'python.*run_telegram_bot.py'")
        time.sleep(2)  # Даем процессам время завершиться
    except Exception as e:
        logging.error(f"Ошибка при остановке процессов: {e}")
    
    try:
        # Импортируем необходимые модули
        from config import TELEGRAM_TOKEN
        from webhook_handler import setup_webhook
        
        # Настраиваем обработчик сигналов для корректного завершения
        def signal_handler(sig, frame):
            logging.info("Получен сигнал остановки. Завершаем работу...")
            # Удаляем webhook перед выходом
            try:
                delete_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteWebhook"
                requests.post(delete_url)
                logging.info("Webhook удален.")
            except Exception as e:
                logging.error(f"Ошибка при удалении webhook: {e}")
            
            logging.info("Бот остановлен.")
            sys.exit(0)
        
        # Регистрируем обработчики сигналов
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Получаем домен Replit
        replit_domain = os.environ.get('REPLIT_DOMAINS', '').split(',')[0]
        if not replit_domain:
            # Fallback к старому формату
            replit_domain = f"{os.environ.get('REPL_SLUG')}.{os.environ.get('REPL_OWNER')}.repl.co"
        logging.info(f"Использую домен для webhook: {replit_domain}")
        
        # Настраиваем webhook
        setup_result = setup_webhook(replit_domain)
        if setup_result:
            logging.info("Webhook успешно настроен")
        else:
            logging.error("Не удалось настроить webhook")
            return 1
            
        # В режиме webhook бот работает через Flask и не требует дополнительного процесса
        # Вместо этого, мы просто обновляем файл здоровья и ждем
        logging.info("Бот запущен в режиме webhook. Мониторим состояние...")
        
        # Основной цикл обновления файла здоровья
        while True:
            update_health_check()
            
            # Проверяем, что webhook по-прежнему настроен
            try:
                check_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getWebhookInfo"
                response = requests.get(check_url)
                if response.status_code == 200:
                    webhook_info = response.json()
                    if not webhook_info.get("result", {}).get("url"):
                        logging.error("Webhook не настроен! Переустанавливаем...")
                        setup_webhook(replit_domain)
            except Exception as e:
                logging.error(f"Ошибка при проверке состояния webhook: {e}")
            
            # Ждем 60 секунд перед следующей проверкой
            time.sleep(60)
        
    except Exception as e:
        logging.error(f"Ошибка при запуске бота: {e}")
        logging.error(f"Трассировка: {sys.exc_info()[2]}")
        return 1
    
    return 0

if __name__ == "__main__":
    # Запускаем основную функцию
    sys.exit(main())