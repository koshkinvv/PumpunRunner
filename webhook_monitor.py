#!/usr/bin/env python3
"""
Скрипт для поддержки и мониторинга webhook для Telegram бота.
Этот скрипт запускается через workflow bot_runner.
"""

import logging
import os
import sys
import time
import requests
import datetime
import signal

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Константы
HEALTH_FILE = "bot_health.txt"

def update_health_check():
    """Обновляет файл проверки здоровья текущим временем."""
    try:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(HEALTH_FILE, "w") as f:
            f.write(now)
        logging.info(f"Файл здоровья обновлен: {now}")
    except Exception as e:
        logging.error(f"Ошибка при обновлении файла здоровья: {e}")

def setup_webhook(domain):
    """Настраивает webhook для бота."""
    from config import TELEGRAM_TOKEN
    
    # Формируем URL для webhook на основе домена
    webhook_url = f"https://{domain}/webhook/{TELEGRAM_TOKEN}"
    
    # Сначала удаляем старый webhook, если он был
    delete_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteWebhook"
    try:
        response = requests.post(delete_url)
        if response.status_code == 200:
            result = response.json()
            logging.info(f"Предыдущий webhook удален: {result}")
        else:
            logging.error(f"Ошибка при удалении webhook: {response.text}")
            return False
    except Exception as e:
        logging.error(f"Исключение при удалении webhook: {e}")
        return False
    
    # Устанавливаем новый webhook
    set_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook"
    try:
        params = {
            'url': webhook_url,
            'max_connections': 40,
            'allowed_updates': ['message', 'callback_query', 'chat_member']
        }
        response = requests.post(set_url, json=params)
        if response.status_code == 200:
            result = response.json()
            logging.info(f"Webhook успешно установлен: {result}")
            return True
        else:
            logging.error(f"Ошибка при установке webhook: {response.text}")
            return False
    except Exception as e:
        logging.error(f"Исключение при установке webhook: {e}")
        return False

def check_webhook_status():
    """Проверяет статус webhook."""
    from config import TELEGRAM_TOKEN
    
    check_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getWebhookInfo"
    try:
        response = requests.get(check_url)
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                webhook_info = result.get("result", {})
                webhook_url = webhook_info.get("url", "")
                if webhook_url:
                    logging.info(f"Webhook активен: {webhook_url}")
                    return True
                else:
                    logging.error("Webhook не настроен")
                    return False
            else:
                logging.error(f"Ошибка ответа API: {result}")
                return False
        else:
            logging.error(f"Ошибка запроса статуса webhook: {response.text}")
            return False
    except Exception as e:
        logging.error(f"Исключение при проверке webhook: {e}")
        return False

def main():
    """Основная функция для поддержки webhook."""
    logging.info("Запуск webhook_monitor.py...")
    
    # Настраиваем обработчик сигналов для корректного завершения
    def signal_handler(sig, frame):
        logging.info("Получен сигнал остановки. Завершаем работу...")
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
    
    # Проверяем текущий статус webhook
    webhook_status = check_webhook_status()
    
    # Если webhook не настроен, настраиваем его
    if not webhook_status:
        logging.info("Webhook не настроен. Настраиваем...")
        setup_result = setup_webhook(replit_domain)
        if not setup_result:
            logging.error("Не удалось настроить webhook")
            return 1
    
    # Основной цикл мониторинга
    logging.info("Webhook настроен и активен. Запускаем мониторинг...")
    
    last_check_time = 0
    check_interval = 300  # 5 минут между проверками webhook
    
    while True:
        try:
            # Обновляем файл здоровья
            update_health_check()
            
            # Периодически проверяем статус webhook
            current_time = time.time()
            if current_time - last_check_time > check_interval:
                webhook_status = check_webhook_status()
                if not webhook_status:
                    logging.warning("Webhook не активен. Переустанавливаем...")
                    setup_webhook(replit_domain)
                last_check_time = current_time
            
            # Ждем перед следующей итерацией
            time.sleep(60)
            
        except Exception as e:
            logging.error(f"Ошибка в цикле мониторинга: {e}")
            time.sleep(10)  # Короткая пауза перед повторной попыткой в случае ошибки

if __name__ == "__main__":
    sys.exit(main())