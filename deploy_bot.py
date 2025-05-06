#!/usr/bin/env python
"""
Супер простой скрипт для запуска бота напрямую.
"""
import logging
import os
import telegram
from telegram.ext import ApplicationBuilder

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def main():
    """Основная функция запуска бота"""
    print("Запуск бота...")
    
    # Получаем токен из переменной окружения
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        print("ОШИБКА: TELEGRAM_TOKEN не найден в переменных окружения!")
        return
    
    # Создаем приложение напрямую
    application = ApplicationBuilder().token(token).build()
    
    # Регистрируем самый простой обработчик
    from telegram.ext import CommandHandler
    
    async def start(update, context):
        await update.message.reply_text('Привет! Я запущен и работаю!')
    
    application.add_handler(CommandHandler("start", start))
    
    # Запускаем polling
    print("Запуск polling...")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()