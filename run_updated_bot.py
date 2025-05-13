"""
Скрипт для запуска обновленной версии бота.
"""
import asyncio
import logging
import os
import sys

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def main():
    """Основная функция для запуска бота."""
    try:
        # Импортируем необходимые модули
        from bot_modified import setup_bot
        from telegram.ext import ApplicationBuilder

        # Получаем токен бота из переменных окружения
        token = os.environ.get("TELEGRAM_TOKEN")
        if not token:
            logger.error("Токен бота не найден. Убедитесь, что переменная окружения TELEGRAM_TOKEN установлена.")
            sys.exit(1)

        # В bot_modified.py функция setup_bot не принимает аргументов,
        # а создает и настраивает application внутри себя
        from bot_modified import setup_bot
        application = setup_bot()

        # Запускаем бота
        logger.info("Бот запущен...")
        await application.initialize()
        await application.start()
        await application.updater.start_polling()

        # Держим бота запущенным до прерывания
        # Блокируем выполнение, чтобы бот работал непрерывно
        print("Бот успешно запущен и работает...")
        
        # Ждем неопределенно долго, чтобы бот не завершился
        try:
            while True:
                await asyncio.sleep(3600)  # Ждем час и проверяем снова
                print("Бот все еще работает...")
        except (KeyboardInterrupt, SystemExit):
            # При получении сигнала остановки корректно завершаем работу
            print("Получен сигнал остановки бота...")
            
        # Остановка и очистка в случае прерывания
        if application.updater:
            await application.updater.stop()
        await application.stop()
        await application.shutdown()

    except Exception as e:
        logger.error(f"Произошла ошибка при запуске бота: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Запускаем асинхронное приложение
    asyncio.run(main())