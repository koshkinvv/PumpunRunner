"""
Упрощенный вариант бота для отладки проблем с API Telegram.
"""
import os
import logging
import asyncio
from telegram import Bot, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Получение токена Telegram из переменных окружения
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    logger.error("Не установлен TELEGRAM_TOKEN в переменных окружения")
    exit(1)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start."""
    await update.message.reply_text("Привет! Я работаю корректно.")


async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /ping."""
    await update.message.reply_text("Pong! Я работаю корректно.")


def setup_app():
    """Настраивает и возвращает приложение бота."""
    logger.info("Настройка бота с токеном: %s...", TELEGRAM_TOKEN[:5] + "...")
    
    # Создаем экземпляр приложения
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("ping", ping_command))
    
    logger.info("Бот настроен успешно")
    return application


async def main() -> None:
    """Точка входа для запуска бота."""
    try:
        logger.info("Запуск бота...")
        app = setup_app()
        await app.initialize()  # Инициализация перед запуском
        await app.start()
        await app.updater.start_polling()
        
        logger.info("Бот запущен успешно")
        
        # Бесконечный цикл для поддержания работы бота
        while True:
            await asyncio.sleep(1)
    except Exception as e:
        logger.error("Ошибка при запуске бота: %s", e, exc_info=True)
    finally:
        # Корректное завершение при остановке
        if 'app' in locals():
            await app.updater.stop()
            await app.stop()
            await app.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error("Необработанная ошибка: %s", e, exc_info=True)