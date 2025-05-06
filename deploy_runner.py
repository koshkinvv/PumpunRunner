#!/usr/bin/env python
"""
Минимальный скрипт для запуска бота в Replit Deployments.
"""
import os
import sys
import logging
import requests
from telegram import Bot
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    filters
)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Получаем токен
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    logger.error("TELEGRAM_TOKEN не найден!")
    sys.exit(1)

# Импортируем из bot_modified.py основные функции
try:
    from bot_modified import (
        help_command, pending_trainings_command, generate_plan_command,
        update_profile_command, callback_query_handler, handle_photo, text_message_handler
    )
    logger.info("Импортированы функции из bot_modified.py")
except ImportError as e:
    logger.error(f"Ошибка импорта из bot_modified.py: {e}")
    # Резервные базовые функции
    async def help_command(update, context):
        """Handler for the /help command."""
        await update.message.reply_text("Справка: доступны команды /start и /help")
    
    pending_trainings_command = help_command
    generate_plan_command = help_command
    update_profile_command = help_command
    
    async def callback_query_handler(update, context):
        await update.callback_query.answer("Функция в разработке")
    
    async def handle_photo(update, context):
        await update.message.reply_text("Анализ фотографий в разработке")
    
    async def text_message_handler(update, context):
        await update.message.reply_text("Пожалуйста, используйте команды для взаимодействия с ботом")


async def start(update, context):
    """Обработчик команды /start."""
    user = update.effective_user
    logger.info(f"Пользователь {user.id} ({user.username}) отправил команду /start")
    
    message = (
        f"👋 Привет, {user.first_name}!\n\n"
        "Я бот для бегунов, который поможет тебе создать персональный план "
        "тренировок.\n\n"
        "Используй /help чтобы узнать больше."
    )
    
    await update.message.reply_text(message)


async def status_command(update, context):
    """Обработчик команды /status для проверки работы бота."""
    await update.message.reply_text("Бот работает в рамках веб-сервиса Replit Deployments")


def main():
    """Запуск бота напрямую"""
    logger.info("====== ЗАПУСК БОТА ======")
    logger.info(f"Python версия: {sys.version}")
    logger.info(f"Рабочая директория: {os.getcwd()}")
    
    # Сброс вебхука перед запуском
    try:
        logger.info("Сброс вебхука...")
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteWebhook?drop_pending_updates=true"
        response = requests.get(url, timeout=10)
        logger.info(f"Сброс вебхука: {response.text}")
    except Exception as e:
        logger.error(f"Ошибка сброса вебхука: {e}")
    
    try:
        # Проверка соединения с API
        bot = Bot(token=TELEGRAM_TOKEN)
        logger.info(f"Бот подключен: {bot.username}")
    except Exception as e:
        logger.error(f"Ошибка подключения к Telegram API: {e}")
        sys.exit(1)
    
    # Создание приложения
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Регистрация обработчиков команд
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("pending", pending_trainings_command))
    app.add_handler(CommandHandler("plan", generate_plan_command))
    app.add_handler(CommandHandler("update", update_profile_command))
    
    # Обработчик inline кнопок
    app.add_handler(CallbackQueryHandler(callback_query_handler))
    
    # Обработчик фотографий
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    # Обработчик текстовых сообщений (должен быть последним)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))
    
    # Запуск поллинга
    logger.info("Запуск поллинга...")
    app.run_polling(allowed_updates=["message", "callback_query", "inline_query"])


if __name__ == "__main__":
    main()