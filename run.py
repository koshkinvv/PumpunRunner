#!/usr/bin/env python
"""
Скрипт запуска Telegram бота для бегунов.
Этот скрипт запускает весь комплекс: бот, монитор и систему восстановления.
"""

import os
import sys
import logging
import subprocess
import time
import signal
import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger('runner_bot_launcher')

def signal_handler(sig, frame):
    """Обработчик сигналов для корректного завершения"""
    logger.info(f"Получен сигнал {sig}, завершаем работу")
    sys.exit(0)

# Регистрируем обработчики сигналов
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def main():
    """Основная функция запуска"""
    logger.info("Запуск бота для бегунов")
    
    # Создаем директорию для логов, если нужно
    os.makedirs("logs", exist_ok=True)
    
    # Текущее время для логов
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    try:
        # Запускаем скрипт start_bot_with_monitor
        logger.info("Запуск скрипта управления ботом...")
        proc = subprocess.Popen(
            ["python", "start_bot_with_monitor.py"],
            stdout=open(f"logs/launcher_{timestamp}.log", "w"),
            stderr=open(f"logs/launcher_error_{timestamp}.log", "w")
        )
        
        logger.info(f"Запущен процесс управления ботом (PID: {proc.pid})")
        logger.info(f"Логи сохраняются в: logs/launcher_{timestamp}.log")
        
        # Ждем завершения процесса
        proc.wait()
        
        exit_code = proc.returncode
        if exit_code != 0:
            logger.error(f"Процесс завершился с ошибкой, код: {exit_code}")
            
            # Проверяем логи ошибок
            try:
                with open(f"logs/launcher_error_{timestamp}.log", "r") as f:
                    error_logs = f.readlines()
                    if error_logs:
                        logger.error("Последние ошибки:")
                        for line in error_logs[-10:]:
                            logger.error(line.strip())
            except Exception as e:
                logger.error(f"Не удалось прочитать логи ошибок: {e}")
        else:
            logger.info("Процесс успешно завершился")
            
    except KeyboardInterrupt:
        logger.info("Остановлено пользователем")
    except Exception as e:
        logger.error(f"Ошибка при запуске: {e}")
        
    logger.info("Выход из скрипта запуска")

if __name__ == "__main__":
    main()