"""
Запускает Telegram бота с обновленным форматированием отображения тренировочных планов.
Это упрощенная версия скрипта запуска, которая использует библиотеку python-telegram-bot.
"""
import logging
import os
import sys
from telegram.ext import Application

# Добавляем текущую директорию в путь поиска модулей, если запускаем из другого каталога
sys.path.append('.')

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

def main():
    """Точка входа для запуска бота."""
    from bot_modified import setup_bot
    
    # Получаем токен из переменных окружения
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        logging.error("TELEGRAM_TOKEN не найден в переменных окружения")
        sys.exit(1)
    
    # Настраиваем и запускаем бота
    app = setup_bot()
    
    # Запуск бота
    app.run_polling()
    
    logging.info("Бот остановлен")
        
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Бот остановлен вручную.")
    except Exception as e:
        logging.error(f"Ошибка при запуске бота: {e}")