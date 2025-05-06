#!/usr/bin/env python
"""
Минимальный бот с подробным логированием
"""
import os
import sys
import logging
import json
import time
import traceback

# Настройка детального логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger("minimal_bot")

def check_environment():
    """Проверка переменных окружения"""
    logger.info("Проверка системной информации:")
    logger.info(f"Python версия: {sys.version}")
    logger.info(f"Текущая директория: {os.getcwd()}")
    
    # Проверка содержимого директории
    try:
        files = os.listdir('.')
        logger.info(f"Содержимое директории ({len(files)} файлов):")
        for file in sorted(files[:20]):  # Показываем только первые 20 файлов
            logger.info(f"  - {file}")
        if len(files) > 20:
            logger.info(f"  ... и еще {len(files) - 20} файлов")
    except Exception as e:
        logger.error(f"Ошибка при получении списка файлов: {e}")
    
    # Проверка переменных окружения (без вывода значений)
    logger.info("Проверка переменных окружения:")
    environment_vars = [
        "TELEGRAM_TOKEN", "DATABASE_URL", "OPENAI_API_KEY",
        "PGUSER", "PGHOST", "PGPASSWORD", "PGDATABASE", "PGPORT"
    ]
    
    for var in environment_vars:
        if os.environ.get(var):
            logger.info(f"  ✓ {var}: установлен")
        else:
            logger.info(f"  ✗ {var}: отсутствует")

def try_import_telegram():
    """Попытка импорта модуля python-telegram-bot"""
    logger.info("Проверка импорта telegram:")
    try:
        import telegram
        from telegram.ext import ApplicationBuilder, CommandHandler
        logger.info(f"  ✓ python-telegram-bot импортирован успешно (версия: {telegram.__version__})")
        return True
    except ImportError as e:
        logger.error(f"  ✗ Ошибка импорта python-telegram-bot: {e}")
        return False
    except Exception as e:
        logger.error(f"  ✗ Неизвестная ошибка при импорте: {e}")
        logger.error(traceback.format_exc())
        return False

def try_connect_telegram_api():
    """Попытка подключения к Telegram API"""
    logger.info("Проверка подключения к Telegram API:")
    token = os.environ.get("TELEGRAM_TOKEN")
    
    if not token:
        logger.error("  ✗ TELEGRAM_TOKEN отсутствует в переменных окружения")
        return False
    
    try:
        import requests
        url = f"https://api.telegram.org/bot{token}/getMe"
        logger.info(f"  Отправка запроса к {url.replace(token, '[СКРЫТО]')}")
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                bot_info = data.get("result", {})
                logger.info(f"  ✓ Успешное подключение к API! Бот: @{bot_info.get('username')} ({bot_info.get('first_name')})")
                return True
            else:
                logger.error(f"  ✗ API вернул ошибку: {data.get('description')}")
        else:
            logger.error(f"  ✗ Ошибка HTTP: {response.status_code} {response.text}")
        
        return False
    except Exception as e:
        logger.error(f"  ✗ Исключение при подключении к API: {e}")
        logger.error(traceback.format_exc())
        return False

def try_start_minimal_bot():
    """Попытка запуска минимального бота"""
    logger.info("Попытка запуска минимального бота:")
    
    if not try_import_telegram():
        return False
    
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        logger.error("  ✗ TELEGRAM_TOKEN отсутствует")
        return False
    
    try:
        from telegram.ext import ApplicationBuilder, CommandHandler
        
        logger.info("  Создание приложения...")
        application = ApplicationBuilder().token(token).build()
        
        async def start_command(update, context):
            logger.info(f"  Получена команда /start от {update.effective_user.username}")
            await update.message.reply_text("Привет! Я работаю!")
        
        logger.info("  Регистрация обработчика команды /start")
        application.add_handler(CommandHandler("start", start_command))
        
        logger.info("  Запуск приложения...")
        application.run_polling(drop_pending_updates=True)
        
        return True
    except Exception as e:
        logger.error(f"  ✗ Ошибка при запуске бота: {e}")
        logger.error(traceback.format_exc())
        return False

def main():
    """Основная функция"""
    logger.info("=" * 50)
    logger.info("ЗАПУСК ДИАГНОСТИКИ БОТА")
    logger.info("=" * 50)
    
    try:
        # Проверка окружения
        check_environment()
        
        # Проверка подключения к API
        api_ok = try_connect_telegram_api()
        
        if api_ok:
            logger.info("Подключение к API успешно, пробуем запустить минимального бота...")
            try_start_minimal_bot()
        else:
            logger.error("Не удалось подключиться к API, бот не будет запущен")
    
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    main()