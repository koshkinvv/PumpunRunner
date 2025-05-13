#!/usr/bin/env python3
"""
Скрипт для запуска веб-приложения Flask со страницей лендинга и админ-панелью.
Запускает сервер Flask на порту 5000.
"""
import subprocess
import sys
import os
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("webapp.log")
    ]
)
logger = logging.getLogger("webapp_runner")

def run_webapp():
    """Запускает веб-приложение на порту 5000."""
    try:
        logger.info("Запуск веб-приложения...")
        
        # Запускаем Flask приложение напрямую, без subprocess
        # Это позволит приложению работать в текущем процессе без ограничений по времени
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        
        # Импортируем app и запускаем его
        from app import app
        
        logger.info("Веб-приложение успешно запущено на порту 5000")
        
        # Запускаем Flask приложение
        app.run(debug=True, host='0.0.0.0', port=5000)
        
    except Exception as e:
        logger.error(f"Ошибка при запуске веб-приложения: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    run_webapp()