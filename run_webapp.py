#!/usr/bin/env python
"""
Скрипт для запуска веб-приложения для мониторинга бота.
"""

import os
import sys
import time
import logging
import subprocess
import signal

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger('webapp_runner')

def signal_handler(sig, frame):
    """Обработчик сигналов для корректного завершения"""
    logger.info(f"Получен сигнал {sig}, завершаем работу")
    sys.exit(0)

# Регистрируем обработчики сигналов
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def main():
    """Основная функция запуска веб-приложения"""
    logger.info("Запуск веб-приложения для мониторинга бота")
    
    # Создаем директорию для логов, если нужно
    os.makedirs("logs", exist_ok=True)
    
    # Запускаем gunicorn с приложением
    try:
        cmd = [
            "gunicorn",
            "--bind", "0.0.0.0:5000",
            "--workers", "2",
            "--timeout", "120",
            "--access-logfile", "logs/gunicorn_access.log",
            "--error-logfile", "logs/gunicorn_error.log",
            "--log-level", "info",
            "--reload",  # Автоматически перезагружает при изменении файлов
            "wsgi:app"  # Модуль и объект приложения
        ]
        
        logger.info(f"Выполняем команду: {' '.join(cmd)}")
        
        process = subprocess.Popen(cmd)
        logger.info(f"Веб-приложение запущено (PID: {process.pid})")
        
        # Ждем завершения процесса
        process.wait()
        
        logger.info(f"Процесс веб-приложения завершен с кодом: {process.returncode}")
    except KeyboardInterrupt:
        logger.info("Остановлено пользователем")
    except Exception as e:
        logger.error(f"Ошибка при запуске веб-приложения: {e}")
    
    logger.info("Выход из скрипта запуска веб-приложения")

if __name__ == "__main__":
    main()