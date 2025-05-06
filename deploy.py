#!/usr/bin/env python
"""
Упрощенный скрипт запуска бота для Replit Deployment.
"""

import os
import sys
import logging
import time
import signal
import requests
from datetime import datetime

# Настройка логирования
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = f"{log_dir}/deploy_{timestamp}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file)
    ]
)

logger = logging.getLogger('deploy')

def reset_telegram_api():
    """Сбрасывает текущую сессию Telegram API"""
    token = os.environ.get('TELEGRAM_TOKEN')
    if not token:
        logger.error("TELEGRAM_TOKEN не найден в переменных окружения!")
        return False
    
    try:
        # Удаляем вебхук и все необработанные обновления
        url = f"https://api.telegram.org/bot{token}/deleteWebhook?drop_pending_updates=true"
        response = requests.get(url)
        logger.info(f"Сброс API: {response.text}")
        
        # Делаем запрос к getUpdates для полного сброса очереди
        url = f"https://api.telegram.org/bot{token}/getUpdates?offset=-1"
        response = requests.get(url)
        logger.info(f"Сброс очереди обновлений: {response.text}")
        
        return True
    except Exception as e:
        logger.error(f"Ошибка при сбросе API: {e}")
        return False

def run_bot():
    """Запускает бота напрямую"""
    try:
        # Проверяем токен перед импортом и запуском
        token = os.environ.get('TELEGRAM_TOKEN')
        logger.info(f"Проверка токена Telegram: {token[:5]}...{token[-5:]}")
        
        # Проверяем доступность API Telegram
        try:
            response = requests.get(f"https://api.telegram.org/bot{token}/getMe")
            result = response.json()
            if result.get("ok"):
                bot_info = result.get("result", {})
                logger.info(f"Токен проверен успешно! Бот: @{bot_info.get('username')} ({bot_info.get('first_name')})")
            else:
                logger.error(f"Ошибка API Telegram: {result}")
                return False
        except Exception as e:
            logger.error(f"Ошибка при проверке токена: {e}")
            return False
        
        logger.info("Импортируем модуль бота...")
        
        # Пытаемся последовательно импортировать из разных модулей
        try:
            logger.info("Пробуем импортировать из bot_modified.py...")
            from bot_modified import setup_bot
        except ImportError:
            try:
                logger.info("Пробуем импортировать из bot.py...")
                from bot import setup_bot
            except ImportError:
                logger.error("Не удалось импортировать setup_bot из bot_modified.py или bot.py!")
                # Выводим список файлов в текущей директории
                logger.info(f"Содержимое текущей директории: {os.listdir('.')}")
                return False
        
        # Запускаем бота
        logger.info("Настройка и запуск бота...")
        application = setup_bot()
        application.run_polling(drop_pending_updates=True)
        return True
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        logger.exception("Детали исключения:")
        return False

def main():
    """Основная функция запуска бота"""
    logger.info("=" * 60)
    logger.info("ЗАПУСК БОТА В РЕЖИМЕ DEPLOYMENT")
    logger.info("=" * 60)
    
    # Проверяем наличие токена
    if not os.environ.get('TELEGRAM_TOKEN'):
        logger.error("TELEGRAM_TOKEN не найден в переменных окружения!")
        sys.exit(1)
    
    # Сбрасываем API Telegram
    reset_telegram_api()
    
    # Запускаем бота
    for attempt in range(1, 6):
        logger.info(f"Попытка запуска бота #{attempt}/5...")
        if run_bot():
            break
        else:
            logger.error(f"Не удалось запустить бота. Пауза 30 секунд перед следующей попыткой...")
            time.sleep(30)
    
    logger.error("Не удалось запустить бота после нескольких попыток. Завершаем работу.")

if __name__ == "__main__":
    main()