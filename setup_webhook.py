#!/usr/bin/env python
"""
Скрипт для настройки webhook для Telegram-бота.
Устанавливает webhook и проверяет его работоспособность.
"""

import os
import sys
import json
import asyncio
import logging
from telegram import Bot

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger('webhook_setup')

# Получаем токен Telegram из переменных окружения
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise ValueError("Отсутствует переменная окружения TELEGRAM_TOKEN")

async def setup_webhook():
    """Настраивает webhook для Telegram-бота."""
    try:
        # Создаем экземпляр бота
        bot = Bot(token=TELEGRAM_TOKEN)
        
        # Получаем информацию о текущем webhook
        webhook_info = await bot.get_webhook_info()
        logger.info(f"Текущий webhook: {webhook_info.url}")
        
        # Проверяем, задана ли переменная окружения REPL_SLUG
        repl_slug = os.environ.get("REPL_SLUG")
        if not repl_slug:
            logger.error("Переменная окружения REPL_SLUG не задана.")
            logger.info("Выполните следующую команду:")
            logger.info("echo 'REPL_SLUG=<ваш slug>' >> .env")
            return
        
        # Используем REPLIT_DEV_DOMAIN для правильного домена Replit
        replit_domain = os.environ.get("REPLIT_DEV_DOMAIN")
        if not replit_domain:
            logger.error("Переменная окружения REPLIT_DEV_DOMAIN не задана.")
            return
        
        # Формируем URL для webhook
        webhook_url = f"https://{replit_domain}/webhook/{TELEGRAM_TOKEN}"
        
        # Устанавливаем webhook
        logger.info(f"Устанавливаем webhook на URL: {webhook_url}")
        await bot.set_webhook(url=webhook_url)
        
        # Проверяем, что webhook установлен
        webhook_info = await bot.get_webhook_info()
        if webhook_info.url == webhook_url:
            logger.info("✅ Webhook успешно установлен!")
            logger.info(f"URL: {webhook_url}")
            logger.info(f"Последняя ошибка: {webhook_info.last_error_message or 'Нет ошибок'}")
            logger.info(f"Ожидающие обновления: {webhook_info.pending_update_count}")
        else:
            logger.error(f"❌ Не удалось установить webhook. Текущий URL: {webhook_info.url}")
    except Exception as e:
        logger.error(f"Ошибка при настройке webhook: {e}")

async def main():
    """Основная функция."""
    await setup_webhook()

if __name__ == "__main__":
    asyncio.run(main())