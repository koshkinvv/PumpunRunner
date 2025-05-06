
#!/usr/bin/env python
"""
Прямой запуск бота для workflow и деплоя.
"""
import os
import sys
import signal
import logging
import psutil
import time
from telegram import Bot
from telegram.error import TelegramError
from bot_modified import setup_bot

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/start_bot_directly.log")
    ]
)
logger = logging.getLogger('start_bot_directly')

async def cleanup_telegram_session():
    """Сброс сессии Telegram API"""
    try:
        token = os.getenv('TELEGRAM_TOKEN')
        if not token:
            logger.error("TELEGRAM_TOKEN не найден в переменных окружения")
            return
            
        bot = Bot(token=token)
        # Удаляем вебхук
        result = await bot.delete_webhook()
        logger.info(f"Удаление вебхука: {result}")
        
        # Сброс обновлений с разными offset
        for offset in [10, 20, 30]:
            try:
                status = await bot.get_updates(offset=offset, timeout=1)
                logger.info(f"Сброс с offset={offset}: {status.status_code if hasattr(status, 'status_code') else 200}")
            except TelegramError as e:
                logger.warning(f"Ошибка при сбросе обновлений (offset={offset}): {e}")
            await asyncio.sleep(2)
    except Exception as e:
        logger.error(f"Ошибка при очистке сессии Telegram: {e}")

def kill_other_bots():
    """Завершает другие процессы бота"""
    current_pid = os.getpid()
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.pid == current_pid:
                continue
            if proc.info['cmdline'] and any('python' in cmd.lower() for cmd in proc.info['cmdline']):
                if any('bot' in cmd.lower() for cmd in proc.info['cmdline']):
                    logger.info(f"Завершаем процесс бота: {proc.pid}")
                    os.kill(proc.pid, signal.SIGTERM)
                    time.sleep(1)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

async def main():
    """Основная функция запуска"""
    logger.info("=" * 50)
    logger.info("ПРЯМОЙ ЗАПУСК БОТА ДЛЯ WORKFLOW")
    logger.info("=" * 50)
    
    try:
        # Завершаем другие процессы бота
        kill_other_bots()
        
        # Очищаем сессию Telegram
        logger.info("Сброс сессии Telegram API...")
        await cleanup_telegram_session()
        
        # Настраиваем и запускаем бота
        logger.info("Настройка бота...")
        application = setup_bot()
        
        # Запускаем бота
        logger.info("Запуск бота...")
        application.run_polling(drop_pending_updates=True)
        
    except KeyboardInterrupt:
        logger.info("Получен сигнал завершения")
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
