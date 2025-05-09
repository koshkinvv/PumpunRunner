"""
Запускает Telegram бота с обновленным форматированием отображения тренировочных планов.
Используются форматирование из function format_training_day() для всех типов тренировок.
"""
import asyncio
import logging
import os
from bot_modified import setup_bot

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/bot.log")
    ]
)

# Создаем директорию для логов, если её нет
os.makedirs("logs", exist_ok=True)

async def main():
    """Точка входа для запуска бота."""
    # Настраиваем и запускаем бота
    app = setup_bot()
    
    # Запуск бота
    await app.initialize()
    await app.start()
    
    logging.info("Бот запущен и готов к работе! Нажмите Ctrl+C для остановки.")
    
    # Ожидаем до остановки бота
    try:
        await app.updater.stop_polling()
    except asyncio.CancelledError:
        pass
    finally:
        await app.stop()
        
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Бот остановлен вручную.")
    except Exception as e:
        logging.error(f"Ошибка при запуске бота: {e}")