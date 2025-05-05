#!/usr/bin/env python3
"""
Скрипт для тестирования webhook Telegram бота.
"""

import os
import json
import requests
from config import TELEGRAM_TOKEN

# URL вебхука для тестирования
REPLIT_DOMAIN = os.environ.get("REPLIT_DEV_DOMAIN", "19158b70-0a3f-4963-8a92-2b91605d3479-00-1hxlsvnxqgndx.kirk.replit.dev")
WEBHOOK_URL = f"https://{REPLIT_DOMAIN}/webhook/{TELEGRAM_TOKEN}"

# Тестовое сообщение с командой /help
test_message = {
    "update_id": 123456789,
    "message": {
        "message_id": 1,
        "chat": {
            "id": 123456789,
            "type": "private",
            "first_name": "Test",
            "last_name": "User",
            "username": "testuser"
        },
        "from": {
            "id": 123456789,
            "is_bot": False,
            "first_name": "Test",
            "last_name": "User",
            "username": "testuser",
            "language_code": "ru"
        },
        "date": 1637000000,
        "text": "/help"
    }
}

def main():
    """Отправляет тестовый запрос к webhook."""
    print(f"Отправка тестового запроса к {WEBHOOK_URL}")
    
    try:
        # Отправляем запрос с таймаутом 10 секунд для избежания блокировки
        response = requests.post(
            WEBHOOK_URL,
            json=test_message,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        # Выводим результат
        print(f"Статус-код ответа: {response.status_code}")
        print(f"Тело ответа: {response.text}")
        
        if response.status_code == 200:
            print("Тест успешен! Webhook работает корректно.")
        else:
            print(f"Внимание: получен необычный статус-код {response.status_code}")
    
    except Exception as e:
        print(f"Ошибка при тестировании webhook: {e}")

if __name__ == "__main__":
    main()