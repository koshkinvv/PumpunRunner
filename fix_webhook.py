#!/usr/bin/env python3
"""
Скрипт для ручной установки webhook для Telegram бота.
"""

import os
import logging
import sys
import json
import requests
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Получаем токен Telegram из переменных окружения
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    logging.error("Telegram токен не найден в переменных окружения")
    sys.exit(1)

def delete_webhook():
    """Удаляет текущий webhook."""
    try:
        delete_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteWebhook"
        response = requests.post(delete_url)
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                logging.info("Webhook успешно удален")
                return True
            else:
                logging.error(f"Ошибка при удалении webhook: {result.get('description')}")
                return False
        else:
            logging.error(f"Ошибка запроса при удалении webhook: {response.text}")
            return False
    except Exception as e:
        logging.error(f"Исключение при удалении webhook: {e}")
        return False

def set_webhook():
    """Устанавливает новый webhook."""
    try:
        # Получаем домен Replit
        replit_domain = os.environ.get('REPLIT_DOMAINS', '').split(',')[0]
        if not replit_domain:
            # Fallback к старому формату
            replit_domain = f"{os.environ.get('REPL_SLUG')}.{os.environ.get('REPL_OWNER')}.repl.co"
        
        # Формируем URL для webhook
        webhook_url = f"https://{replit_domain}/webhook/{TELEGRAM_TOKEN}"
        logging.info(f"Устанавливаем webhook на URL: {webhook_url}")
        
        # Устанавливаем webhook
        set_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook"
        params = {
            'url': webhook_url,
            'max_connections': 40,
            'allowed_updates': ['message', 'callback_query', 'chat_member']
        }
        response = requests.post(set_url, json=params)
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                logging.info("Webhook успешно установлен")
                logging.info(f"Ответ API: {json.dumps(result, indent=2)}")
                return True
            else:
                logging.error(f"Ошибка при установке webhook: {result.get('description')}")
                return False
        else:
            logging.error(f"Ошибка запроса при установке webhook: {response.text}")
            return False
    except Exception as e:
        logging.error(f"Исключение при установке webhook: {e}")
        return False

def get_webhook_info():
    """Получает информацию о текущем webhook."""
    try:
        info_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getWebhookInfo"
        response = requests.get(info_url)
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                webhook_info = result.get("result", {})
                logging.info(f"Информация о webhook: {json.dumps(webhook_info, indent=2)}")
                return webhook_info
            else:
                logging.error(f"Ошибка при получении информации о webhook: {result.get('description')}")
                return None
        else:
            logging.error(f"Ошибка запроса при получении информации о webhook: {response.text}")
            return None
    except Exception as e:
        logging.error(f"Исключение при получении информации о webhook: {e}")
        return None

def main():
    """Основная функция скрипта."""
    # Получаем текущую информацию о webhook
    logging.info("Получаем информацию о текущем webhook...")
    get_webhook_info()
    
    # Удаляем текущий webhook
    logging.info("Удаляем текущий webhook...")
    if not delete_webhook():
        logging.error("Не удалось удалить webhook. Выход.")
        return 1
    
    # Устанавливаем новый webhook
    logging.info("Устанавливаем новый webhook...")
    if not set_webhook():
        logging.error("Не удалось установить webhook. Выход.")
        return 1
    
    # Проверяем, что webhook успешно установлен
    logging.info("Проверяем статус webhook...")
    webhook_info = get_webhook_info()
    if webhook_info and webhook_info.get("url"):
        logging.info(f"Webhook успешно настроен на URL: {webhook_info.get('url')}")
        return 0
    else:
        logging.error("Не удалось подтвердить установку webhook.")
        return 1

if __name__ == "__main__":
    sys.exit(main())