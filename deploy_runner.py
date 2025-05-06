#!/usr/bin/env python
"""
Сверхпростой скрипт для запуска бота в Replit Deployments.
"""
import os
import sys
import logging
import time
import requests

# Настройка логирования на стандартный вывод
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger("deploy_runner")

def main():
    """Основная функция запуска бота"""
    # Выводим отладочную информацию
    logger.info("==== Запуск бота в Replit Deployments ====")
    logger.info(f"Текущая директория: {os.getcwd()}")
    logger.info(f"Список файлов: {os.listdir('.')}")
    
    # Проверяем токен Telegram
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        logger.error("TELEGRAM_TOKEN отсутствует в переменных окружения!")
        sys.exit(1)
    
    # Проверяем валидность токена
    try:
        logger.info("Проверка токена Telegram...")
        response = requests.get(f"https://api.telegram.org/bot{token}/getMe")
        if response.status_code == 200 and response.json().get("ok"):
            bot_info = response.json().get("result", {})
            logger.info(f"Токен валиден! Бот: @{bot_info.get('username')} ({bot_info.get('first_name')})")
        else:
            logger.error(f"Токен недействителен! Ответ API: {response.text}")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Ошибка при проверке токена: {e}")
        sys.exit(1)
    
    # Сбрасываем вебхук и очищаем обновления
    try:
        logger.info("Сброс вебхука...")
        response = requests.get(f"https://api.telegram.org/bot{token}/deleteWebhook?drop_pending_updates=true")
        logger.info(f"Результат сброса вебхука: {response.text}")
    except Exception as e:
        logger.error(f"Ошибка при сбросе вебхука: {e}")
    
    # Импорт и запуск бота
    try:
        logger.info("Импорт setup_bot из bot_modified.py...")
        from bot_modified import setup_bot
        
        logger.info("Настройка бота...")
        application = setup_bot()
        
        logger.info("Запуск бота в режиме polling...")
        application.run_polling(drop_pending_updates=True)
    except ImportError:
        logger.error("Ошибка импорта из bot_modified.py!")
        try:
            logger.info("Пробуем bot.py...")
            from bot import setup_bot
            
            logger.info("Настройка бота...")
            application = setup_bot()
            
            logger.info("Запуск бота в режиме polling...")
            application.run_polling(drop_pending_updates=True)
        except Exception as e:
            logger.error(f"Критическая ошибка при запуске бота: {e}")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске бота: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()