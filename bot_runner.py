"""
Запускает бота из bot_modified.py с полной функциональностью.
"""
import os
import logging
import asyncio
from bot_modified import setup_bot

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

async def main():
    """Точка входа для запуска бота."""
    # Объявляем переменную application в глобальной области видимости функции
    application = None
    
    try:
        logger.info("Запуск бота из bot_modified.py...")
        
        # Сначала сбрасываем Telegram API для решения проблем с конфликтами
        try:
            import requests
            import os
            
            token = os.environ.get("TELEGRAM_TOKEN")
            if token:
                url = f"https://api.telegram.org/bot{token}/deleteWebhook?drop_pending_updates=true"
                response = requests.get(url, timeout=10)
                logger.info(f"Сброс вебхука: {response.text}")
        except Exception as e:
            logger.warning(f"Ошибка при сбросе вебхука: {e}")
        
        # Получаем настроенное приложение бота из bot_modified.py
        application = setup_bot()
        
        # Запускаем бот в режиме long polling
        logger.info("Инициализация бота...")
        await application.initialize()
        
        logger.info("Запуск бота...")
        await application.start()
        
        logger.info("Запуск long polling...")
        await application.updater.start_polling()
        
        logger.info("Бот успешно запущен!")
        
        # Бесконечный цикл для поддержания работы бота
        while True:
            await asyncio.sleep(1)
            
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}", exc_info=True)
    finally:
        # Корректное завершение при остановке
        if application:
            logger.info("Останавливаем updater...")
            try:
                await application.updater.stop()
            except Exception as e:
                logger.error(f"Ошибка при остановке updater: {e}")
                
            logger.info("Останавливаем бота...")
            try:
                await application.stop()
            except Exception as e:
                logger.error(f"Ошибка при остановке бота: {e}")
                
            logger.info("Завершаем работу бота...")
            try:
                await application.shutdown()
            except Exception as e:
                logger.error(f"Ошибка при завершении работы бота: {e}")
                
            logger.info("Бот остановлен корректно")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Необработанная ошибка: {e}", exc_info=True)