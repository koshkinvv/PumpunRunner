#!/usr/bin/env python
"""
Минимальная версия бота для запуска в Replit Deployments.
Только самая базовая функциональность.
"""
import os
import sys
import logging
import asyncio
from datetime import datetime
from telegram import Update, Bot
from telegram.ext import (
    Application, CommandHandler, ContextTypes, CallbackContext
)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger("minimal_bot")

# Получение токена
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    logger.error("TELEGRAM_TOKEN не найден!")
    sys.exit(1)

# Базовые команды
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help."""
    logger.info(f"Пользователь {update.effective_user.id} отправил команду /help")
    
    help_text = (
        "🏃‍♂️ <b>Доступные команды</b>:\n\n"
        "/start - Начать работу с ботом\n"
        "/help - Показать это сообщение\n"
        "/status - Проверить статус бота\n\n"
        "🚧 <i>Остальные команды находятся в разработке</i>"
    )
    
    await update.message.reply_text(help_text, parse_mode="HTML")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /status для проверки работы бота."""
    user = update.effective_user
    logger.info(f"Пользователь {user.id} ({user.username}) отправил команду /status")
    
    # Подготовим информацию о статусе
    now = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    status_text = (
        f"🟢 <b>Бот работает</b>\n\n"
        f"⏱ Текущее время: {now}\n"
        f"👤 Ваш ID: {user.id}\n"
        f"👤 Имя: {user.first_name}\n"
        f"🤖 Версия бота: минимальная (тестовая)\n\n"
        f"✅ API Telegram: подключено\n"
        f"🏃‍♂️ Режим: только базовые команды"
    )
    
    await update.message.reply_text(status_text, parse_mode="HTML")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик ошибок."""
    logger.error(f"Возникла ошибка: {context.error}")
    logger.error(f"Update: {update}")
    
    if update and isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            "Произошла ошибка при обработке команды. Попробуйте позже."
        )

async def check_api_status():
    """Регулярная проверка статуса API."""
    while True:
        try:
            bot = Bot(token=TELEGRAM_TOKEN)
            me = await bot.get_me()
            logger.info(f"Бот {me.first_name} ({me.username}) активен и работает")
        except Exception as e:
            logger.error(f"Ошибка при проверке API: {e}")
        
        await asyncio.sleep(60)  # Проверка раз в минуту

def main():
    """Запуск бота."""
    logger.info("====== ЗАПУСК МИНИМАЛЬНОГО БОТА ======")
    logger.info(f"Python версия: {sys.version}")
    logger.info(f"Рабочая директория: {os.getcwd()}")
    
    # Предварительный сброс вебхука
    try:
        import requests
        logger.info("Сброс вебхука перед запуском...")
        reset_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteWebhook?drop_pending_updates=true"
        response = requests.get(reset_url, timeout=10)
        logger.info(f"Результат сброса вебхука: {response.text}")
    except Exception as e:
        logger.error(f"Ошибка при сбросе вебхука: {e}")
    
    # Создание приложения
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Регистрация обработчиков
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status_command))
    
    # Обработчик ошибок
    app.add_error_handler(error_handler)
    
    # Запуск задачи проверки статуса
    loop = asyncio.get_event_loop()
    loop.create_task(check_api_status())
    
    # Запуск поллинга
    logger.info("Запуск поллинга...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()