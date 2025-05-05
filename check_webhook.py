#!/usr/bin/env python
"""
Скрипт для проверки настроек webhook в Telegram API.
"""

import os
import sys
import logging
import asyncio
from dotenv import load_dotenv
from bot_modified import setup_bot

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("check_webhook")

async def check_webhook_info():
    """Проверяет текущие настройки webhook в Telegram API."""
    try:
        # Создаем экземпляр бота
        bot = setup_bot()
        
        # Получаем информацию о webhook
        webhook_info = await bot.bot.get_webhook_info()
        
        # Выводим полную информацию о webhook
        logger.info(f"Webhook URL: {webhook_info.url}")
        logger.info(f"Webhook активен: {bool(webhook_info.url)}")
        logger.info(f"Ожидающие обновления: {webhook_info.pending_update_count}")
        logger.info(f"Максимальное количество соединений: {webhook_info.max_connections}")
        logger.info(f"IP-адрес: {webhook_info.ip_address}")
        logger.info(f"Последняя ошибка: {webhook_info.last_error_message}")
        logger.info(f"Дата последней ошибки: {webhook_info.last_error_date}")
        logger.info(f"Последнее обновление успешно: {webhook_info.last_synchronization_error_date is None}")
        
        return webhook_info
    except Exception as e:
        logger.error(f"Ошибка при проверке webhook: {e}")
        return None

async def set_webhook(url=None):
    """Устанавливает webhook для бота."""
    try:
        # Создаем экземпляр бота
        bot = setup_bot()
        
        if not url:
            # Используем REPLIT_DEV_DOMAIN для правильного домена Replit
            replit_domain = os.environ.get("REPLIT_DEV_DOMAIN")
            if replit_domain:
                # Получаем токен из переменных окружения
                telegram_token = os.environ.get("TELEGRAM_TOKEN")
                url = f"https://{replit_domain}/webhook/{telegram_token}"
            else:
                logger.error("Не удалось определить URL для webhook. Установите REPLIT_DEV_DOMAIN.")
                return False
        
        # Устанавливаем webhook
        logger.info(f"Устанавливаем webhook на URL: {url}")
        await bot.bot.set_webhook(url=url)
        
        # Проверяем установку
        webhook_info = await bot.bot.get_webhook_info()
        if webhook_info.url == url:
            logger.info("Webhook успешно установлен!")
            return True
        else:
            logger.warning(f"Webhook не установлен! Текущий URL: {webhook_info.url}")
            return False
    except Exception as e:
        logger.error(f"Ошибка при установке webhook: {e}")
        return False

async def delete_webhook():
    """Удаляет webhook для бота."""
    try:
        # Создаем экземпляр бота
        bot = setup_bot()
        
        # Удаляем webhook
        logger.info("Удаляем webhook...")
        await bot.bot.delete_webhook()
        
        # Проверяем удаление
        webhook_info = await bot.bot.get_webhook_info()
        if not webhook_info.url:
            logger.info("Webhook успешно удален!")
            return True
        else:
            logger.warning(f"Webhook не удален! Текущий URL: {webhook_info.url}")
            return False
    except Exception as e:
        logger.error(f"Ошибка при удалении webhook: {e}")
        return False

async def main():
    """Основная функция скрипта."""
    if len(sys.argv) < 2:
        print("Использование: python check_webhook.py [check|set|delete] [url]")
        return
    
    command = sys.argv[1].lower()
    
    if command == "check":
        await check_webhook_info()
    elif command == "set":
        url = sys.argv[2] if len(sys.argv) > 2 else None
        await set_webhook(url)
    elif command == "delete":
        await delete_webhook()
    else:
        print("Неизвестная команда. Используйте: check, set или delete")

if __name__ == "__main__":
    asyncio.run(main())